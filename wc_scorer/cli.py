# wc_scorer/cli.py
import argparse
import json
import os
import sys

from . import espn, extract, rankings, report, scoring, teams


def compute(ref_dir, dates, refresh, cache_dir, overrides_path):
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
    return results, warnings


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

    args = p.parse_args(argv)
    return args.func(args)
