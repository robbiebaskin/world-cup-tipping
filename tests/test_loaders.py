# tests/test_loaders.py
import unittest
from wc_scorer import teams, rankings


class TestLoaders(unittest.TestCase):
    def test_roster_and_groups(self):
        roster = teams.load_roster()
        self.assertEqual(len(roster), 12)
        tg = teams.team_group(roster)
        self.assertEqual(tg["Mexico"], "A")

    def test_to_canonical(self):
        nm = teams.load_name_map()
        self.assertEqual(teams.to_canonical("South Korea", nm), "Korea Rep.")
        self.assertEqual(teams.to_canonical("Mexico", nm), "Mexico")
        with self.assertRaises(KeyError):
            teams.to_canonical("Atlantis", nm)

    def test_entrants(self):
        es = rankings.load_entrants()
        self.assertEqual(len(es), 63)
        self.assertTrue(all("multipliers" in e for e in es))


if __name__ == "__main__":
    unittest.main()
