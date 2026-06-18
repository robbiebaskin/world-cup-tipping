import json
import os


def load_roster(ref_dir: str = "data/reference") -> dict:
    with open(os.path.join(ref_dir, "roster.json")) as f:
        return json.load(f)["groups"]


def team_group(roster: dict) -> dict:
    return {t: g for g, ts in roster.items() for t in ts}


def load_name_map(ref_dir: str = "data/reference") -> dict:
    with open(os.path.join(ref_dir, "name_map.json")) as f:
        return json.load(f)["map"]


def to_canonical(name: str, name_map: dict) -> str:
    if name not in name_map:
        raise KeyError(f"unmapped ESPN team name: {name!r}")
    return name_map[name]
