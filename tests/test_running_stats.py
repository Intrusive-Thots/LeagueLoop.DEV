"""
Unit tests for src/utils/running_stats.py
Tests RunningStats (Welford's algorithm) and RunningPercentile (P² algorithm).
"""
import unittest
import math
from utils.running_stats import RunningStats, RunningPercentile


class TestRunningStats(unittest.TestCase):
    def test_initial_state(self):
        stats = RunningStats()
        self.assertEqual(stats.n, 0)
        self.assertEqual(stats.mean, 0.0)
        self.assertEqual(stats.variance(), 0.0)
        self.assertEqual(stats.variance(population=False), 0.0)
        self.assertEqual(stats.stddev(), 0.0)
        self.assertEqual(stats.skewness(), 0.0)
        self.assertEqual(stats.kurtosis(), 0.0)
        self.assertEqual(stats.excess_kurtosis(), -3.0)
        self.assertEqual(stats.cv(), 0.0)
        self.assertEqual(stats.min(), 0.0)
        self.assertEqual(stats.max(), 0.0)
        self.assertEqual(stats.range(), 0.0)

    def test_single_update(self):
        stats = RunningStats()
        stats.update(42.0)
        self.assertEqual(stats.n, 1)
        self.assertEqual(stats.mean, 42.0)
        self.assertEqual(stats.variance(population=True), 0.0)
        self.assertEqual(stats.variance(population=False), 0.0)
        self.assertEqual(stats.stddev(), 0.0)
        self.assertEqual(stats.min(), 42.0)
        self.assertEqual(stats.max(), 42.0)
        self.assertEqual(stats.range(), 0.0)

    def test_multiple_updates_known_values(self):
        stats = RunningStats()
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        for x in data:
            stats.update(x)

        self.assertEqual(stats.n, 5)
        self.assertAlmostEqual(stats.mean, 30.0)
        self.assertAlmostEqual(stats.variance(population=True), 200.0)
        self.assertAlmostEqual(stats.variance(population=False), 250.0)
        self.assertAlmostEqual(stats.stddev(population=True), math.sqrt(200.0))
        self.assertAlmostEqual(stats.stddev(population=False), math.sqrt(250.0))
        self.assertAlmostEqual(stats.skewness(), 0.0)  # Symmetric distribution
        self.assertEqual(stats.min(), 10.0)
        self.assertEqual(stats.max(), 50.0)
        self.assertEqual(stats.range(), 40.0)

    def test_cv_calculation(self):
        stats = RunningStats()
        # Positive mean
        for x in [10.0, 20.0, 30.0]:
            stats.update(x)
        expected_cv = math.sqrt(200.0 / 3) / 20.0
        self.assertAlmostEqual(stats.cv(), expected_cv)

        # Zero or negative mean
        stats_zero = RunningStats()
        stats_zero.update(-10.0)
        stats_zero.update(10.0)
        self.assertEqual(stats_zero.mean, 0.0)
        self.assertEqual(stats_zero.cv(), 0.0)

    def test_skewness_and_kurtosis_thresholds(self):
        stats = RunningStats()
        # n <= 2 should return 0.0 for skewness
        stats.update(1.0)
        stats.update(2.0)
        self.assertEqual(stats.skewness(), 0.0)

        # n <= 3 should return 0.0 for kurtosis
        stats.update(3.0)
        self.assertEqual(stats.kurtosis(), 0.0)

        # n = 4 with variance > 0
        stats.update(4.0)
        self.assertIsInstance(stats.skewness(), float)
        self.assertIsInstance(stats.kurtosis(), float)
        self.assertIsInstance(stats.excess_kurtosis(), float)

        # n = 4 with non-symmetric data
        stats_skewed = RunningStats()
        for x in [1.0, 1.0, 1.0, 10.0]:
            stats_skewed.update(x)
        self.assertNotEqual(stats_skewed.skewness(), 0.0)

    def test_zero_variance_skewness_and_kurtosis(self):
        stats = RunningStats()
        for _ in range(5):
            stats.update(5.0)
        self.assertEqual(stats.variance(), 0.0)
        self.assertEqual(stats.skewness(), 0.0)
        self.assertEqual(stats.kurtosis(), 0.0)

    def test_reset(self):
        stats = RunningStats()
        for x in [1.0, 2.0, 3.0, 4.0, 5.0]:
            stats.update(x)
        stats.reset()

        self.assertEqual(stats.n, 0)
        self.assertEqual(stats.mean, 0.0)
        self.assertEqual(stats.M2, 0.0)
        self.assertEqual(stats.M3, 0.0)
        self.assertEqual(stats.M4, 0.0)
        self.assertEqual(stats.min(), 0.0)
        self.assertEqual(stats.max(), 0.0)
        self.assertEqual(stats.range(), 0.0)

    def test_get_all_stats(self):
        stats = RunningStats()
        for x in [10.0, 20.0, 30.0]:
            stats.update(x)
        all_stats = stats.get_all_stats()

        expected_keys = {
            'count', 'mean', 'variance', 'stddev', 'skewness',
            'kurtosis', 'excess_kurtosis', 'cv', 'min', 'max', 'range'
        }
        self.assertEqual(set(all_stats.keys()), expected_keys)
        self.assertEqual(all_stats['count'], 3)
        self.assertEqual(all_stats['mean'], 20.0)
        self.assertEqual(all_stats['min'], 10.0)
        self.assertEqual(all_stats['max'], 30.0)
        self.assertEqual(all_stats['range'], 20.0)


class TestRunningPercentile(unittest.TestCase):
    def test_initialization_buffer(self):
        rp = RunningPercentile(percentile=0.95)
        self.assertFalse(rp.initialized)
        self.assertEqual(rp.percentile(), 0.0)

        rp.update(10.0)
        rp.update(50.0)
        rp.update(30.0)
        self.assertFalse(rp.initialized)
        # 3 elements, p=0.95 -> idx = int(3 * 0.95) = 2 -> sorted[2] = 50.0
        self.assertEqual(rp.percentile(), 50.0)

    def test_initialization_trigger(self):
        rp = RunningPercentile(percentile=0.50)
        inputs = [10.0, 50.0, 30.0, 20.0, 40.0]
        for x in inputs:
            rp.update(x)

        self.assertTrue(rp.initialized)
        self.assertEqual(len(rp.init_buffer), 0)
        self.assertEqual(rp.q, [10.0, 20.0, 30.0, 40.0, 50.0])

    def test_stream_updates(self):
        rp = RunningPercentile(percentile=0.50)
        # Feed 100 numbers from 1 to 100
        for i in range(1, 101):
            rp.update(float(i))

        self.assertTrue(rp.initialized)
        self.assertEqual(rp.count, 100)
        # Median (50th percentile) should be close to 50
        pct = rp.percentile()
        self.assertGreater(pct, 30.0)
        self.assertLess(pct, 70.0)

    def test_extreme_values_updates(self):
        rp = RunningPercentile(percentile=0.90)
        initial_vals = [10.0, 20.0, 30.0, 40.0, 50.0]
        for x in initial_vals:
            rp.update(x)

        # Update with value below q[0]
        rp.update(5.0)
        self.assertEqual(rp.q[0], 5.0)

        # Update with value above q[4]
        rp.update(100.0)
        self.assertEqual(rp.q[4], 100.0)

        # Update with intermediate values
        for v in [15.0, 25.0, 35.0, 45.0]:
            rp.update(v)

        self.assertIsInstance(rp.percentile(), float)

    def test_reset(self):
        rp = RunningPercentile(percentile=0.95)
        for i in range(10):
            rp.update(float(i))
        rp.reset()

        self.assertEqual(rp.count, 0)
        self.assertFalse(rp.initialized)
        self.assertEqual(rp.init_buffer, [])
        self.assertEqual(rp.percentile(), 0.0)


if __name__ == '__main__':
    unittest.main()
