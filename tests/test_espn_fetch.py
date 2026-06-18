# tests/test_espn_fetch.py
import unittest, os, json
from wc_scorer import espn

class TestFetch(unittest.TestCase):
    def test_fetch_caches_and_reads_back(self):
        raw = espn.fetch(cache_dir="data/cache")            # network or cache
        self.assertIn("events", raw)
        self.assertTrue(len(raw["events"]) >= 20)
        cached = [f for f in os.listdir("data/cache") if f.endswith(".json")]
        self.assertTrue(cached, "expected a cache file to be written")
        raw2 = espn.fetch(cache_dir="data/cache", refresh=False)  # from cache
        self.assertEqual(len(raw["events"]), len(raw2["events"]))

    def test_team_names_includes_real_and_placeholders(self):
        raw = espn.fetch(cache_dir="data/cache")
        names = espn.team_names(raw)
        self.assertIn("Mexico", names)
        self.assertIn("South Korea", names)

if __name__ == "__main__":
    unittest.main()
