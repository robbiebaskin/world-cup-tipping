# tests/test_webexport.py
import json
import os
import tempfile
import unittest

from wc_scorer import webexport

# Al (90) leads; Beth and Cy tie at 50 -> ranked by name (same key as report.ladder).
RESULTS = [
    {"name": "Beth", "star": "Brazil", "total": 50,
     "by_country": {"Brazil": {"multiplier": 5, "components": {"win": 25}, "points": 25}}},
    {"name": "Al", "star": "Spain", "total": 90,
     "by_country": {"Spain": {"multiplier": 5, "components": {"win": 25, "ga": -3}, "points": 47}}},
    {"name": "Cy", "star": "Brazil", "total": 50,
     "by_country": {"Brazil": {"multiplier": 3, "components": {"win": 15}, "points": 15}}},
]
TEAM_GROUP = {"Brazil": "C", "Spain": "H"}
ROSTER = {"C": ["Brazil", "Haiti", "Morocco", "Scotland"],
          "H": ["Spain", "Tunisia", "Norway", "Iraq"]}
WEIGHTS = {"win": 5, "draw": 3, "gf": 2, "ga": -1}
MATCHES = [
    {"stage": "group", "team_a": "Brazil", "team_b": "Scotland", "ga": 2, "gb": 0,
     "completed": True, "penalties": False, "shootout_winner": None},
    {"stage": "group", "team_a": "Spain", "team_b": "Iraq", "ga": 1, "gb": 1,
     "completed": True, "penalties": False, "shootout_winner": None},
    {"stage": "group", "team_a": "Haiti", "team_b": "Morocco", "ga": 0, "gb": 0,
     "completed": False, "penalties": False, "shootout_winner": None},
]
NOW = "2026-06-18T00:00:00+00:00"


def build():
    return webexport.build_payload(RESULTS, ["group A tie"], TEAM_GROUP, ROSTER,
                                   MATCHES, WEIGHTS, NOW)


class TestBuildPayload(unittest.TestCase):
    def test_entrants_ranked_with_tie_broken_by_name(self):
        ents = build()["entrants"]
        self.assertEqual([(e["rank"], e["name"]) for e in ents],
                         [(1, "Al"), (2, "Beth"), (3, "Cy")])

    def test_by_country_passed_through_verbatim(self):
        al = build()["entrants"][0]
        self.assertEqual(al["by_country"], RESULTS[1]["by_country"])
        self.assertEqual(al["total"], 90)
        self.assertEqual(al["star"], "Spain")

    def test_tournament_progress(self):
        t = build()["tournament"]
        self.assertEqual(t["matches_played"], 2)   # two completed
        self.assertEqual(t["matches_total"], 104)
        self.assertEqual(t["stage"], "Group stage")
        self.assertEqual(t["groups"], ROSTER)

    def test_metadata_blocks_present(self):
        p = build()
        self.assertEqual(p["team_group"], TEAM_GROUP)
        self.assertEqual(p["weights"], WEIGHTS)
        self.assertEqual(p["warnings"], ["group A tie"])
        self.assertEqual(p["generated_at"], NOW)
        self.assertEqual(p["matches"], MATCHES)

    def test_stage_label_advances_to_knockout(self):
        matches = MATCHES + [{"stage": "qf", "team_a": "Spain", "team_b": "Brazil",
                              "ga": 1, "gb": 0, "completed": False,
                              "penalties": False, "shootout_winner": None}]
        p = webexport.build_payload(RESULTS, [], TEAM_GROUP, ROSTER, matches, WEIGHTS, NOW)
        self.assertEqual(p["tournament"]["stage"], "Quarter-finals")


class TestWriteJson(unittest.TestCase):
    def test_round_trips_and_creates_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "web", "data.json")
            payload = build()
            webexport.write_json(payload, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                self.assertEqual(json.load(f), payload)


if __name__ == "__main__":
    unittest.main()
