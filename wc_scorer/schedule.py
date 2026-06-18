# wc_scorer/schedule.py
"""Decide when to refresh the live feed, from the schedule the feed itself carries.

The ESPN scoreboard feed lists every fixture with a kickoff time (`date`) and a
live state (`status.type.state`: pre/in/post). A cron fires this every 5 minutes;
`should_refresh` throttles the actual network pull to ~5 min during matches and
~`max_age_min` otherwise. No hardcoded fixture list — it stays correct as rounds
advance.
"""
from datetime import datetime, timedelta


def _parse(date: str) -> datetime:
    s = date.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def kickoffs(raw: dict) -> list:
    """Return [(kickoff_utc, state), ...] for every fixture in the feed."""
    out = []
    for ev in raw.get("events", []):
        date = ev.get("date")
        if not date:
            continue
        try:
            ko = _parse(date)
        except ValueError:
            continue
        state = ""
        for comp in ev.get("competitions", []):
            state = (comp.get("status", {}).get("type", {}).get("state") or "").lower()
            if state:
                break
        out.append((ko, state))
    return out


def should_refresh(raw: dict, now: datetime, cache_mtime, pre_min: int = 10,
                   post_min: int = 165, max_age_min: int = 120):
    """Return (refresh?, reason). Refresh if a match is on or the cache is stale."""
    kos = kickoffs(raw)
    if any(state == "in" for _, state in kos):
        return True, "match in progress"
    pre, post = timedelta(minutes=pre_min), timedelta(minutes=post_min)
    if any(ko - pre <= now <= ko + post for ko, _ in kos):
        return True, "within a match window"
    if cache_mtime is None:
        return True, "no cached feed yet"
    age_min = int((now - cache_mtime).total_seconds() // 60)
    if age_min >= max_age_min:
        return True, f"cache stale ({age_min} min old)"
    return False, f"no match on, cache fresh ({age_min} min old)"
