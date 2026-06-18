import unittest, os

class TestSanity(unittest.TestCase):
    def test_workbook_present(self):
        self.assertTrue(os.path.exists("World Cup Tipping 2026.xlsx"))

    def test_package_importable(self):
        import wc_scorer  # noqa: F401

if __name__ == "__main__":
    unittest.main()
