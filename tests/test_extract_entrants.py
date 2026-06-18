# tests/test_extract_entrants.py
import unittest
from wc_scorer.xlsx_reader import read_sheet
from wc_scorer.extract import extract_roster, extract_entrants

class TestEntrants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        xlsx = "World Cup Tipping 2026.xlsx"
        roster = extract_roster(read_sheet(xlsx, "Results"))
        cls.entrants = extract_entrants(read_sheet(xlsx, "Entries"), roster)
        cls.by_name = {e["name"]: e for e in cls.entrants}

    def test_count(self):
        self.assertEqual(len(self.entrants), 63)

    def test_each_has_one_star_and_48_multipliers(self):
        for e in self.entrants:
            stars = [t for t, m in e["multipliers"].items() if m == 5]
            self.assertEqual(len(stars), 1, e["name"])
            self.assertEqual(e["starred_team"], stars[0], e["name"])
            self.assertEqual(len(e["multipliers"]), 48, e["name"])

    def test_known_entrants(self):
        # From the workbook grid (NOT the hand-typed Ladder label).
        self.assertEqual(self.by_name["Lennon Dresner (P)"]["starred_team"], "Brazil")
        # Luka's grid stars France at x5 even though Ladder!C says "Spain".
        self.assertEqual(self.by_name["Luka Obradovic"]["starred_team"], "France")

if __name__ == "__main__":
    unittest.main()
