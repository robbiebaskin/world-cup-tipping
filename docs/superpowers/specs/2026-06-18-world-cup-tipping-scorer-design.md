# World Cup 2026 Tipping Scorer — Design Spec

**Date:** 2026-06-18
**Status:** Approved for planning

## Context

A 63-entrant World Cup tipping competition is currently run from a single Excel
workbook (`World Cup Tipping 2026.xlsx`). Each entrant ranked teams within the 12
groups before the tournament; those rankings are fixed. As the tournament plays
out, the organiser must **manually** tally each team's wins/draws/goals/cards and
knockout progress into the workbook's `Results` tab, and the workbook then
multiplies those team totals by each entrant's per-team rank multiplier.

Two problems with the current workbook:
1. Inputs are hand-tallied per team. The organiser wants to feed in **match
   results** and have wins/draws/losses, goals for/against, cards, and knockout
   milestones derived automatically — ideally pulled live from a data feed.
2. The workbook shows each entrant's **total** only. The organiser wants the
   **make-up of each entrant's score, broken down by country** (how many points
   each backed team contributed, and from what — wins, draws, goals, cards,
   milestones).

This spec defines a Python tool that replaces the manual data-entry half of the
workbook while reproducing its scoring logic exactly, and adds the per-country
breakdown.

## Goals

- Pull live 2026 World Cup results from a free source (no manual tallying).
- Reproduce the workbook's scoring **exactly** (team points + rank multipliers).
- Output the **ladder** (all 63 entrants, ranked) and, per entrant, a
  **per-country breakdown** of their score.
- Be re-runnable any time during the tournament; cache feed data so a re-run is
  deterministic and offline-capable.
- **All reference data is code-extracted into versioned JSON, never hand-authored
  from memory** (see below). The output then auto-updates from the live feed with
  no further data entry.

## Core principle: extract, don't transcribe

Nothing about the competition (entrant rankings, the 48-team roster, group
memberships, the ESPN↔workbook name map) is typed into source code from memory.
Each is **extracted by code from its authoritative source** and written to a
clean JSON file that is the stable interface for the rest of the tool:

- The `.xlsx` is the authority for entrants, rankings, roster, and groups.
- The ESPN feed is the authority for live results.
- The name map is **generated** by matching ESPN names against the extracted
  roster (exact + normalized match), with only the genuine non-matches recorded
  in a small reviewed `name_map_exceptions.json`.

This removes hallucination risk and cleanly separates *static reference data*
(extracted once, re-extracted only if the workbook changes) from *live data*
(re-fetched each run). See "Reference data" below for the file schemas.

## Non-goals

- No web UI. CLI + file output (console, CSV, Markdown).
- No live push/auto-refresh daemon. The user runs it on demand.
- Not editing or writing back to the original `.xlsx`.

## Scoring rules (ground truth, from the workbook)

### Layer 1 — each team's "performance points"

Verbatim from the `Results!O` formula in the workbook:

| Component | Weight |
|---|---|
| Win | +5 |
| Draw (incl. games decided on penalties) | +3 |
| Loss | 0 |
| Goal for | +2 each |
| Goal against | −1 each |
| Yellow card | −1 each |
| Red card | −5 each |
| Group winner | +5 |
| Qualify from group | +2 |
| Reach Quarter Final | +10 |
| Reach Semi Final | +15 |
| Reach Final | +20 |
| Win the World Cup | +30 |

`team_points = 5*W + 3*D + 0*L + 2*GF − 1*GA − 1*Y − 5*R + 5*GroupWinner
+ 2*Qualify + 10*QF + 15*SF + 20*Final + 30*Winner`

(Team points can be negative — e.g. heavy goals-against + cards.)

### Layer 2 — each entrant's score

Each entrant assigned each team a **multiplier** based on how they ranked it:

| Rank | Multiplier |
|---|---|
| ⭐ Starred team (predicted champion) | ×5 |
| Ranked 1 | ×3 |
| Ranked 2 | ×2 |
| Ranked 3 | ×1 |
| Unranked (4th team in a group) | ×0 |

In the starred team's own group all four teams are ranked (⭐ + 1/2/3); in the
other 11 groups only the top 3 are ranked, leaving one team at ×0.

For each entrant: `entrant_total = Σ over teams (team_points × entrant_multiplier)`.
A ×0 team contributes nothing. A positively-multiplied team that scores negative
points **reduces** the entrant's total.

The per-country breakdown decomposes each backed team's contribution into its
components ×multiplier, e.g. for a team with multiplier 3:
`country_breakdown = {W: 3*5*w, D: 3*3*d, GF: 3*2*gf, GA: 3*(−1)*ga, ...}`.

## Data source: ESPN unofficial API (validated)

Endpoint (free, no key, JSON):

```
https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=YYYYMMDD-YYYYMMDD&limit=300
```

Validated 2026-06-18: returns real 2026 World Cup data (22 completed + 1
in-progress at time of writing), matching reality. Per-match fields used:

- `events[].competitions[0].competitors[]` → `team.displayName`, `team.id`,
  `score` (full-time goals), `homeAway`, and (knockouts) `shootoutScore`.
- `events[].competitions[0].status.type` → `name` (`STATUS_FULL_TIME`, …) and
  `completed` (bool). Only `completed` matches are scored.
- `events[].competitions[0].details[]` → discipline/goal events; each has
  `type.text` (`Goal`, `Own Goal`, `Yellow Card`, `Red Card`) and `team.id`.
  Cards are counted from here, per team.
- Stage: `events[].season.slug` (`group-stage`, `round-of-32`,
  `round-of-16`, `quarterfinals`, `semifinals`, `final`) plus
  `competitions[0].notes[].headline` / `altGameNote` (e.g. "FIFA World Cup,
  Group A") as a cross-check.

**Caching:** every fetch is written to `data/cache/espn-<rangestart>-<rangeend>.json`.
Scoring reads from cache; a `--refresh` flag re-fetches. This makes runs
deterministic, offline-replayable, and resilient to ESPN outages or glitches.

### Date-range query note

The `dates=START-END` range query and per-day single-date queries both return
the full set (verified: 28 events incl. scheduled, day-by-day sum identical), so
the tool issues **one** range request `20260611-20260719`.

## Team identity & group membership

The competition draw is fixed and already encoded in the workbook. The tool
treats the workbook's roster as canonical:

- **Canonical roster** = the 48 teams in `Results` (12 groups × 4), in group
  order. This gives group membership without relying on ESPN's group labels.
- **ESPN → canonical name map** (one boundary only), held in the generated
  `data/reference/name_map.json` (see "Reference data"). It is produced by code
  matching ESPN `displayName`s against the extracted roster, not transcribed by
  hand. Examples that the matcher resolves or records as exceptions:
  `South Korea→Korea Rep`, `Türkiye→Turkey`, `Curaçao→Curacao`,
  `Congo DR→Congo`, `Uzbekistan→Uzebekistan` (workbook's spelling),
  `Bosnia-Herzegovina→Bosnia`, `United States→USA`. An **unmapped ESPN team
  raises a hard error** (never silently dropped).
- **Entrant multipliers** join to teams **positionally** (group index, slot
  index) from the `Entries` tab — no cross-tab name matching needed.

## Derived results

For each **completed** match between teams in the same group / a knockout stage:

- **W/D/L**: from full-time `score`. Equal score = draw for both. In a knockout
  decided on penalties (detected via `shootoutScore` present / level FT score in
  a KO stage), it counts as a **draw (+3) for both**; the shootout winner gets
  the next stage's milestone.
- **Goals for / against**: from `score` (own goals already reflected in the
  scoreline; `details` own-goal events are not double-counted).
- **Yellow / Red**: counted from `details[]` by team. A second yellow is counted
  as **one yellow + one red** (the booking sequence).

Milestones (auto-derived, mostly from stage appearance, avoiding tiebreaker
complexity):

- **Group winner (+5)**: top of the computed group table
  (points → goal difference → goals scored). True ties in the top slot are
  **flagged for manual override**, not guessed.
- **Qualify (+2)**: team appears in any `round-of-32` match.
- **QF (+10) / SF (+15) / Final (+20)**: team appears in a match of that stage.
- **Winner (+30)**: team wins the final.

Group-table points use standard 3-1-0 (this is only for ranking within a group
to find the winner; it is independent of the tipping point weights above).

### Manual override hook

`data/overrides.json` (optional) can patch any team's derived stats or force a
group winner, for the rare cases above or any ESPN data glitch. Applied after
derivation, before scoring. Absent file = no overrides.

## Reference data (extracted by code → versioned JSON)

A one-off extraction step (`extract.py`, re-run only when the workbook changes)
parses the `.xlsx` and writes three human-readable, diff-able JSON files under
`data/reference/`. These are committed and are the stable input to scoring, so a
normal run never touches the binary `.xlsx` at all.

`data/reference/roster.json` — canonical teams + groups (from `Results` tab):
```json
{
  "groups": {
    "A": ["Mexico", "South Africa", "Korea Rep", "Czechia"],
    "B": ["Canada", "Bosnia", "Qatar", "Switzerland"]
  }
}
```

`data/reference/entrants.json` — all 63 entrants (from `Entries` tab):
```json
[
  {
    "name": "Lennon Dresner",
    "starred_team": "Brazil",
    "multipliers": { "Mexico": 2, "Korea Rep": 3, "Czechia": 1, "Brazil": 5, "...": 0 }
  }
]
```

`data/reference/name_map.json` — ESPN `displayName` → canonical roster name,
**generated** by matching the live feed's names against `roster.json`. Generation:
exact match first, then accent/case/punctuation-normalized match
(`Curaçao`→`Curacao`, etc.). Verified against the live feed (50 distinct names,
48 real teams): **42 auto-match**, leaving exactly **6 real aliases** that the
extractor records (after human confirmation) in the map:
```json
{ "South Korea": "Korea Rep.", "Türkiye": "Turkey", "United States": "USA",
  "Congo DR": "Congo", "Bosnia-Herzegovina": "Bosnia", "Uzbekistan": "Uzebekistan" }
```
Knockout-fixture placeholders (`"Group A 2nd Place"`, `"Winner Match 73"`, …)
appear only in not-yet-played matches; the generator filters them out and they
never reach scoring (only completed matches are scored). At runtime, an ESPN
team name absent from the map is a **hard error** — never silently dropped.

Each file carries a `_meta` block (`source`, `extracted_at`, source file mtime)
so the tool can warn if the workbook changed since extraction. The extractor
validates invariants before writing (exactly 12 groups × 4 teams = 48 unique
teams; 63 entrants; each entrant has exactly one ×5 star and multipliers covering
all 48 teams) and fails loudly otherwise, so bad extraction can't reach scoring.

> **Verified 2026-06-18** against the real workbook: roster = 48 teams/12 groups;
> 63 entrants extracted, all matching the `Ladder` names, each with exactly one
> ⭐ and 48 multipliers. The `Ladder!C` "* Selected" column is **hand-typed and
> unreliable** (one confirmed error — it lists "Spain" for Luka Obradovic whose
> grid actually stars France at ×5), so the ⭐ is derived from the **grid
> multiplier of 5**, never from that label.

## Architecture

Python package `wc_scorer/`, focused single-purpose modules:

```
wc_scorer/
  xlsx_reader.py # regex-based .xlsx cell reader (openpyxl is broken here)
  extract.py     # .xlsx -> data/reference/*.json (run only when workbook changes)
  espn.py        # fetch (cached) + parse ESPN feed -> normalized per-match records
  teams.py       # load roster.json + name_map.json; to_canonical() (hard error on unknown)
  rankings.py    # load entrants.json
  scoring.py     # team points (layer 1) + per-entrant per-country breakdown (layer 2)
  report.py      # render ladder + per-country breakdowns to console / CSV / Markdown
  cli.py         # argument parsing, wiring, override application
data/
  reference/     # roster.json, entrants.json, name_map.json (+ exceptions) — committed
  cache/         # raw ESPN JSON snapshots
  overrides.json # optional manual corrections
docs/superpowers/specs/...   # this spec
tests/
```

Runtime split: `extract.py` is the **only** code that reads the binary `.xlsx`
and runs rarely; the scoring path reads only the JSON in `data/reference/` plus
the (cached) live feed, so re-scoring as results change is fast and binary-free.

### Module contracts

- **`xlsx_reader.py`**
  `read_sheet(xlsx_path, sheet_name) -> dict[cellref, Cell]` (`Cell =
  {value, formula}`) using the regex-based reader (openpyxl is broken in this
  environment's Python — expat import fails). Resolves shared strings and
  formula cached values. **Must handle self-closing cells** (`<c r=".." />`,
  used for empty cells) as well as `<c ..>..</c>` — a regex that assumes every
  cell has a closing tag silently swallows following cells and drops data (this
  bug was hit and fixed during spec verification). Shared by the extractor; not
  used at scoring time.

- **`extract.py`**
  `extract(xlsx_path, out_dir, espn_names) -> None`. Writes `roster.json`,
  `entrants.json`, `name_map.json` (+ exceptions). **Verified Entries geometry:**
  17-row blocks (name rows at 1, 18, 35, … = `1 + 17*block`), 3 entrant bands per
  block at column offsets `1 + 17*k` (k=0,1,2 → cols A, R, AI). Within a band, 3
  row-groups (offsets +2, +7, +12 from the name row) each holding 4 groups ×
  4 teams; for group quadrant `q` (0–3): team col = `base + 4*q`, multiplier col =
  `base + 4*q + 2`; the three row-groups map to groups A–D, E–F–G–H, I–J–K–L.
  Multipliers join to teams **positionally** against `roster.json` (so canonical
  spelling wins, e.g. `Korea Rep.`). Loop blocks until one yields no names.
  **Roster geometry:** scan `Results` column A; `Group X` header rows start a
  group, the next 4 non-empty cells are its teams. Validates invariants (48 teams
  / 12 groups, 63 entrants, exactly one ⭐ each, 48 multipliers each) and fails
  loudly before writing.

- **`rankings.py`**
  `load_entrants(ref_dir) -> list[Entrant]` from `entrants.json`, where
  `Entrant = {name, starred_team, multipliers: {canonical_team: int}}`.

- **`teams.py`**
  `load_roster(ref_dir) -> Roster` (12 groups × 4 canonical names, in order) and
  `load_name_map(ref_dir)`. `to_canonical(espn_name)` raises on unknown.

- **`espn.py`**
  `fetch(date_range, refresh=False) -> raw_json` (cached) and
  `parse(raw_json, roster) -> list[Match]` where
  `Match = {stage, team_a, team_b, ga, gb, completed, penalties, winner,
  cards: {team: {yellow, red}}}`.

- **`scoring.py`**
  `team_stats(matches, roster, overrides) -> {team: TeamStats}` (W/D/L, GF, GA,
  Y, R, milestones) → `team_points(TeamStats) -> int`.
  `score_entrant(entrant, team_points_map, team_stats_map) -> EntrantResult`
  with `total` and `by_country` (each backed country's component breakdown ×
  multiplier).

- **`report.py`**
  `ladder(results)` → table sorted by total desc (name, total, ⭐).
  `breakdown(result)` → per-country table: country, mult, W/D/L, GF, GA, Y, R,
  milestones, points. Emit to stdout (pretty), `out/ladder.csv`,
  `out/breakdown.csv`, `out/report.md`.

### Data flow

```
.xlsx ──rankings.py──> entrants (multipliers)
  │
  └────teams.py──────> canonical roster + name map
ESPN API ──espn.py──> cached JSON ──parse──> matches
                                              │
matches + roster + overrides ──scoring.team_stats──> per-team stats ──> per-team points
                                              │
entrants × per-team points/stats ──scoring.score_entrant──> per-entrant total + by_country
                                              │
                                       report.py ──> ladder + breakdowns (console/CSV/MD)
```

## CLI

Two commands — extraction (rare) and scoring (the normal run):

```
# one-off / when the workbook changes: rebuild data/reference/*.json from the .xlsx
python -m wc_scorer extract --rankings "World Cup Tipping 2026.xlsx"

# normal run: reads data/reference/*.json + cached feed; no .xlsx needed
python -m wc_scorer score \
  [--refresh]                 \  # re-fetch from ESPN instead of using cache
  [--dates 20260611-20260719] \
  [--format console,csv,md]   \
  [--out out/]
```

`score` with no flags uses the committed reference JSON + cached feed and prints
the ladder + every entrant's per-country breakdown. To update the output as
results come in: `python -m wc_scorer score --refresh`.

## Testing

- **Golden formula test:** evaluate the literal `Results!O` Excel formula string
  (extracted from the workbook) against randomized component inputs and assert
  `team_points()` returns the identical number — proves Layer 1 is faithful to
  the workbook.
- **Multiplier test:** a small hand-built fixture (2 groups, 3 entrants) with
  hand-computed totals and per-country breakdowns; assert `score_entrant` matches.
- **Name-map test:** every ESPN `displayName` seen in the cached snapshot maps to
  exactly one canonical roster team; every roster team is reachable; unknown name
  raises.
- **Derivation tests:** W/D/L and card counting from a fixture match incl. a
  penalty-shootout knockout (draw +3 both, winner advances) and a second-yellow
  (1 yellow + 1 red).
- **End-to-end smoke:** run against the cached snapshot; assert 63 entrants in the
  ladder and that totals are integers.
- **Extraction regression:** assert all 63 extracted entrant names match the
  `Ladder` names, each entrant has exactly one ⭐ and 48 multipliers, and the
  roster is 12 groups × 4 unique teams (the checks that verified the geometry).

## Open items / decisions to validate

- **Penalty & knockout fields**: no knockout matches exist in the feed yet
  (group stage). The `shootoutScore` / penalty detection and KO stage slugs must
  be re-validated once knockouts begin; covered by the override hook in the
  interim.
- **Group-winner tiebreakers** beyond points→GD→GF (e.g. head-to-head, fair
  play, drawing of lots) are flagged for manual override rather than implemented.

## Defaults locked in

- Penalty-decided knockout = draw (+3) both teams; winner gets next-stage bonus.
- Group tiebreak: points → GD → GF; ties flagged for override.
- Second yellow = one yellow + one red.
- Output: console + CSV + Markdown.
- Repo location: `/Users/robbiebaskin/Documents/personal/dev/drez`; the workbook
  is copied into the repo so the tool is self-contained. Scratch JSON left in
  `~/Downloads` during research will be removed.
