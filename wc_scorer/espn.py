# wc_scorer/espn.py
"""Fetch and parse the unofficial ESPN FIFA World Cup scoreboard feed."""
import json
import os
import subprocess
import urllib.error
import urllib.request

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
DEFAULT_DATES = "20260611-20260719"


def _url(dates: str) -> str:
    return f"{BASE}?dates={dates}&limit=300"


def _http_get(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError:
        # macOS Homebrew Python can lack CA certs; curl is verified to work here.
        return subprocess.check_output(["curl", "-s", url], timeout=30)


def fetch(dates: str = DEFAULT_DATES, cache_dir: str = "data/cache",
          refresh: bool = False) -> dict:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"espn-{dates}.json")
    if refresh or not os.path.exists(path):
        data = _http_get(_url(dates))
        with open(path, "wb") as f:
            f.write(data)
    with open(path, "rb") as f:
        return json.load(f)


def team_names(raw: dict) -> set[str]:
    names = set()
    for event in raw.get("events", []):
        for comp in event.get("competitions", []):
            for c in comp.get("competitors", []):
                dn = c.get("team", {}).get("displayName")
                if dn:
                    names.add(dn)
    return names


import re as _re
from .teams import to_canonical


def stage_of(event: dict) -> str:
    text = (event.get("season", {}).get("slug", "") or "").lower()
    for comp in event.get("competitions", []):
        for note in comp.get("notes", []) or []:
            text += " " + (note.get("headline", "") or "").lower()
    if _re.search(r"third|3rd", text):
        return "third"
    if "32" in text:
        return "r32"
    if "16" in text:
        return "r16"
    if "quarter" in text:
        return "qf"
    if "semi" in text:
        return "sf"
    if "group" in text:
        return "group"
    if "final" in text:
        return "final"
    return "other"


def _int(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def parse(raw: dict, name_map: dict) -> list:
    matches = []
    for event in raw.get("events", []):
        stage = stage_of(event)
        for comp in event.get("competitions", []):
            cs = comp.get("competitors", [])
            if len(cs) != 2:
                continue
            try:
                names = [to_canonical(c["team"]["displayName"], name_map) for c in cs]
            except KeyError:
                # Skip placeholder/TBD fixtures (not-yet-played knockouts).
                continue
            id_to_team = {c.get("team", {}).get("id"): n for c, n in zip(cs, names)}
            goals = [_int(c.get("score")) for c in cs]
            shootout = [c.get("shootoutScore") for c in cs]
            completed = bool(comp.get("status", {}).get("type", {}).get("completed"))
            penalties = all(s not in (None, "") for s in shootout)
            shootout_winner = None
            if penalties:
                hi = 0 if _int(shootout[0]) >= _int(shootout[1]) else 1
                shootout_winner = names[hi]
            cards = {n: {"yellow": 0, "red": 0} for n in names}
            for d in comp.get("details", []) or []:
                ttext = (d.get("type", {}).get("text") or "").lower()
                tid = d.get("team", {}).get("id")
                team = id_to_team.get(tid)
                if not team:
                    continue
                if "yellow" in ttext and "red" in ttext:   # second yellow
                    cards[team]["yellow"] += 1
                    cards[team]["red"] += 1
                elif "yellow" in ttext:
                    cards[team]["yellow"] += 1
                elif "red" in ttext:
                    cards[team]["red"] += 1
            matches.append({
                "stage": stage,
                "team_a": names[0], "team_b": names[1],
                "ga": goals[0], "gb": goals[1],
                "completed": completed,
                "penalties": penalties,
                "shootout_winner": shootout_winner,
                "cards": cards,
            })
    return matches
