# tests/test_e2e.py
import unittest
from wc_scorer import cli

class TestEndToEnd(unittest.TestCase):
    def test_compute_against_real_data(self):
        results = cli.compute(ref_dir="data/reference", dates=None,
                              refresh=False, cache_dir="data/cache",
                              overrides_path=None)
        self.assertEqual(len(results), 63)
        for r in results:
            self.assertIsInstance(r["total"], int)
        # Highest scorer should be positive once group games are in.
        self.assertGreater(max(r["total"] for r in results), 0)

if __name__ == "__main__":
    unittest.main()
