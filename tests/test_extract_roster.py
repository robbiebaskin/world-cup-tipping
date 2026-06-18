# tests/test_extract_roster.py
import unittest
from wc_scorer.xlsx_reader import read_sheet
from wc_scorer.extract import extract_roster

class TestRoster(unittest.TestCase):
    def setUp(self):
        self.roster = extract_roster(read_sheet("World Cup Tipping 2026.xlsx", "Results"))

    def test_twelve_groups_of_four(self):
        self.assertEqual(sorted(self.roster), list("ABCDEFGHIJKL"))
        for g, teams in self.roster.items():
            self.assertEqual(len(teams), 4, g)

    def test_48_unique_teams(self):
        flat = [t for ts in self.roster.values() for t in ts]
        self.assertEqual(len(flat), 48)
        self.assertEqual(len(set(flat)), 48)

    def test_known_members(self):
        self.assertEqual(self.roster["A"], ["Mexico", "South Africa", "Korea Rep.", "Czechia"])
        self.assertIn("Uzebekistan", self.roster["K"])  # workbook's spelling

if __name__ == "__main__":
    unittest.main()
