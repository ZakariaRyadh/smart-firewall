"""Run from the repo root: python -m unittest tests.test_state"""
import random
import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from sfw.decide import Decision
from sfw.features import CAP_SECONDS, FEATURES, build_features
from sfw.state import (HARD_WINDOW, clear_hard_flag, connect, decision_counts,
                       flag_hard, get_meta, hard_flag_active, is_known,
                       live_features, log_decision, mark_known, recent_decisions,
                       recent_knocks, record_knock, set_meta)

TZ = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 7, 15, 0, 0, tzinfo=TZ)


class TestState(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")

    def test_first_ever_knock(self):
        f = live_features(self.db, "1.1.1.1", NOW)
        self.assertEqual(f["time_since_last"], CAP_SECONDS)
        self.assertEqual(f["is_known_ip"], 0)
        self.assertEqual(f["attempts_last_5min"], 0)
        self.assertEqual((f["hour"], f["dow"]), (15, NOW.weekday()))

    def test_gap_is_capped(self):
        record_knock(self.db, "1.1.1.1", NOW - timedelta(days=30))
        f = live_features(self.db, "1.1.1.1", NOW)
        self.assertEqual(f["time_since_last"], CAP_SECONDS)

    def test_other_ip_not_counted(self):
        record_knock(self.db, "2.2.2.2", NOW - timedelta(seconds=10))
        f = live_features(self.db, "1.1.1.1", NOW)
        self.assertEqual((f["attempts_last_5min"], f["time_since_last"]),
                         (0, CAP_SECONDS))

    def test_known_only_after_mark_known(self):
        record_knock(self.db, "1.1.1.1", NOW - timedelta(seconds=10))
        self.assertFalse(is_known(self.db, "1.1.1.1"))  # knocking alone is not enough
        mark_known(self.db, "1.1.1.1", NOW)
        mark_known(self.db, "1.1.1.1", NOW)  # twice is fine
        self.assertEqual(live_features(self.db, "1.1.1.1", NOW)["is_known_ip"], 1)

    def test_recent_knocks_window_and_order(self):
        record_knock(self.db, "1.1.1.1", NOW - timedelta(seconds=400))
        record_knock(self.db, "1.1.1.1", NOW - timedelta(seconds=20), ok=False)
        record_knock(self.db, "1.1.1.1", NOW)
        got = recent_knocks(self.db, "1.1.1.1", NOW)
        self.assertEqual([ok for _, ok in got], [False, True])

    def test_log_decision(self):
        log_decision(self.db, "1.1.1.1", NOW, Decision("block", "rate_1min"))
        row = self.db.execute("SELECT ip, action, reason, score FROM decisions").fetchone()
        self.assertEqual(row, ("1.1.1.1", "block", "rate_1min", None))

    def test_recent_decisions_and_counts(self):
        feats = {"hour": 15, "dow": 5, "is_known_ip": 1,
                 "time_since_last": 60.0, "attempts_last_5min": 0}
        for i in range(5):
            log_decision(self.db, "1.1.1.1", NOW + timedelta(seconds=i),
                         Decision("allow", "model", -0.4), feats)
        log_decision(self.db, "2.2.2.2", NOW, Decision("block", "rate_1min"))
        newest = recent_decisions(self.db, limit=3)
        self.assertEqual([e["id"] for e in newest], [4, 5, 6])  # newest 3, oldest first
        self.assertEqual(recent_decisions(self.db, after_id=5)[0]["ip"], "2.2.2.2")
        self.assertEqual(recent_decisions(self.db, after_id=1)[0]["features"]["hour"], 15)
        self.assertEqual(decision_counts(self.db), {"allow": 5, "block": 1})

    def test_meta(self):
        self.assertIsNone(get_meta(self.db, "demo"))
        set_meta(self.db, "demo", "1")
        self.assertEqual(get_meta(self.db, "demo"), "1")


class TestParity(unittest.TestCase):
    """live_features must give the same numbers as build_features."""

    def test_same_as_build_features(self):
        rng = random.Random(3)
        ips = ["1.1.1.1", "2.2.2.2", "3.3.3.3"]
        t = datetime(2026, 11, 1, 8, 0, 0, tzinfo=TZ)
        rows = []
        for _ in range(80):
            t += timedelta(seconds=rng.choice([3, 17, 45, 200, 299, 301, 4000, 90000]))
            rows.append({"timestamp": pd.Timestamp(t), "source_ip": rng.choice(ips)})
        feat = build_features(pd.DataFrame(rows)).reset_index(drop=True)

        db = connect(":memory:")
        for _, row in feat.iterrows():
            now = row["timestamp"].to_pydatetime()
            live = live_features(db, row["source_ip"], now)
            for name in FEATURES:
                self.assertEqual(live[name], row[name], (name, now))
            record_knock(db, row["source_ip"], now)
            mark_known(db, row["source_ip"], now)  # normal rows: all allowed


class TestHardFlag(unittest.TestCase):
    """An IP told to do the longer knock is flagged for a few minutes."""

    def setUp(self):
        self.db = connect(":memory:")

    def test_flag_is_active_inside_the_window(self):
        flag_hard(self.db, "1.1.1.1", NOW)
        self.assertTrue(hard_flag_active(self.db, "1.1.1.1", NOW))
        self.assertTrue(hard_flag_active(self.db, "1.1.1.1",
                                         NOW + timedelta(seconds=HARD_WINDOW - 1)))

    def test_flag_expires(self):
        flag_hard(self.db, "1.1.1.1", NOW)
        self.assertFalse(hard_flag_active(self.db, "1.1.1.1",
                                          NOW + timedelta(seconds=HARD_WINDOW + 1)))

    def test_no_flag_by_default_and_other_ips_unaffected(self):
        self.assertFalse(hard_flag_active(self.db, "1.1.1.1", NOW))
        flag_hard(self.db, "1.1.1.1", NOW)
        self.assertFalse(hard_flag_active(self.db, "2.2.2.2", NOW))

    def test_flagging_again_extends_the_window(self):
        flag_hard(self.db, "1.1.1.1", NOW)
        later = NOW + timedelta(seconds=HARD_WINDOW - 10)
        flag_hard(self.db, "1.1.1.1", later)
        self.assertTrue(hard_flag_active(self.db, "1.1.1.1",
                                         later + timedelta(seconds=HARD_WINDOW - 1)))

    def test_clear_removes_the_flag(self):
        flag_hard(self.db, "1.1.1.1", NOW)
        clear_hard_flag(self.db, "1.1.1.1")
        self.assertFalse(hard_flag_active(self.db, "1.1.1.1", NOW))
        clear_hard_flag(self.db, "1.1.1.1")  # clearing twice is fine


if __name__ == "__main__":
    unittest.main()
