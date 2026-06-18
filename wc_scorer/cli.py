# wc_scorer/cli.py
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from . import espn, extract, rankings, report, schedule, scoring, teams, webexport


def _pipeline(ref_dir, dates, refresh, cache_dir, overrides_path):
    """Run the full scoring pipeline. Returns (results, warnings, roster, matches)."""
    roster = teams.load_roster(ref_dir)
    name_map = teams.load_name_map(ref_dir)
    entrants = rankings.load_entrants(ref_dir)
    raw = espn.fetch(dates or espn.DEFAULT_DATES, cache_dir=cache_dir, refresh=refresh)
    matches = espn.parse(raw, name_map)
    overrides = None
    if overrides_path and os.path.exists(overrides_path):
        with open(overrides_path) as f:
            overrides = json.load(f)
    stats = scoring.team_stats(matches, roster, overrides=overrides)
    warnings = stats.pop("_warnings", [])
    results = scoring.score_all(entrants, stats)
    return results, warnings, roster, matches


def compute(ref_dir, dates, refresh, cache_dir, overrides_path):
    results, warnings, _, _ = _pipeline(ref_dir, dates, refresh, cache_dir, overrides_path)
    return results, warnings


def _export(ref_dir, dates, refresh, cache_dir, overrides_path, out_path, now=None):
    """Score and write the web UI's JSON payload. Returns warnings."""
    results, warnings, roster, matches = _pipeline(ref_dir, dates, refresh, cache_dir,
                                                   overrides_path)
    now = now or datetime.now(timezone.utc).isoformat()
    payload = webexport.build_payload(results, warnings, teams.team_group(roster),
                                      roster, matches, scoring.WEIGHTS, now)
    webexport.write_json(payload, out_path)
    return payload, warnings


def run_extract(args) -> int:
    names = espn.team_names(espn.fetch(args.dates or espn.DEFAULT_DATES,
                                       cache_dir=args.cache, refresh=args.refresh))
    summary = extract.extract(args.rankings, out_dir=args.out, espn_names=names,
                              now=args.now)
    print(f"Extracted: {summary['entrants']} entrants, {summary['roster']} teams, "
          f"{summary['name_map']} name mappings.")
    if summary["exceptions"]:
        print(f"UNMAPPED ESPN NAMES (add to MANUAL_ALIASES): {summary['exceptions']}")
        return 1
    return 0


def run_score(args) -> int:
    results, warnings = compute(args.ref, args.dates, args.refresh, args.cache, args.overrides)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    tg = teams.team_group(teams.load_roster(args.ref))
    fmts = args.format.split(",")
    if "console" in fmts:
        print(report.render_ladder(results))
        for r in report.ladder(results):
            print(report.render_breakdown(r, tg))
    if "csv" in fmts:
        report.write_csv(results, tg, args.out)
    if "md" in fmts:
        report.write_markdown(results, tg, os.path.join(args.out, "report.md"))
    return 0


def run_export(args) -> int:
    payload, warnings = _export(args.ref, args.dates, args.refresh, args.cache,
                                args.overrides, args.out, now=args.now or None)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    t = payload["tournament"]
    print(f"Wrote {args.out}: {len(payload['entrants'])} entrants, "
          f"{t['matches_played']}/{t['matches_total']} matches ({t['stage']}).")
    return 0


def run_serve(args) -> int:
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class Handler(SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Cache-Control", "no-store")  # always serve the latest
            super().end_headers()

    run_export(args)
    web_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    handler = partial(Handler, directory=web_dir)
    httpd = ThreadingHTTPServer(("", args.port), handler)
    print(f"Serving {web_dir} at http://localhost:{args.port}/  (Ctrl-C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()
    return 0


def run_refresh(args) -> int:
    cache_path = os.path.join(args.cache, f"espn-{args.dates or espn.DEFAULT_DATES}.json")
    raw = espn.fetch(args.dates or espn.DEFAULT_DATES, cache_dir=args.cache, refresh=False)
    cache_mtime = None
    if os.path.exists(cache_path):
        cache_mtime = datetime.fromtimestamp(os.path.getmtime(cache_path), tz=timezone.utc)
    now = datetime.now(timezone.utc)
    do, reason = schedule.should_refresh(raw, now, cache_mtime, pre_min=args.pre_min,
                                         post_min=args.post_min, max_age_min=args.max_age_min)
    if not do:
        print(f"{now.isoformat()} skip: {reason}")
        return 0
    payload, _ = _export(args.ref, args.dates, True, args.cache, args.overrides, args.out,
                         now=now.isoformat())
    t = payload["tournament"]
    print(f"{now.isoformat()} refreshed ({reason}): "
          f"{t['matches_played']}/{t['matches_total']} matches.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="wc_scorer")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("extract", help="parse the workbook into reference JSON")
    pe.add_argument("--rankings", default="World Cup Tipping 2026.xlsx")
    pe.add_argument("--out", default="data/reference")
    pe.add_argument("--cache", default="data/cache")
    pe.add_argument("--dates", default=None)
    pe.add_argument("--now", default="")
    pe.add_argument("--refresh", action="store_true")
    pe.set_defaults(func=run_extract)

    ps = sub.add_parser("score", help="score the competition from the live feed")
    ps.add_argument("--ref", default="data/reference")
    ps.add_argument("--cache", default="data/cache")
    ps.add_argument("--dates", default=None)
    ps.add_argument("--refresh", action="store_true")
    ps.add_argument("--overrides", default="data/overrides.json")
    ps.add_argument("--format", default="console,csv,md")
    ps.add_argument("--out", default="out")
    ps.set_defaults(func=run_score)

    def add_export_args(sp, with_refresh=True):
        sp.add_argument("--ref", default="data/reference")
        sp.add_argument("--cache", default="data/cache")
        sp.add_argument("--dates", default=None)
        sp.add_argument("--overrides", default="data/overrides.json")
        sp.add_argument("--out", default="web/data.json")
        if with_refresh:
            sp.add_argument("--refresh", action="store_true")

    px = sub.add_parser("export", help="write web/data.json for the web UI")
    add_export_args(px)
    px.add_argument("--now", default="")
    px.set_defaults(func=run_export)

    pv = sub.add_parser("serve", help="export then serve the web/ UI over http")
    add_export_args(pv)
    pv.add_argument("--now", default="")
    pv.add_argument("--port", type=int, default=8137)
    pv.set_defaults(func=run_serve)

    pr = sub.add_parser("refresh",
                        help="refresh web/data.json if a match is on or the cache is stale")
    add_export_args(pr, with_refresh=False)
    pr.add_argument("--pre-min", type=int, default=10, dest="pre_min")
    pr.add_argument("--post-min", type=int, default=165, dest="post_min")
    pr.add_argument("--max-age-min", type=int, default=120, dest="max_age_min")
    pr.set_defaults(func=run_refresh)

    args = p.parse_args(argv)
    return args.func(args)
