# tests/test_schedule.py
import unittest
from datetime import datetime, timedelta, timezone

from wc_scorer import schedule

NOW = datetime(2026, 6, 18, 20, 0, tzinfo=timezone.utc)
FRESH = NOW - timedelta(minutes=30)      # cache pulled 30 min ago
STALE = NOW - timedelta(hours=3)         # cache pulled 3 h ago


def ev(date, state="pre"):
    return {"date": date, "competitions": [{"status": {"type": {"state": state}}}]}


def feed(*events):
    return {"events": list(events)}


def decide(raw, cache_mtime=FRESH, **kw):
    return schedule.should_refresh(raw, NOW, cache_mtime, **kw)


class TestShouldRefresh(unittest.TestCase):
    def test_refresh_when_a_match_is_live(self):
        ok, _ = decide(feed(ev("2026-06-25T19:00Z", "in")))   # kickoff far off, but live
        self.assertTrue(ok)

    def test_refresh_when_now_inside_kickoff_window(self):
        ok, _ = decide(feed(ev("2026-06-18T20:00Z", "pre")))  # kicks off now
        self.assertTrue(ok)

    def test_refresh_when_cache_stale_and_no_game(self):
        ok, reason = decide(feed(ev("2026-06-25T19:00Z", "pre")), cache_mtime=STALE)
        self.assertTrue(ok)
        self.assertIn("stale", reason)

    def test_refresh_when_no_cache(self):
        ok, _ = decide(feed(ev("2026-06-25T19:00Z", "pre")), cache_mtime=None)
        self.assertTrue(ok)

    def test_skip_when_no_game_and_cache_fresh(self):
        ok, _ = decide(feed(ev("2026-06-25T19:00Z", "pre")))
        self.assertFalse(ok)

    def test_window_opens_at_pre_buffer_inclusive(self):
        # kickoff exactly pre_min ahead -> window just opened
        self.assertTrue(decide(feed(ev("2026-06-18T20:10Z", "pre")))[0])
        # one minute earlier than that -> not yet in window, cache fresh -> skip
        self.assertFalse(decide(feed(ev("2026-06-18T20:11Z", "pre")))[0])

    def test_window_closes_at_post_buffer_inclusive(self):
        # kickoff post_min behind (165 min) -> window about to close, still in
        self.assertTrue(decide(feed(ev("2026-06-18T17:15Z", "post")))[0])
        # one minute past the post buffer -> closed, cache fresh -> skip
        self.assertFalse(decide(feed(ev("2026-06-18T17:14Z", "post")))[0])


class TestKickoffs(unittest.TestCase):
    def test_parses_z_suffix_and_state(self):
        kos = schedule.kickoffs(feed(ev("2026-06-11T19:00Z", "post")))
        self.assertEqual(len(kos), 1)
        dt, state = kos[0]
        self.assertEqual(dt, datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc))
        self.assertEqual(state, "post")


if __name__ == "__main__":
    unittest.main()
