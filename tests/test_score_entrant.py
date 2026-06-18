# tests/test_score_entrant.py
import unittest
from wc_scorer.scoring import score_entrant, empty_stats

class TestScoreEntrant(unittest.TestCase):
    def test_breakdown_and_total(self):
        mex = empty_stats(); mex.update(win=1, gf=2)          # points = 5 + 4 = 9
        bra = empty_stats(); bra.update(draw=1)               # points = 3
        stats = {"Mexico": mex, "Brazil": bra, "Haiti": empty_stats()}
        entrant = {"name": "Tester", "starred_team": "Mexico",
                   "multipliers": {"Mexico": 5, "Brazil": 3, "Haiti": 0}}
        r = score_entrant(entrant, stats)
        self.assertEqual(r["by_country"]["Mexico"]["points"], 45)   # 5 * 9
        self.assertEqual(r["by_country"]["Mexico"]["components"]["win"], 25)  # 5*5*1
        self.assertEqual(r["by_country"]["Mexico"]["components"]["gf"], 20)   # 5*2*2
        self.assertEqual(r["by_country"]["Brazil"]["points"], 9)    # 3 * 3
        self.assertNotIn("Haiti", r["by_country"])                  # mult 0 excluded
        self.assertEqual(r["total"], 54)

if __name__ == "__main__":
    unittest.main()
