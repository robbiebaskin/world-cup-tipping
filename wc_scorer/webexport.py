# wc_scorer/webexport.py
"""Serialize score_all output + tournament metadata to JSON for the web UI.

This module never computes scores; it shapes the scorer's output (already
multiplier-applied and signed) into a single JSON-serializable payload.
"""
import json
import os

from . import report

# 72 group + 32 knockout (R32 16 + R16 8 + QF 4 + SF 2 + 3rd 1 + final 1).
MATCHES_TOTAL = 104

# Stage progression, lowest to highest, with human labels for the UI header.
_STAGE_ORDER = ["group", "r32", "r16", "qf", "sf", "third", "final"]
_STAGE_LABEL = {
    "group": "Group stage",
    "r32": "Round of 32",
    "r16": "Round of 16",
    "qf": "Quarter-finals",
    "sf": "Semi-finals",
    "third": "Third-place play-off",
    "final": "Final",
}


def _stage_label(matches: list) -> str:
    best = -1
    for m in matches:
        stage = m.get("stage")
        if stage in _STAGE_ORDER:
            best = max(best, _STAGE_ORDER.index(stage))
    return _STAGE_LABEL[_STAGE_ORDER[best]] if best >= 0 else "Not started"


def build_payload(results: list, warnings: list, team_group: dict, roster: dict,
                  matches: list, weights: dict, now: str) -> dict:
    entrants = []
    for rank, r in enumerate(report.ladder(results), 1):
        entrants.append({
            "rank": rank,
            "name": r["name"],
            "star": r["star"],
            "total": r["total"],
            "by_country": r["by_country"],
        })
    return {
        "generated_at": now,
        "tournament": {
            "matches_played": sum(1 for m in matches if m.get("completed")),
            "matches_total": MATCHES_TOTAL,
            "stage": _stage_label(matches),
            "groups": roster,
        },
        "weights": weights,
        "team_group": team_group,
        "warnings": warnings,
        "matches": matches,
        "entrants": entrants,
    }


def write_json(payload: dict, path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
