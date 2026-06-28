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

    def test_no_group_winner_until_group_complete(self):
        # one game each: group not decided -> no winner awarded yet (matches workbook)
        matches = [
            m("group", "Mexico", "South Africa", 3, 0),
            m("group", "Korea Rep.", "Czechia", 0, 0),
        ]
        s = team_stats(matches, ROSTER)
        self.assertEqual(s["Mexico"]["group_winner"], 0)
        self.assertEqual(s["_warnings"], [])  # no premature tie warnings either

    def test_group_milestones_wait_for_whole_group_stage(self):
        # group A fully played but group B not started -> award nothing yet
        a_done = [
            m("group", "Mexico", "South Africa", 3, 0),
            m("group", "Korea Rep.", "Czechia", 0, 0),
            m("group", "Mexico", "Korea Rep.", 2, 0),
            m("group", "Mexico", "Czechia", 1, 0),
            m("group", "South Africa", "Korea Rep.", 1, 0),
            m("group", "South Africa", "Czechia", 1, 0),
        ]
        s = team_stats(a_done, ROSTER)
        self.assertEqual(s["Mexico"]["group_winner"], 0)   # group B unfinished
        self.assertEqual(s["Mexico"]["qualify"], 0)

    def test_group_winner_and_qualify_when_stage_complete(self):
        # 12 complete groups. Per group: t0 wins all, t1 wins two, t2 beats t3,
        # t3 loses all. t2's winning margin grows with i to order the 12 thirds.
        roster = {chr(65 + i): [f"G{i}T{j}" for j in range(4)] for i in range(12)}
        matches = []
        for i in range(12):
            t0, t1, t2, t3 = roster[chr(65 + i)]
            matches += [
                m("group", t0, t1, 1, 0), m("group", t0, t2, 1, 0), m("group", t0, t3, 1, 0),
                m("group", t1, t2, 1, 0), m("group", t1, t3, 1, 0),
                m("group", t2, t3, 1 + i, 0),
            ]
        s = team_stats(matches, roster)
        self.assertEqual(s["G5T0"]["group_winner"], 1)     # winner of each group
        self.assertEqual(s["G5T1"]["group_winner"], 0)
        self.assertEqual(s["G5T0"]["qualify"], 0)          # winner excluded from qualify (Exc GW)
        self.assertEqual(s["G5T1"]["qualify"], 1)          # runner-up qualifies
        self.assertEqual(s["G5T3"]["qualify"], 0)          # 4th never qualifies
        # 8 best thirds qualify: highest margins (i=4..11) in, i=0..3 out
        self.assertEqual(s["G11T2"]["qualify"], 1)
        self.assertEqual(s["G0T2"]["qualify"], 0)
        self.assertEqual(s["_warnings"], [])

    def test_group_winner_excluded_from_qualify_bonus(self):
        # Workbook col J is "Round of 32 Qual (2) (Exc GW)" — group winners get the
        # +5 group-winner bonus, NOT the +2 qualify bonus. Only non-winning qualifiers
        # (runners-up, best thirds) get qualify.
        roster = {chr(65 + i): [f"G{i}T{j}" for j in range(4)] for i in range(12)}
        matches = []
        for i in range(12):
            t0, t1, t2, t3 = roster[chr(65 + i)]
            matches += [
                m("group", t0, t1, 1, 0), m("group", t0, t2, 1, 0), m("group", t0, t3, 1, 0),
                m("group", t1, t2, 1, 0), m("group", t1, t3, 1, 0),
                m("group", t2, t3, 1 + i, 0),
            ]
        s = team_stats(matches, roster)
        self.assertEqual(s["G5T0"]["group_winner"], 1)     # group winner
        self.assertEqual(s["G5T0"]["qualify"], 0)          # ...excluded from qualify (Exc GW)
        self.assertEqual(s["G5T1"]["qualify"], 1)          # runner-up still qualifies

    def test_knockout_run_accumulates_milestones(self):
        roster = {"A": ["X", "Y", "Z", "W"], "B": ["V", "U", "P", "Q"]}
        matches = [
            m("r32", "X", "Y", 1, 0),                                  # X & Y qualify
            m("r16", "X", "Z", 2, 1),                                  # X & Z reach R16
            m("qf", "X", "W", 1, 0),                                   # X & W make QF
            m("sf", "X", "V", 1, 1, penalties=True, winner="X"),       # draw both; X advances
            m("final", "X", "U", 2, 0),                                # X & U make final; X champion
        ]
        s = team_stats(matches, roster)
        x = s["X"]
        self.assertEqual((x["qualify"], x["r16"], x["qf"], x["sf"], x["final"], x["winner"]),
                         (1, 1, 1, 1, 1, 1))
        self.assertEqual(x["win"], 4)            # R32, R16, QF, Final (SF was a shootout = draw)
        self.assertEqual(x["draw"], 1)           # SF shootout
        self.assertEqual(s["Y"]["qualify"], 1)   # R32 loser still qualified
        self.assertEqual(s["Z"]["r16"], 1)       # reached R16...
        self.assertEqual(s["Z"]["qf"], 0)        # ...but lost there, never made QF
        self.assertEqual(s["U"]["final"], 1)
        self.assertEqual(s["U"]["winner"], 0)    # runner-up is not champion

    def test_unclassified_completed_match_warns(self):
        s = team_stats([m("other", "Mexico", "Canada", 1, 0)], ROSTER)
        self.assertTrue(any("Mexico" in w and "Canada" in w for w in s["_warnings"]))

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

    def test_adjust_override_applies_delta(self):
        # `adjust` corrects feed glitches additively (a delta), so the correction survives
        # later matches — unlike `patch`, which sets an absolute value.
        matches = [
            m("group", "Mexico", "South Africa", 2, 0,
              cards={"Mexico": {"yellow": 1, "red": 0}, "South Africa": {"yellow": 0, "red": 0}}),
        ]
        s = team_stats(matches, ROSTER,
                       overrides={"adjust": {"Mexico": {"yellow": 1}, "South Africa": {"yellow": -0}}})
        self.assertEqual(s["Mexico"]["yellow"], 2)   # derived 1 + delta 1
        # a negative delta subtracts from the derived value
        s2 = team_stats(matches, ROSTER, overrides={"adjust": {"Mexico": {"yellow": -1}}})
        self.assertEqual(s2["Mexico"]["yellow"], 0)

if __name__ == "__main__":
    unittest.main()
