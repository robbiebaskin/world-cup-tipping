# wc_scorer/report.py
import csv
import os

_BREAKDOWN_COLS = ["win", "draw", "loss", "gf", "ga", "yellow", "red",
                   "group_winner", "qualify", "r16", "qf", "sf", "final", "winner"]


def ladder(results: list) -> list:
    return sorted(results, key=lambda r: (-r["total"], r["name"]))


def render_ladder(results: list) -> str:
    lines = ["Rank  Total  Star            Name",
             "----  -----  --------------  --------------------"]
    for i, r in enumerate(ladder(results), 1):
        lines.append(f"{i:>4}  {r['total']:>5}  {r['star'][:14]:<14}  {r['name']}")
    return "\n".join(lines)


def render_breakdown(result: dict, team_group: dict) -> str:
    lines = [f"\n{result['name']}  —  total {result['total']}  (★ {result['star']})",
             f"  {'Country':<16}{'Grp':<4}{'x':<3}{'Pts':>5}   detail"]
    rows = sorted(result["by_country"].items(), key=lambda kv: -kv[1]["points"])
    for team, info in rows:
        detail = ", ".join(f"{k}:{v}" for k, v in info["components"].items())
        grp = team_group.get(team, "?")
        lines.append(f"  {team:<16}{grp:<4}{info['multiplier']:<3}{info['points']:>5}   {detail}")
    return "\n".join(lines)


def write_csv(results: list, team_group: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "ladder.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "name", "star", "total"])
        for i, r in enumerate(ladder(results), 1):
            w.writerow([i, r["name"], r["star"], r["total"]])
    with open(os.path.join(out_dir, "breakdown.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entrant", "country", "group", "multiplier"] + _BREAKDOWN_COLS + ["points"])
        for r in ladder(results):
            for team, info in sorted(r["by_country"].items(), key=lambda kv: -kv[1]["points"]):
                comps = info["components"]
                w.writerow([r["name"], team, team_group.get(team, "?"), info["multiplier"]]
                           + [comps.get(c, 0) for c in _BREAKDOWN_COLS] + [info["points"]])


def write_markdown(results: list, team_group: dict, out_path: str) -> None:
    parts = ["# World Cup Tipping — Standings\n", "## Ladder\n",
             "| Rank | Name | ★ | Total |", "|---:|---|---|---:|"]
    for i, r in enumerate(ladder(results), 1):
        parts.append(f"| {i} | {r['name']} | {r['star']} | {r['total']} |")
    parts.append("\n## Breakdowns\n")
    for r in ladder(results):
        parts.append(f"### {r['name']} — {r['total']} (★ {r['star']})\n")
        parts.append("| Country | Grp | × | Points |")
        parts.append("|---|---|---:|---:|")
        for team, info in sorted(r["by_country"].items(), key=lambda kv: -kv[1]["points"]):
            parts.append(f"| {team} | {team_group.get(team, '?')} | {info['multiplier']} | {info['points']} |")
        parts.append("")
    with open(out_path, "w") as f:
        f.write("\n".join(parts))
