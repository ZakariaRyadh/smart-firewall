"""Run from the repo root: python -m unittest tests.test_attack"""
import os
import random
import tempfile
import unittest
from unittest import mock

from gateway import attack


def write_conf(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False)
    f.write(text)
    f.close()
    return f.name


class TestLoadPorts(unittest.TestCase):
    def test_reads_quoted_list_and_ignores_comments(self):
        path = write_conf('# comment\nNORMAL="1111 2222 3333"\nHARD="1 2 3"\nWAIT=4\n')
        self.addCleanup(os.remove, path)
        self.assertEqual(attack.load_ports(path), [1111, 2222, 3333])

    def test_missing_file_gives_a_clear_error(self):
        with self.assertRaisesRegex(SystemExit, "knock.conf"):
            attack.load_ports("/nonexistent/knock.conf")

    def test_missing_key_or_bad_port_is_refused(self):
        for text in ['HARD="1 2"\n', 'NORMAL=""\n', 'NORMAL="1111 abc"\n',
                     'NORMAL="CHANGE_ME_1 CHANGE_ME_2"\n', 'NORMAL="1111 70000"\n']:
            path = write_conf(text)
            self.addCleanup(os.remove, path)
            with self.assertRaises(SystemExit, msg=text):
                attack.load_ports(path)


class TestTargetGuard(unittest.TestCase):
    def test_private_addresses_are_accepted(self):
        for ok in ["10.10.10.2", "192.168.1.5", "172.16.0.9", "127.0.0.1"]:
            self.assertEqual(attack.private_ip(ok), ok)

    def test_public_addresses_and_names_are_refused(self):
        for bad in ["8.8.8.8", "1.1.1.1", "example.com", "", "10.10.10.2/24", "::1"]:
            with self.assertRaises(SystemExit, msg=bad):
                attack.private_ip(bad)


class TestPlan(unittest.TestCase):
    def test_burst_is_many_fast_knocks(self):
        gaps = attack.plan("burst", random.Random(1))
        self.assertEqual(len(gaps), 20)
        self.assertTrue(all(1 <= g <= 2 for g in gaps))

    def test_volume_is_many_slower_knocks(self):
        gaps = attack.plan("volume", random.Random(1))
        self.assertEqual(len(gaps), 25)
        self.assertTrue(all(5 <= g <= 15 for g in gaps))

    def test_single_knock_scenarios(self):
        for name in ("new_ip", "slow_known"):
            self.assertEqual(len(attack.plan(name, random.Random(1))), 1)

    def test_same_seed_same_plan(self):
        self.assertEqual(attack.plan("burst", random.Random(7)),
                         attack.plan("burst", random.Random(7)))

    def test_unknown_scenario(self):
        with self.assertRaises(SystemExit):
            attack.plan("nope", random.Random(1))


class TestKnock(unittest.TestCase):
    def test_one_connect_per_port_in_order(self):
        with mock.patch("gateway.attack.socket.socket") as sock:
            attack.knock("10.10.10.2", [1111, 2222, 3333])
        conn = sock.return_value
        self.assertEqual([c.args[0] for c in conn.connect_ex.call_args_list],
                         [("10.10.10.2", 1111), ("10.10.10.2", 2222), ("10.10.10.2", 3333)])
        self.assertEqual(conn.close.call_count, 3)

    def test_binds_to_the_source_address(self):
        with mock.patch("gateway.attack.socket.socket") as sock:
            attack.knock("10.10.10.2", [1111], source="10.10.10.4")
        sock.return_value.bind.assert_called_with(("10.10.10.4", 0))

    def test_no_bind_without_a_source(self):
        with mock.patch("gateway.attack.socket.socket") as sock:
            attack.knock("10.10.10.2", [1111])
        sock.return_value.bind.assert_not_called()

    def test_network_errors_do_not_stop_the_knock(self):
        with mock.patch("gateway.attack.socket.socket") as sock:
            sock.return_value.connect_ex.side_effect = OSError("unreachable")
            attack.knock("10.10.10.2", [1111, 2222])      # must not raise
        self.assertEqual(sock.return_value.close.call_count, 2)


class TestRun(unittest.TestCase):
    def run_scenario(self, name, probe="closed or blocked"):
        knocks, sleeps, lines = [], [], []
        attack.run(name, "10.10.10.2", [1111, 2222, 3333], rng=random.Random(1),
                   knock_fn=lambda host, ports, source=None: knocks.append((host, ports, source)),
                   sleep_fn=sleeps.append, probe_fn=lambda host, source=None: probe,
                   out=lines.append, source="10.10.10.4")
        return knocks, sleeps, lines

    def test_sends_every_knock_and_waits_between_them(self):
        knocks, sleeps, _ = self.run_scenario("burst")
        self.assertEqual(len(knocks), 20)
        self.assertEqual(knocks[0], ("10.10.10.2", [1111, 2222, 3333], "10.10.10.4"))
        self.assertEqual(len(sleeps), 20)       # 19 gaps between knocks + 1 settle wait
        self.assertTrue(all(1 <= s <= 2 for s in sleeps[:-1]))
        self.assertEqual(sleeps[-1], 4)         # lets the gateway finish deciding

    def test_reports_the_ssh_result_at_the_end(self):
        _, _, lines = self.run_scenario("new_ip", probe="open")
        self.assertIn("open", lines[-2])
        self.assertIn("dashboard", lines[-1])

    def test_never_prints_the_ports(self):
        _, _, lines = self.run_scenario("burst")
        text = "\n".join(lines)
        for port in ("1111", "2222", "3333"):
            self.assertNotIn(port, text)


class TestProbe(unittest.TestCase):
    def test_open_when_the_connect_succeeds(self):
        with mock.patch("gateway.attack.socket.socket") as sock:
            sock.return_value.connect_ex.return_value = 0
            self.assertEqual(attack.probe_ssh("10.10.10.2"), "open")

    def test_closed_or_blocked_otherwise(self):
        with mock.patch("gateway.attack.socket.socket") as sock:
            sock.return_value.connect_ex.return_value = 11
            self.assertEqual(attack.probe_ssh("10.10.10.2"), "closed or blocked")


if __name__ == "__main__":
    unittest.main()
