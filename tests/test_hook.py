"""Run from the repo root: python -m unittest tests.test_hook"""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from gateway import hook
from sfw.rules import BLOCK, HARDER
from sfw.state import connect, decision_counts, is_known, recent_decisions

NOW = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
IP = "10.10.10.3"
FEATURES = ["hour", "dow", "is_known_ip", "time_since_last", "attempts_last_5min"]


class StubModel:
    def __init__(self, score):
        self.score = score

    def score_samples(self, X):
        return [self.score]


def bundle(score):
    return {"model": StubModel(score), "p5": -0.6, "lowest": -0.7, "features": FEATURES}


class FakeFw:
    def __init__(self):
        self.calls = []

    def allow(self, ip):
        self.calls.append(("allow", ip))

    def block(self, ip):
        self.calls.append(("block", ip))


class FailingFw(FakeFw):
    def allow(self, ip):
        raise RuntimeError("nft failed")


class TestHandleKnock(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.fw = FakeFw()

    def knock(self, score, ip=IP, now=NOW):
        return hook.handle_knock(self.db, bundle(score), ip, now, self.fw)

    def test_allow_opens_and_marks_known(self):
        d = self.knock(-0.5)
        self.assertEqual(d.action, "allow")
        self.assertEqual(self.fw.calls, [("allow", IP)])
        self.assertTrue(is_known(self.db, IP))
        self.assertEqual(decision_counts(self.db), {"allow": 1})

    def test_block_by_model_blocks_and_stays_unknown(self):
        d = self.knock(-0.8)
        self.assertEqual((d.action, d.reason), (BLOCK, "model"))
        self.assertEqual(self.fw.calls, [("block", IP)])
        self.assertFalse(is_known(self.db, IP))

    def test_harder_knock_opens_nothing(self):
        d = self.knock(-0.65)
        self.assertEqual(d.action, HARDER)
        self.assertEqual(self.fw.calls, [])
        self.assertFalse(is_known(self.db, IP))
        self.assertEqual(decision_counts(self.db), {"harder_knock": 1})

    def test_rule_blocks_after_burst_even_if_model_allows(self):
        for i in range(6):                       # 6 knocks, 10 s apart, model says allow
            d = self.knock(-0.5, now=NOW + timedelta(seconds=10 * i))
        self.assertEqual((d.action, d.reason), (BLOCK, "rate_1min"))
        self.assertEqual(self.fw.calls[-1], ("block", IP))
        self.assertEqual(self.fw.calls.count(("allow", IP)), 5)

    def test_decision_and_features_are_saved(self):
        self.knock(-0.5)
        row = recent_decisions(self.db)[0]
        self.assertEqual((row["ip"], row["action"], row["score"]), (IP, "allow", -0.5))
        self.assertEqual(row["features"]["hour"], 12)

    def test_other_ips_are_separate(self):
        self.knock(-0.5, ip="10.10.10.3")
        self.knock(-0.8, ip="10.10.10.4")
        self.assertEqual(self.fw.calls, [("allow", "10.10.10.3"), ("block", "10.10.10.4")])

    def test_nft_failure_fails_closed(self):
        with self.assertRaises(RuntimeError):
            hook.handle_knock(self.db, bundle(-0.5), IP, NOW, FailingFw())
        self.assertFalse(is_known(self.db, IP))          # not marked known
        self.assertEqual(decision_counts(self.db), {"allow": 1})  # but still visible

    def test_bad_ip_never_reaches_the_firewall(self):
        for bad in ["1.2.3.4; reboot", "::1", "abc", "", "10.10.10.3/24", "1.2.3"]:
            with self.assertRaises(ValueError):
                self.knock(-0.5, ip=bad)
        self.assertEqual(self.fw.calls, [])
        self.assertEqual(decision_counts(self.db), {})


class TestNft(unittest.TestCase):
    def test_allow_uses_fixed_argument_list(self):
        with mock.patch("gateway.hook.subprocess.run") as run:
            hook.Nft().allow(IP)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0],
                         ["/usr/sbin/nft", "add", "element", "inet", "sfw", "knocked",
                          "{ 10.10.10.3 }"])
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertTrue(run.call_args.kwargs["check"])

    def test_block_uses_blocked_set(self):
        with mock.patch("gateway.hook.subprocess.run") as run:
            hook.Nft().block(IP)
        self.assertEqual(run.call_args.args[0][5], "blocked")

    def test_bad_ip_is_refused_before_nft(self):
        with mock.patch("gateway.hook.subprocess.run") as run:
            with self.assertRaises(ValueError):
                hook.Nft().allow("1.2.3.4 } ; flush ruleset ; {")
        run.assert_not_called()


class TestMain(unittest.TestCase):
    def test_wrong_arguments(self):
        self.assertEqual(hook.main([]), 2)
        self.assertEqual(hook.main(["a", "b"]), 2)

    def test_bad_ip_fails_closed(self):
        with mock.patch.object(hook, "Nft") as nft:
            self.assertEqual(hook.main(["not-an-ip"]), 1)
        nft.assert_not_called()

    def test_missing_model_fails_closed(self):
        env = {"SFW_MODEL": "/nonexistent/model.joblib", "SFW_DB": ":memory:"}
        with mock.patch.dict(os.environ, env), mock.patch.object(hook, "Nft") as nft:
            self.assertEqual(hook.main([IP]), 1)
        nft.assert_not_called()

    def test_full_run_loads_model_and_db_from_files(self):
        import tempfile
        import joblib
        with tempfile.TemporaryDirectory() as tmp:
            model, dbfile = os.path.join(tmp, "m.joblib"), os.path.join(tmp, "s.db")
            joblib.dump(bundle(-0.5), model)      # StubModel is pickled by reference
            env = {"SFW_MODEL": model, "SFW_DB": dbfile}
            with mock.patch.dict(os.environ, env), mock.patch.object(hook, "Nft") as nft:
                self.assertEqual(hook.main([IP]), 0)
            nft.return_value.allow.assert_called_once_with(IP)
            self.assertEqual(decision_counts(connect(dbfile)), {"allow": 1})

    def test_nft_error_gives_exit_1(self):
        import tempfile
        import joblib
        with tempfile.TemporaryDirectory() as tmp:
            model = os.path.join(tmp, "m.joblib")
            joblib.dump(bundle(-0.5), model)
            env = {"SFW_MODEL": model, "SFW_DB": os.path.join(tmp, "s.db")}
            with mock.patch.dict(os.environ, env), mock.patch.object(hook, "Nft") as nft:
                nft.return_value.allow.side_effect = RuntimeError("nft failed")
                self.assertEqual(hook.main([IP]), 1)


if __name__ == "__main__":
    unittest.main()
