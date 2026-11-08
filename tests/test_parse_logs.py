"""Run from the repo root: python -m unittest tests.test_parse_logs

All log lines here are made up (documentation IPs, fake users).
"""
import unittest
from datetime import datetime

from pipeline.parse_logs import LOCAL, parse_lines, parse_ts

NOW = datetime(2026, 11, 8, 12, 0, 0, tzinfo=LOCAL)

ISO_ACCEPT = "2026-11-05T11:21:36+01:00 pi sshd-session[100]: Accepted password for alice from 192.0.2.10 port 40000 ssh2"
ISO_FAIL = "2026-11-05T11:20:00+01:00 pi sshd-session[101]: Failed password for alice from 192.0.2.10 port 40001 ssh2"
INVALID = "2026-11-05T11:19:50+01:00 pi sshd-session[102]: Invalid user bob from 198.51.100.7 port 50000"
INVALID_FAIL = "2026-11-05T11:19:55+01:00 pi sshd-session[102]: Failed password for invalid user bob from 198.51.100.7 port 50000 ssh2"
NOISE = "2026-11-05T11:19:00+01:00 pi sshd[1]: Server listening on 0.0.0.0 port 22."


class TestParseTs(unittest.TestCase):
    def test_iso_other_zone_converted_to_algiers(self):
        t = parse_ts("2026-11-05T10:00:00+00:00", NOW)
        self.assertEqual(t.hour, 11)
        self.assertEqual(t.utcoffset().total_seconds(), 3600)

    def test_syslog_stamp_gets_algiers_zone(self):
        t = parse_ts("Nov  5 10:00:03", NOW)
        self.assertIsNotNone(t.tzinfo)
        self.assertEqual((t.year, t.month, t.day, t.hour), (2026, 11, 5, 10))

    def test_syslog_december_read_in_january_is_last_year(self):
        jan = datetime(2027, 1, 3, 9, 0, 0, tzinfo=LOCAL)
        t = parse_ts("Dec 30 23:00:00", jan)
        self.assertEqual(t.year, 2026)


class TestParseLines(unittest.TestCase):
    def test_fields_and_sort_order(self):
        recs = parse_lines([ISO_ACCEPT, ISO_FAIL], NOW)
        self.assertEqual([r["result"] for r in recs], ["failed", "accepted"])
        r = recs[1]
        self.assertEqual(r["source_ip"], "192.0.2.10")
        self.assertEqual(r["user"], "alice")
        self.assertEqual(r["day_of_week"], "Thursday")
        self.assertEqual(r["hour"], 11)
        self.assertEqual(r["auth_method"], "password")
        self.assertEqual(r["port"], "40000")
        self.assertTrue(r["timestamp"].endswith("+01:00"))

    def test_unrelated_lines_ignored(self):
        self.assertEqual(parse_lines([NOISE, "garbage"], NOW), [])

    def test_invalid_user_then_failed_counts_once(self):
        recs = parse_lines([INVALID, INVALID_FAIL], NOW)
        self.assertEqual([r["result"] for r in recs], ["failed"])

    def test_invalid_user_alone_is_kept(self):
        recs = parse_lines([INVALID], NOW)
        self.assertEqual([r["result"] for r in recs], ["invalid_user"])

    def test_keep_invalid_user_flag_keeps_both(self):
        recs = parse_lines([INVALID, INVALID_FAIL], NOW, keep_invalid_user=True)
        self.assertEqual(len(recs), 2)

    def test_mixed_formats_sort_by_time_not_text(self):
        syslog = "Nov  5 11:20:30 pi sshd[9]: Failed password for alice from 192.0.2.10 port 1 ssh2"
        recs = parse_lines([ISO_ACCEPT, syslog, ISO_FAIL], NOW)
        times = [r["timestamp"] for r in recs]
        self.assertEqual(times, sorted(times))
        self.assertEqual(len(recs), 3)


if __name__ == "__main__":
    unittest.main()
