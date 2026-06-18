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
