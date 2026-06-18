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

## Web UI (mobile-first)

A static frontend in `web/` shows the leaderboard, a find-your-name search, and a
tap-to-expand per-person breakdown (per country × scoring metric), plus fixtures
and a scoring-rules reference. It reads a single JSON file the scorer produces —
it never re-implements scoring.

```bash
# Build web/data.json from the current results
python3 -m wc_scorer export

# Export, then serve web/ at http://localhost:8137 (Ctrl-C to stop)
python3 -m wc_scorer serve            # add --port NNNN to change the port
```

Open the printed URL on your phone (same Wi-Fi) or in a browser. Opening
`web/index.html` directly via `file://` won't work — the page fetches
`data.json`, which needs an http server.

### Keeping it fresh automatically

`wc_scorer refresh` regenerates `web/data.json` only when it's worth it: it pulls
live results while a match is on (within the kickoff window or live) and at most
every ~2 h otherwise — decided from the kickoff times the ESPN feed already
carries (`wc_scorer/schedule.py`). Wire it to a 5-minute cron and the cadence
sorts itself out:

```bash
bash scripts/refresh-cron.sh install     # add the every-5-min cron job
bash scripts/refresh-cron.sh status      # show it
bash scripts/refresh-cron.sh uninstall   # remove it
```

Tunable: `--pre-min`, `--post-min` (match window) and `--max-age-min` (idle
cadence) on `wc_scorer refresh`.

## Deploy online (GitHub Pages — free)

`.github/workflows/deploy.yml` rebuilds `web/data.json` from live results and
publishes `web/` to GitHub Pages on every push, manually, and every ~5 minutes
on a schedule (best-effort — GitHub often delays high-frequency schedules). CI does the refresh itself (the scorer needs only the committed
`data/reference/*.json` + the public ESPN feed), so nothing has to run on your
machine. One-time setup:

1. Push this repo to GitHub. Use a **public** repo — Pages + Actions are free
   and unlimited there.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. Trigger once: **Actions → refresh-and-deploy → Run workflow** (or just push).
   The site goes live at `https://<user>.github.io/<repo>/`.

Notes:
- **Privacy:** a public repo exposes players' real names and the workbook. The
  leaderboard is public anyway, but if the *source* must stay private, deploy
  with **Cloudflare Pages** (free, builds from a private repo; its free tier caps
  ~500 builds/month, so refresh less often) or **GitHub Pro** ($4/mo for Pages
  from a private repo).
- Scheduled runs are best-effort and **auto-pause after 60 days of repo
  inactivity** — fine for a month-long tournament; push or re-run to wake them.
- The adaptive `wc_scorer refresh` throttle is for the local cron above; on CI
  each run is a fresh checkout with no cache to age, so the workflow just runs
  `export --refresh` on a fixed schedule.

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
