"""Run from the repo root: python -m unittest tests.test_attack_sim"""
import unittest
from sfw.attack_sim import SCENARIOS, generate
from sfw.rules import BLOCK, check_rules

KNOWN = ["10.0.0.1", "10.0.0.2"]


def first_block(ep):
    """Knock number at which the hard rules first block, else None."""
    hist = []
    for k, t in enumerate(ep["timestamp"].dt.to_pydatetime(), 1):
        hist.append((t, True))
        hit = check_rules(hist, t)
        if hit and hit[1] == BLOCK:
            return k
    return None


class TestAttackSim(unittest.TestCase):
    def test_same_seed_same_rows(self):
        a = generate("burst", 5, seed=1, known_ips=KNOWN)
        b = generate("burst", 5, seed=1, known_ips=KNOWN)
        self.assertTrue(a.equals(b))

    def test_other_seed_differs(self):
        a = generate("burst", 5, seed=1, known_ips=KNOWN)
        b = generate("burst", 5, seed=2, known_ips=KNOWN)
        self.assertFalse(a.equals(b))

    def test_columns_and_label(self):
        df = generate("night_unknown", 3, seed=1)
        self.assertEqual(list(df.columns),
                         ["timestamp", "source_ip", "scenario", "episode", "source"])
        self.assertTrue((df["source"] == "attack_sim").all())
        self.assertTrue((df["scenario"] == "night_unknown").all())

    def test_night_unknown_hours_and_one_knock(self):
        df = generate("night_unknown", 30, seed=1)
        self.assertEqual(len(df), 30)
        self.assertTrue(df["timestamp"].dt.hour.between(1, 5).all())

    def test_known_scenarios_use_given_ips(self):
        df = generate("burst", 10, seed=1, known_ips=KNOWN)
        self.assertTrue(set(df["source_ip"]) <= set(KNOWN))

    def test_known_scenario_needs_ips(self):
        with self.assertRaises(ValueError):
            generate("burst", 1, seed=1)

    def test_rules_stop_burst_volume_slow_volume(self):
        for name in ("burst", "volume", "slow_volume"):
            df = generate(name, 20, seed=7, known_ips=KNOWN)
            for _, ep in df.groupby("episode"):
                self.assertIsNotNone(first_block(ep), name)

    def test_all_scenarios_generate(self):
        for name in SCENARIOS:
            self.assertFalse(generate(name, 2, seed=1, known_ips=KNOWN).empty)


if __name__ == "__main__":
    unittest.main()
