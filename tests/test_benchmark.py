import unittest

from llokim.benchmark import (
    benchmark_once,
    peak_rss_mib,
    run_benchmark,
    synthetic_entries,
)


class BenchmarkTests(unittest.TestCase):
    def test_synthetic_sizes(self):
        self.assertEqual(len(synthetic_entries(100)), 100)

    def test_single_benchmark(self):
        result = benchmark_once(100, iterations=1)
        self.assertEqual(result["events"], 100)
        self.assertIsInstance(result["parsing_seconds"], float)
        self.assertIsInstance(result["analysis_seconds"], float)
        self.assertIsInstance(result["report_seconds"], float)
        self.assertEqual(result["ai_inference_seconds"], None)

    def test_complete_benchmark_metadata(self):
        result = run_benchmark(sizes=(100,), iterations=1)
        self.assertTrue(result["synthetic"])
        self.assertEqual(result["ai_inference"], "not run")
        self.assertEqual(len(result["measurements"]), 1)

    def test_peak_rss_is_optional(self):
        memory = peak_rss_mib()
        self.assertTrue(memory is None or memory >= 0)


if __name__ == "__main__":
    unittest.main()
