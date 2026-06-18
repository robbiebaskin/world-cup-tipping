# tests/test_report.py
import unittest, os, tempfile
from wc_scorer import report

RESULTS = [
    {"name": "Beth", "star": "Brazil", "total": 50,
     "by_country": {"Brazil": {"multiplier": 5, "components": {"win": 25}, "points": 25}}},
    {"name": "Al", "star": "Spain", "total": 90,
     "by_country": {"Spain": {"multiplier": 5, "components": {"win": 25}, "points": 25}}},
]
TEAM_GROUP = {"Brazil": "C", "Spain": "H"}

class TestReport(unittest.TestCase):
    def test_ladder_sorted_desc(self):
        rows = report.ladder(RESULTS)
        self.assertEqual([r["name"] for r in rows], ["Al", "Beth"])

    def test_render_ladder_contains_rank(self):
        text = report.render_ladder(RESULTS)
        self.assertIn("Al", text)
        self.assertIn("90", text)

    def test_write_csv_and_md(self):
        with tempfile.TemporaryDirectory() as d:
            report.write_csv(RESULTS, TEAM_GROUP, d)
            report.write_markdown(RESULTS, TEAM_GROUP, os.path.join(d, "report.md"))
            self.assertTrue(os.path.exists(os.path.join(d, "ladder.csv")))
            self.assertTrue(os.path.exists(os.path.join(d, "breakdown.csv")))
            self.assertTrue(os.path.exists(os.path.join(d, "report.md")))
            with open(os.path.join(d, "breakdown.csv")) as f:
                self.assertIn("multiplier", f.readline())

if __name__ == "__main__":
    unittest.main()
