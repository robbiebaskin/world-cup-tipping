# wc_scorer/scoring.py
"""Layer 1 (team performance points) and Layer 2 (per-entrant scoring)."""

_STAT_KEYS = ["win", "draw", "loss", "gf", "ga", "yellow", "red",
              "group_winner", "qualify", "r16", "qf", "sf", "final", "winner"]
_STAGE_MILESTONE = {"r32": "qualify", "r16": "r16", "qf": "qf", "sf": "sf", "final": "final"}


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
    table = {t: {"pts": 0, "gd": 0, "gf": 0, "gp": 0} for t in teams_all}  # group standings
    warnings = []

    for mt in matches:
        if not mt["completed"]:
            continue
        a, b = mt["team_a"], mt["team_b"]
        if a not in stats or b not in stats:
            continue
        if mt["stage"] == "other":
            # Stage couldn't be classified — surface it loudly rather than silently
            # dropping any milestone (e.g. if ESPN renames a knockout slug).
            warnings.append(f"unclassified stage for completed match: {a} vs {b}")
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
            table[a]["gp"] += 1; table[b]["gp"] += 1
            table[a]["gf"] += ga; table[a]["gd"] += ga - gb
            table[b]["gf"] += gb; table[b]["gd"] += gb - ga
            if ga == gb:
                table[a]["pts"] += 1; table[b]["pts"] += 1
            else:
                table[win]["pts"] += 3

    forced = overrides.get("force_group_winner", {})
    # Manual group-winner overrides apply immediately.
    for g, winner in forced.items():
        for t in roster.get(g, []):
            stats[t]["group_winner"] = 1 if t == winner else 0

    # Group winner and qualify are awarded only once the ENTIRE group stage is
    # complete (every team has played all its group games) — never to a mid-stage
    # leader, and qualify needs the cross-group best-third ranking. (R32 appearance
    # below also credits qualify, as a ground-truth reinforcement once drawn.)
    stage_done = all(all(table[t]["gp"] >= len(ts) - 1 for t in ts) for ts in roster.values())
    if stage_done:
        key = lambda t: (table[t]["pts"], table[t]["gd"], table[t]["gf"])
        thirds = []
        for g, ts in roster.items():
            ranked = sorted(ts, key=key, reverse=True)
            for t in ranked[:2]:                      # top two of each group qualify
                stats[t]["qualify"] = 1
            thirds.append(ranked[2])
            if g not in forced:
                if key(ranked[0]) == key(ranked[1]):
                    warnings.append(f"group {g}: tie for winner between {ranked[0]} and {ranked[1]}")
                else:
                    stats[ranked[0]]["group_winner"] = 1
        thirds.sort(key=key, reverse=True)            # 8 best third-placed teams qualify
        for t in thirds[:8]:
            stats[t]["qualify"] = 1
        if len(thirds) > 8 and key(thirds[7]) == key(thirds[8]):
            warnings.append(f"best-third qualify cutoff tie (verify): {thirds[7]} vs {thirds[8]}")

    # The workbook's "Round of 32 Qual (2)" bonus EXCLUDES group winners (col J header
    # "(Exc GW)"): a group winner earns the +5 group-winner bonus instead, never the +2
    # qualify bonus. Enforce after winners are finalized — covers both the top-two qualify
    # path above and the R32-appearance qualify path in the match loop.
    for t in teams_all:
        if stats[t]["group_winner"]:
            stats[t]["qualify"] = 0

    for team, patch in overrides.get("patch", {}).items():
        if team in stats:
            stats[team].update(patch)

    # `adjust` applies additive deltas (e.g. correcting an ESPN card miscount against the
    # authoritative workbook). Unlike `patch`'s absolute set, a delta survives later matches.
    for team, delta in overrides.get("adjust", {}).items():
        if team in stats:
            for k, v in delta.items():
                stats[team][k] = stats[team].get(k, 0) + v

    stats["_warnings"] = warnings
    return stats


WEIGHTS = {
    "win": 5, "draw": 3, "loss": 0, "gf": 2, "ga": -1, "yellow": -1, "red": -5,
    "group_winner": 5, "qualify": 2, "r16": 5, "qf": 10, "sf": 15, "final": 20, "winner": 30,
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
        components = {k: v for k in WEIGHTS if (v := mult * WEIGHTS[k] * stats.get(k, 0))}
        points = mult * team_points(stats)
        by_country[team] = {"multiplier": mult, "components": components, "points": points}
        total += points
    return {"name": entrant["name"], "star": entrant["starred_team"],
            "total": total, "by_country": by_country}


def score_all(entrants: list, stats_map: dict) -> list:
    return [score_entrant(e, stats_map) for e in entrants]
