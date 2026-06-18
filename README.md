# World Cup 2026 Tipping Scorer

Scores the family World Cup tipping competition from live results.

## Usage

```bash
# One-off (or whenever the workbook changes): build reference data from the .xlsx
python3 -m wc_scorer extract

# Score using the latest results (re-fetches the live feed)
python3 -m wc_scorer score --refresh
```

Outputs the ladder + a per-country breakdown for every entrant to the console,
and writes `out/ladder.csv`, `out/breakdown.csv`, `out/report.md`.

## How scoring works

Two layers, reproducing the original workbook exactly:
1. Each team earns performance points: win 5, draw 3 (incl. penalty games),
   goals-for 2, goals-against −1, yellow −1, red −5, group winner 5, qualify 2,
   QF 10, SF 15, final 20, winner 30.
2. Each entrant multiplies each backed team's points by their rank (★ 5, 1st ×3,
   2nd ×2, 3rd ×1, unranked ×0).

## Data sources

- Rankings/roster: extracted by code from `World Cup Tipping 2026.xlsx` into
  `data/reference/*.json` (never hand-typed).
- Live results: ESPN unofficial scoreboard API, cached under `data/cache/`.

## Manual overrides

Edit `data/overrides.json` to force a group winner (tiebreaker edge cases) or
patch a team's stats if the feed is wrong. Group-winner ties print a WARNING.

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
