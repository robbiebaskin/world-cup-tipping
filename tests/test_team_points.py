# tests/test_team_points.py
import re
import unittest
from wc_scorer.xlsx_reader import read_sheet
from wc_scorer.scoring import WEIGHTS, team_points, empty_stats

# Column letters in Results!P formula -> our stat keys.
COL_TO_STAT = {"B": "win", "C": "draw", "D": "loss", "E": "gf", "F": "ga",
               "G": "yellow", "H": "red", "I": "group_winner", "J": "qualify",
               "K": "r16", "L": "qf", "M": "sf", "N": "final", "O": "winner"}

class TestGoldenPoints(unittest.TestCase):
    def test_weights_match_workbook_formula(self):
        formula = read_sheet("World Cup Tipping 2026.xlsx", "Results")["P3"]["formula"]
        # e.g. (B3*5)+(C3*3)+...+(F3*-1)+...
        found = {}
        for col, coef in re.findall(r"\(([A-Z])3\*(-?\d+)\)", formula):
            found[COL_TO_STAT[col]] = int(coef)
        self.assertEqual(found, WEIGHTS)

    def test_team_points_one_hot(self):
        for key, weight in WEIGHTS.items():
            s = empty_stats(); s[key] = 1
            self.assertEqual(team_points(s), weight, key)

    def test_team_points_realistic(self):
        s = empty_stats()
        s.update(win=2, draw=1, gf=5, ga=2, yellow=3, red=1, group_winner=1, qualify=1)
        # 2*5 + 1*3 + 5*2 + 2*-1 + 3*-1 + 1*-5 + 1*5 + 1*2 = 10+3+10-2-3-5+5+2 = 20
        self.assertEqual(team_points(s), 20)

if __name__ == "__main__":
    unittest.main()
