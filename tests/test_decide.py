"""Run from the repo root: python -m unittest tests.test_decide"""
import unittest
from datetime import datetime, timedelta

from sfw.decide import ALLOW, decide
from sfw.rules import BLOCK, HARDER

NOW = datetime(2026, 11, 7, 12, 0, 0)
FEATURES = ["hour", "dow", "is_known_ip", "time_since_last", "attempts_last_5min"]
ROW = dict(zip(FEATURES, [12, 5, 1, 3600, 0]))


class StubModel:
    """Returns a fixed score, so the bands can be tested without training."""
    def __init__(self, score):
        self.score = score

    def score_samples(self, X):
        return [self.score]


def bundle(score):
    return {"model": StubModel(score), "p5": -0.6, "lowest": -0.7,
            "features": FEATURES}


ONE_KNOCK = [(NOW, True)]


class TestDecide(unittest.TestCase):
    def test_allow_above_p5(self):
        d = decide(bundle(-0.5), ROW, ONE_KNOCK, NOW)
        self.assertEqual((d.action, d.reason, d.score), (ALLOW, "model", -0.5))

    def test_harder_knock_between_p5_and_lowest(self):
        d = decide(bundle(-0.65), ROW, ONE_KNOCK, NOW)
        self.assertEqual(d.action, HARDER)

    def test_block_below_lowest(self):
        d = decide(bundle(-0.8), ROW, ONE_KNOCK, NOW)
        self.assertEqual((d.action, d.reason), (BLOCK, "model"))

    def test_rule_skips_model(self):
        history = [(NOW - timedelta(seconds=10 * i), True) for i in range(6)]
        d = decide(bundle(-0.5), ROW, history, NOW)  # model would allow
        self.assertEqual((d.action, d.reason, d.score), (BLOCK, "rate_1min", None))


if __name__ == "__main__":
    unittest.main()
