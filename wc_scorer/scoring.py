# wc_scorer/scoring.py
"""Layer 1 (team performance points) and Layer 2 (per-entrant scoring)."""

_STAT_KEYS = ["win", "draw", "loss", "gf", "ga", "yellow", "red",
              "group_winner", "qualify", "qf", "sf", "final", "winner"]
_STAGE_MILESTONE = {"r32": "qualify", "qf": "qf", "sf": "sf", "final": "final"}


def empty_stats() -> dict:
    return {k: 0 for k in _STAT_KEYS}


def _winner_of(match: dict):
    if match["penalties"]:
        return None  # scored as a draw; advancement handled separately
    if match["ga"] > match["gb"]:
        return match["team_a"]
    if match["gb"] > match["ga"]:
        return match["team_b"]
    return None


def team_stats(matches: list, roster: dict, overrides: dict = None) -> dict:
    overrides = overrides or {}
    teams_all = [t for ts in roster.values() for t in ts]
    stats = {t: empty_stats() for t in teams_all}
    table = {t: {"pts": 0, "gd": 0, "gf": 0} for t in teams_all}  # group standings

    for mt in matches:
        if not mt["completed"]:
            continue
        a, b = mt["team_a"], mt["team_b"]
        if a not in stats or b not in stats:
            continue
        ga, gb = mt["ga"], mt["gb"]
        stats[a]["gf"] += ga; stats[a]["ga"] += gb
        stats[b]["gf"] += gb; stats[b]["ga"] += ga
        for team in (a, b):
            stats[team]["yellow"] += mt["cards"].get(team, {}).get("yellow", 0)
            stats[team]["red"] += mt["cards"].get(team, {}).get("red", 0)

        win = _winner_of(mt)
        if mt["penalties"] or ga == gb:
            stats[a]["draw"] += 1; stats[b]["draw"] += 1
        else:
            loser = b if win == a else a
            stats[win]["win"] += 1; stats[loser]["loss"] += 1

        # milestones from knockout stage appearance
        ms = _STAGE_MILESTONE.get(mt["stage"])
        if ms:
            stats[a][ms] = 1; stats[b][ms] = 1
        if mt["stage"] == "final":
            champ = mt["shootout_winner"] or win
            if champ:
                stats[champ]["winner"] = 1

        # group standings (group stage only)
        if mt["stage"] == "group":
            table[a]["gf"] += ga; table[a]["gd"] += ga - gb
            table[b]["gf"] += gb; table[b]["gd"] += gb - ga
            if ga == gb:
                table[a]["pts"] += 1; table[b]["pts"] += 1
            else:
                table[win]["pts"] += 3

    warnings = []
    forced = overrides.get("force_group_winner", {})
    for g, ts in roster.items():
        if g in forced:
            for t in ts:
                stats[t]["group_winner"] = 1 if t == forced[g] else 0
            continue
        ranked = sorted(ts, key=lambda t: (table[t]["pts"], table[t]["gd"], table[t]["gf"]),
                        reverse=True)
        top, second = ranked[0], ranked[1]
        tie = (table[top]["pts"], table[top]["gd"], table[top]["gf"]) == \
              (table[second]["pts"], table[second]["gd"], table[second]["gf"])
        # only award once the group has actually played; tie -> warn, no award
        played = any(table[t]["pts"] or stats[t]["gf"] or stats[t]["ga"] for t in ts)
        if played and not tie:
            stats[top]["group_winner"] = 1
        elif played and tie:
            warnings.append(f"group {g}: tie for winner between {top} and {second}")

    for team, patch in overrides.get("patch", {}).items():
        if team in stats:
            stats[team].update(patch)

    stats["_warnings"] = warnings
    return stats


WEIGHTS = {
    "win": 5, "draw": 3, "loss": 0, "gf": 2, "ga": -1, "yellow": -1, "red": -5,
    "group_winner": 5, "qualify": 2, "qf": 10, "sf": 15, "final": 20, "winner": 30,
}


def team_points(stats: dict) -> int:
    return sum(WEIGHTS[k] * stats.get(k, 0) for k in WEIGHTS)


def score_entrant(entrant: dict, stats_map: dict) -> dict:
    by_country = {}
    total = 0
    for team, mult in entrant["multipliers"].items():
        if mult <= 0:
            continue
        stats = stats_map.get(team) or empty_stats()
        components = {k: mult * WEIGHTS[k] * stats.get(k, 0)
                      for k in WEIGHTS if stats.get(k, 0)}
        points = mult * team_points(stats)
        by_country[team] = {"multiplier": mult, "components": components, "points": points}
        total += points
    return {"name": entrant["name"], "star": entrant["starred_team"],
            "total": total, "by_country": by_country}


def score_all(entrants: list, stats_map: dict) -> list:
    return [score_entrant(e, stats_map) for e in entrants]
