# tests/test_team_stats.py
import unittest
from wc_scorer.scoring import team_stats, empty_stats

ROSTER = {"A": ["Mexico", "South Africa", "Korea Rep.", "Czechia"],
          "B": ["Canada", "Bosnia", "Qatar", "Switzerland"]}

def m(stage, a, b, ga, gb, completed=True, penalties=False, winner=None, cards=None):
    return {"stage": stage, "team_a": a, "team_b": b, "ga": ga, "gb": gb,
            "completed": completed, "penalties": penalties, "shootout_winner": winner,
            "cards": cards or {a: {"yellow": 0, "red": 0}, b: {"yellow": 0, "red": 0}}}

class TestTeamStats(unittest.TestCase):
    def test_win_draw_goals_cards(self):
        matches = [
            m("group", "Mexico", "South Africa", 2, 0,
              cards={"Mexico": {"yellow": 1, "red": 0}, "South Africa": {"yellow": 0, "red": 1}}),
            m("group", "Mexico", "Korea Rep.", 1, 1),
        ]
        s = team_stats(matches, ROSTER)
        self.assertEqual(s["Mexico"]["win"], 1)
        self.assertEqual(s["Mexico"]["draw"], 1)
        self.assertEqual(s["Mexico"]["gf"], 3)
        self.assertEqual(s["Mexico"]["ga"], 1)
        self.assertEqual(s["Mexico"]["yellow"], 1)
        self.assertEqual(s["South Africa"]["loss"], 1)
        self.assertEqual(s["South Africa"]["red"], 1)

    def test_group_winner(self):
        matches = [
            m("group", "Mexico", "South Africa", 3, 0),
            m("group", "Korea Rep.", "Czechia", 0, 0),
        ]
        s = team_stats(matches, ROSTER)
        self.assertEqual(s["Mexico"]["group_winner"], 1)
        self.assertEqual(s["South Africa"]["group_winner"], 0)

    def test_penalty_knockout_is_draw_for_both_winner_advances(self):
        matches = [m("r32", "Mexico", "Canada", 1, 1, penalties=True, winner="Mexico")]
        s = team_stats(matches, ROSTER)
        self.assertEqual(s["Mexico"]["draw"], 1)
        self.assertEqual(s["Canada"]["draw"], 1)
        self.assertEqual(s["Mexico"]["qualify"], 1)
        self.assertEqual(s["Canada"]["qualify"], 1)

    def test_override_group_winner(self):
        matches = [m("group", "Mexico", "South Africa", 3, 0)]
        s = team_stats(matches, ROSTER, overrides={"force_group_winner": {"A": "Korea Rep."}})
        self.assertEqual(s["Korea Rep."]["group_winner"], 1)
        self.assertEqual(s["Mexico"]["group_winner"], 0)

if __name__ == "__main__":
    unittest.main()
