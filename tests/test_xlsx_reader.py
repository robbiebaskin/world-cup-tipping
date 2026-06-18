# tests/test_xlsx_reader.py
import unittest
from wc_scorer.xlsx_reader import col_to_num, num_to_col, read_sheet, cell

XLSX = "World Cup Tipping 2026.xlsx"

class TestColumns(unittest.TestCase):
    def test_col_round_trip(self):
        for n in (1, 16, 17, 18, 26, 27, 35, 50):
            self.assertEqual(col_to_num(num_to_col(n)), n)
        self.assertEqual(num_to_col(1), "A")
        self.assertEqual(num_to_col(18), "R")
        self.assertEqual(num_to_col(35), "AI")

class TestReadSheet(unittest.TestCase):
    def setUp(self):
        self.results = read_sheet(XLSX, "Results")

    def test_group_header_and_first_team_present(self):
        # The first team of each group lives on the SAME row as the points
        # formula; a reader that mishandles self-closing cells drops it.
        self.assertEqual(cell(self.results, "A", 2), "Group A")
        self.assertEqual(cell(self.results, "A", 3), "Mexico")
        self.assertEqual(cell(self.results, "A", 4), "South Africa")

    def test_points_formula_captured(self):
        f = self.results["O3"]["formula"]
        self.assertIn("(B3*5)", f)
        self.assertIn("(N3*30)", f)

if __name__ == "__main__":
    unittest.main()
