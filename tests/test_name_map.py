# tests/test_name_map.py
import unittest
from wc_scorer.xlsx_reader import read_sheet
from wc_scorer.extract import extract_roster, build_name_map, norm

ALIASES = {
    "South Korea": "Korea Rep.", "Türkiye": "Turkey", "United States": "USA",
    "Congo DR": "Congo", "Bosnia-Herzegovina": "Bosnia", "Uzbekistan": "Uzebekistan",
}

class TestNameMap(unittest.TestCase):
    def setUp(self):
        self.roster = extract_roster(read_sheet("World Cup Tipping 2026.xlsx", "Results"))

    def test_norm_strips_accents_and_punct(self):
        self.assertEqual(norm("Curaçao"), norm("Curacao"))
        self.assertEqual(norm("Korea Rep."), "korearep")

    def test_auto_matches_and_aliases(self):
        feed = {"Mexico", "Curaçao", "South Korea", "Türkiye", "United States",
                "Congo DR", "Bosnia-Herzegovina", "Uzbekistan",
                "Group A 2nd Place", "Winner Match 73"}
        name_map, exceptions = build_name_map(self.roster, feed,
                                              manual_aliases=ALIASES)
        self.assertEqual(name_map["Mexico"], "Mexico")
        self.assertEqual(name_map["Curaçao"], "Curacao")
        self.assertEqual(name_map["South Korea"], "Korea Rep.")
        self.assertNotIn("Group A 2nd Place", name_map)   # placeholder filtered
        self.assertEqual(exceptions, [])                  # all resolved via aliases

    def test_unaliased_real_team_becomes_exception(self):
        name_map, exceptions = build_name_map(self.roster, {"South Korea"},
                                              manual_aliases={})
        self.assertIn("South Korea", exceptions)

    def test_real_feed_fully_resolved(self):
        from wc_scorer import espn
        aliases = {"South Korea": "Korea Rep.", "Türkiye": "Turkey",
                   "United States": "USA", "Congo DR": "Congo",
                   "Bosnia-Herzegovina": "Bosnia", "Uzbekistan": "Uzebekistan"}
        names = espn.team_names(espn.fetch(cache_dir="data/cache"))
        name_map, exceptions = build_name_map(self.roster, names, manual_aliases=aliases)
        self.assertEqual(exceptions, [], f"unfiltered/unmapped feed names: {exceptions}")
        flat = [t for ts in self.roster.values() for t in ts]
        self.assertTrue(set(flat) <= set(name_map.values()))

if __name__ == "__main__":
    unittest.main()
