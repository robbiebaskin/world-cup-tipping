# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`wc_scorer` scores a 63-entrant World Cup 2026 tipping competition. Entrants ranked teams within the 12 groups before the tournament (fixed data, held in an Excel workbook); the tool pulls live match results and reproduces the workbook's scoring, producing a ladder plus a per-country breakdown of every entrant's score.

## Commands

No build step and **no dependencies** — pure Python 3 standard library. Do not add third-party packages (see Hard constraints).

```bash
# Run the whole test suite (unittest, not pytest)
python3 -m unittest discover -s tests -p "test_*.py"

# Run one test module / class / method
python3 -m unittest tests.test_team_points
python3 -m unittest tests.test_team_points.TestGoldenPoints.test_weights_match_workbook_formula

# Enforce pristine output (the suite must pass cleanly under this)
python3 -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py"

# Rebuild reference JSON from the workbook (rare — only when the .xlsx changes)
python3 -m wc_scorer extract

# Score from the live feed and write out/ladder.csv, out/breakdown.csv, out/report.md
python3 -m wc_scorer score --refresh

# Build web/data.json for the web UI (add --refresh to pull live first)
python3 -m wc_scorer export
# Export, then serve web/ over http (default :8137; sends Cache-Control: no-store)
python3 -m wc_scorer serve
# Refresh web/data.json only if a match is on or the cache is >2h stale (cron-friendly)
python3 -m wc_scorer refresh
```

Always run commands from the repo root so `from wc_scorer import ...` resolves. Warnings from `score` (e.g. group-winner ties) go to **stderr**; the report goes to stdout.

## Architecture

Two distinct phases, deliberately separated:

- **Extract (rare):** `extract.py` is the *only* code that reads the binary workbook (`World Cup Tipping 2026.xlsx`). It writes three committed, diff-able JSON files to `data/reference/` — `roster.json` (12 groups × 4 teams), `entrants.json` (63 entrants + rank multipliers), `name_map.json` (ESPN name → canonical roster name). It validates invariants and raises before writing.
- **Score (normal run):** reads only `data/reference/*.json` + the cached ESPN feed. Never touches the `.xlsx`.

Scoring data flow (and the module that owns each step):

```
.xlsx ──extract.py──> data/reference/*.json
ESPN API ──espn.fetch (cached to data/cache/)──> espn.parse ──> match records
match records + roster ──scoring.team_stats──> per-team stats (+ "_warnings")
                          scoring.team_points──> per-team points  (Layer 1)
entrants × team points ──scoring.score_all──> per-entrant total + by_country  (Layer 2)
                          report.py──> ladder + breakdown (console / CSV / Markdown)
                          webexport.build_payload──> web/data.json ──> web/ static UI (no build)
cli.py / __main__.py wires it together (subcommands: extract, score, export, serve, refresh)
```

**Two-layer scoring** is the core model. Layer 1: each team earns performance points (win 5, draw 3 incl. penalty games, GF 2, GA −1, yellow −1, red −5, group-winner 5, qualify 2 **excluding group winners**, R16 5, QF 10, SF 15, final 20, winner 30). Layer 2: each entrant multiplies each backed team's points by their rank (⭐ 5, 1st ×3, 2nd ×2, 3rd ×1, unranked ×0) — `WEIGHTS` and `score_entrant` in `scoring.py`.

Loaders (`teams.py`, `rankings.py`) are the runtime read path for the reference JSON. `teams.to_canonical` raises on an unmapped name (never silently drops).

## Hard constraints (these are load-bearing — verify before changing)

- **Standard library only.** `openpyxl` and `pytest` are broken/absent in this environment, and `xml.etree`/`expat` is broken — so `xlsx_reader.py` parses the `.xlsx` (a zip of XML) with regex. It **must** handle self-closing cells (`<c r=".." />`); a regex assuming every `<c>` has a `</c>` silently swallows following cells and drops data (this bug was hit and fixed).
- **Canonical team names come from `roster.json`** — they use the workbook's exact spellings, including quirks like `Korea Rep.` (trailing period) and `Uzebekistan` (misspelling). Never hand-type team names; join by position/canonical name.
- **The ⭐ star is the team with grid multiplier 5**, not the workbook's `Ladder!C` "* Selected" label (which is hand-typed and has at least one known error).
- **Scoring weights are golden-tested** against the workbook's literal `Results!O3` formula (`tests/test_team_points.py`). Do not change `WEIGHTS` without re-confirming against the workbook — a mismatch there is a real discrepancy, not a test to loosen.
- **Verify the full pipeline against the workbook:** per-team stats + points must match the `Results` sheet (cols B–N stats, O points) and per-entrant totals must match the `Ladder` sheet (B=Name, C=Total Points) exactly. A mismatch is an algo bug or stale reference data (re-extract if a newer `.xlsx` is provided) — not a test to loosen.
- **Invariants:** 63 entrants; 48 teams in 12 groups of 4; each entrant has exactly one ⭐ and 48 multipliers. The extractor enforces these.
- **ESPN feed:** unknown team name in the feed = hard error; knockout-fixture placeholders (e.g. "Group A 2nd Place", "Third Place Group A") are filtered. `espn.fetch` uses `urllib` with a `curl` fallback (macOS Homebrew Python can lack CA certs) and caches every pull to `data/cache/` (gitignored).
- **ESPN card parsing keys off the detail-type *text* — match precisely.** Require `"card" in type` before counting yellow/red, or non-card details leak in (e.g. `"Penalty - Scored"` contains the substring `red`; this bug was hit and fixed).
- **`team_stats` returns a `"_warnings"` key alongside team keys.** Callers must pop it before iterating teams (`cli.compute` does; `score_entrant` is safe because it iterates entrant multipliers, not stats keys).

## Edge cases and the override hook

- Penalty-decided knockout games count as a **draw for both** teams; the shootout winner still gets the next stage's milestone.
- **Group winner and `qualify` are awarded only once the *whole* group stage is complete** (every team in every group has played all its group games) — never a mid-stage leader. `qualify` = top two of each group + the 8 best third-placed teams (ranked by points, GD, GF; R32 appearance also credits it as ground-truth reinforcement). **Group winners are then excluded from the `qualify` bonus** — the workbook's col J header is "Round of 32 Qual (2) (Exc GW)": a group winner earns the +5 group-winner bonus *instead of* the +2 qualify. This is enforced as a final pass in `team_stats` after winners are decided (covers both the top-two and R32-appearance qualify paths). Winner ties (and the best-third cutoff tie) are flagged (stderr) and left unawarded for the override hook. `r16`/`qf`/`sf`/`final` are credited the moment a team **wins** the prior knockout round (winning R32 → `r16`, R16 → `qf`, QF → `sf`, SF → `final`; the shootout winner advances on penalties), via `_STAGE_ADVANCE` — a team need not wait to appear in the next round's fixture. Appearance in a round still credits that round's milestone too, as idempotent ground-truth reinforcement; the set of teams reaching each round is identical either way, so output matches the workbook for any fully-played round.
- `data/overrides.json` (`{"force_group_winner": {...}, "patch": {...}, "adjust": {...}}`) patches derived stats or forces a group winner for genuine ambiguities or feed glitches; applied after derivation. `patch` **sets** absolute stat values (`{"Team": {"yellow": 2}}`); `adjust` applies **additive deltas** (`{"Team": {"yellow": 1}}`) so a feed-glitch correction survives later matches (use this for ESPN-vs-workbook card miscounts on teams still in the tournament — an absolute `patch` would clobber their knockout cards). The workbook is authoritative: ESPN under/over-counted yellows for Morocco (+1), Haiti (−1), Turkey (−1) in the group stage, corrected via `adjust`.
- **Knockout/penalty paths are unvalidated against live data** (only the group stage has been played). They are written to ESPN's documented fields and covered by the override hook, and are flagged for re-validation when the Round of 32 begins.

## Web UI and deployment

- **`web/`** is a static, build-free frontend (`index.html`, `styles.css`, `app.js`, `flags.js`, `favicon.svg`) that fetches `web/data.json`. It is a **consumer only — never re-implement scoring in JS.** `web/data.json` is generated and gitignored; the `web/` source files are committed.
- **`webexport.build_payload`** serializes `score_all` output + `team_group` + tournament metadata to the payload. `cli._pipeline` is the shared scoring path; `compute` still returns `(results, warnings)` unchanged.
- **`schedule.should_refresh`** decides when `refresh` pulls live — from ESPN kickoff times + live state, throttled by the cache file's mtime. `scripts/refresh-cron.sh install|uninstall` manages the local 5-min cron.
- **The `matches` list excludes TBD knockout fixtures** (each record now also carries `date`), so it's < 104. Use `tournament.matches_played` / `matches_total` (104 constant) for progress counts so Standings and Fixtures agree.
- **CSS gotcha:** an element with an explicit `display:` won't hide via the `hidden` attribute — add `[hidden]{display:none}` (hit/fixed on `.pills`).
- **Deploy:** `.github/workflows/deploy.yml` runs `export --refresh` on a ~5-min (best-effort) schedule and publishes `web/` to GitHub Pages. CI uses `export --refresh` (not `refresh` — its mtime throttle doesn't survive stateless CI checkouts). First-time Pages enablement needs repo admin (a push-only token can't create the Pages site).

## Design docs

`docs/superpowers/specs/` and `docs/superpowers/plans/` hold the design spec and implementation plan — read them for the rationale behind the above.
