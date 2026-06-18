# tests/test_espn_parse.py
import unittest
from wc_scorer import espn, teams

class TestParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = espn.fetch(cache_dir="data/cache")
        cls.matches = espn.parse(raw, teams.load_name_map())

    def test_completed_group_matches_parsed(self):
        done = [m for m in self.matches if m["completed"]]
        self.assertGreaterEqual(len(done), 20)
        opener = next(m for m in done if {m["team_a"], m["team_b"]} == {"Mexico", "South Africa"})
        self.assertEqual(opener["stage"], "group")
        # Mexico 2 - 0 South Africa
        gf = opener["ga"] if opener["team_a"] == "Mexico" else opener["gb"]
        self.assertEqual(gf, 2)

    def test_names_are_canonical(self):
        for m in self.matches:
            self.assertNotIn("South Korea", (m["team_a"], m["team_b"]))

    def test_scored_penalty_not_counted_as_red_card(self):
        # "Penalty - Scored" contains the substring "red" (sco-RED); it must NOT
        # be counted as a red card. Real cards still count.
        raw = {"events": [{
            "season": {"slug": "group-stage"},
            "competitions": [{
                "status": {"type": {"completed": True}},
                "competitors": [
                    {"team": {"id": "1", "displayName": "Germany"}, "score": "2"},
                    {"team": {"id": "2", "displayName": "Curacao"}, "score": "0"},
                ],
                "details": [
                    {"type": {"text": "Penalty - Scored"}, "team": {"id": "1"}},
                    {"type": {"text": "Yellow Card"}, "team": {"id": "1"}},
                    {"type": {"text": "Red Card"}, "team": {"id": "2"}},
                ],
            }],
        }]}
        cards = espn.parse(raw, {"Germany": "Germany", "Curacao": "Curacao"})[0]["cards"]
        self.assertEqual(cards["Germany"]["red"], 0)     # scored penalty is not a red
        self.assertEqual(cards["Germany"]["yellow"], 1)
        self.assertEqual(cards["Curacao"]["red"], 1)     # a real red still counts

    def test_stage_helper(self):
        self.assertEqual(espn.stage_of({"season": {"slug": "group-stage"}}), "group")
        self.assertEqual(espn.stage_of({"season": {"slug": "round-of-32"}}), "r32")
        self.assertEqual(espn.stage_of({"season": {"slug": "quarterfinals"}}), "qf")
        self.assertEqual(espn.stage_of({"season": {"slug": "final"}}), "final")

if __name__ == "__main__":
    unittest.main()
