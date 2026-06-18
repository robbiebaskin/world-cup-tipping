# tests/test_extract_run.py
import unittest, os, json, tempfile
from wc_scorer import espn
from wc_scorer.extract import extract

class TestExtractRun(unittest.TestCase):
    def test_writes_valid_reference_files(self):
        names = espn.team_names(espn.fetch(cache_dir="data/cache"))
        with tempfile.TemporaryDirectory() as d:
            summary = extract("World Cup Tipping 2026.xlsx", out_dir=d,
                              espn_names=names, now="2026-06-18T00:00:00")
            roster = json.load(open(os.path.join(d, "roster.json")))
            entrants = json.load(open(os.path.join(d, "entrants.json")))
            name_map = json.load(open(os.path.join(d, "name_map.json")))
            self.assertEqual(len([t for g in roster["groups"].values() for t in g]), 48)
            self.assertEqual(len(entrants["entrants"]), 63)
            self.assertEqual(name_map["map"]["South Korea"], "Korea Rep.")
            self.assertEqual(summary["exceptions"], [])  # all feed names resolved
            self.assertIn("_meta", roster)

if __name__ == "__main__":
    unittest.main()
