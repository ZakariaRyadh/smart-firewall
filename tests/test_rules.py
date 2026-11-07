"""Run from the repo root: python -m unittest tests.test_rules"""
import unittest
from datetime import datetime, timedelta

from sfw.rules import BLOCK, HARDER, check_rules

NOW = datetime(2026, 11, 7, 12, 0, 0)


def knocks(offsets, ok=True):
    """Knocks at `offsets` seconds before NOW (largest offset = oldest)."""
    return [(NOW - timedelta(seconds=s), ok) for s in offsets]


class TestRules(unittest.TestCase):
    def test_normal_mistype_fires_nothing(self):
        # 2 tries, 10 s apart: first wrong, second right
        history = [(NOW - timedelta(seconds=10), False), (NOW, True)]
        self.assertIsNone(check_rules(history, NOW))

    def test_single_knock_fires_nothing(self):
        self.assertIsNone(check_rules(knocks([0]), NOW))

    def test_rate_1min_blocks(self):
        history = knocks([50, 40, 30, 20, 10, 0])  # 6 in 1 min, 10 s apart
        self.assertEqual(check_rules(history, NOW), ("rate_1min", BLOCK))

    def test_rate_1min_five_is_ok(self):
        history = knocks([40, 30, 20, 10, 0])  # exactly 5
        self.assertIsNone(check_rules(history, NOW))

    def test_rate_5min_blocks(self):
        # 16 knocks spread over 5 min, never more than 5 in any 1 min
        history = knocks([290 - 18 * i for i in range(16)])
        self.assertEqual(check_rules(history, NOW), ("rate_5min", BLOCK))

    def test_rate_5min_old_knocks_ignored(self):
        history = knocks([600 + 10 * i for i in range(20)])  # all older than 5 min
        self.assertIsNone(check_rules(history, NOW))

    def test_bad_knock_x3_blocks(self):
        history = [(NOW - timedelta(seconds=s), False) for s in (30, 15, 0)]
        self.assertEqual(check_rules(history, NOW), ("bad_knock_x3", BLOCK))

    def test_bad_knock_two_wrong_is_ok(self):
        history = [(NOW - timedelta(seconds=s), False) for s in (15, 0)]
        self.assertIsNone(check_rules(history, NOW))

    def test_bad_knock_streak_broken_by_ok(self):
        history = [(NOW - timedelta(seconds=30), False),
                   (NOW - timedelta(seconds=15), True),
                   (NOW, False)]
        self.assertIsNone(check_rules(history, NOW))

    def test_too_fast_harder_knock(self):
        history = knocks([1.0, 0.5, 0])  # two gaps of 0.5 s
        self.assertEqual(check_rules(history, NOW), ("too_fast", HARDER))

    def test_too_fast_one_fast_gap_is_ok(self):
        history = knocks([5.5, 0.5, 0])  # only one gap under 1 s
        self.assertIsNone(check_rules(history, NOW))

    def test_block_wins_over_harder_knock(self):
        # 6 knocks in 1 s: both rate_1min (block) and too_fast (harder) fire
        history = knocks([1.0, 0.8, 0.6, 0.4, 0.2, 0])
        self.assertEqual(check_rules(history, NOW), ("rate_1min", BLOCK))

    def test_unsorted_input(self):
        history = list(reversed([(NOW - timedelta(seconds=s), False)
                                 for s in (30, 15, 0)]))
        self.assertEqual(check_rules(history, NOW), ("bad_knock_x3", BLOCK))


if __name__ == "__main__":
    unittest.main()
