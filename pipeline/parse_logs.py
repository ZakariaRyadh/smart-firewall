"""Turn the Pi's SSH log into one clean row per login event.

Run from the repo root (the Pi log is root-owned, so use sudo there):

    python -m pipeline.parse_logs --log ssh.log                 # table on screen
    python -m pipeline.parse_logs --log ssh.log --json          # JSON lines on screen
    python -m pipeline.parse_logs --log ssh.log --out data/real.jsonl

Real logs never go in git. Only this script does.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("Africa/Algiers")
DEFAULT_LOG = "/opt/smart-firewall/ssh-logs/ssh.log"

TS = r"(?P<ts>\d{4}-\d{2}-\d{2}T[\d:.+-]+|[A-Z][a-z]{2}\s+\d+\s[\d:]{8})"
PROC = r"\S+\s+sshd(?:-session)?\[\d+\]:\s"
IP = r"(?P<ip>[0-9a-fA-F.:]+)"
PATTERNS = [
    (re.compile(TS + r"\s+" + PROC + r"Accepted (?P<method>\S+) for (?P<user>\S+) from " + IP + r" port (?P<port>\d+)"), "accepted"),
    (re.compile(TS + r"\s+" + PROC + r"Failed (?P<method>\S+) for (?:invalid user )?(?P<user>\S+) from " + IP + r" port (?P<port>\d+)"), "failed"),
    (re.compile(TS + r"\s+" + PROC + r"Invalid user (?P<user>\S+) from " + IP + r"(?: port (?P<port>\d+))?"), "invalid_user"),
]


def parse_ts(s, now=None):
    """Return a tz-aware datetime in Algiers time.

    ISO stamps carry their own offset and are converted. Old syslog stamps
    ("Nov  5 10:00:03") have no year and no zone: assume Algiers time, take
    the current year, and go back one year if that lands in the future
    (a December line read in January).
    """
    now = now or datetime.now(LOCAL)
    if "T" in s:
        t = datetime.fromisoformat(s)
        if t.tzinfo is None:
            return t.replace(tzinfo=LOCAL)
        return t.astimezone(LOCAL)
    t = datetime.strptime(f"{now.year} {s}", "%Y %b %d %H:%M:%S").replace(tzinfo=LOCAL)
    if t > now + timedelta(days=1):
        t = t.replace(year=t.year - 1)
    return t


def parse_lines(lines, now=None, keep_invalid_user=False):
    """Parse log lines into records, oldest first.

    One bad login with an unknown username writes two lines: "Invalid user X"
    then "Failed password for invalid user X" (same port). That is one
    attempt, so the invalid_user row is dropped when a failed row for the
    same ip, user and port exists. Pass keep_invalid_user=True to keep both.
    """
    items = []  # (datetime, record)
    for line in lines:
        for rx, result in PATTERNS:
            m = rx.search(line)
            if not m:
                continue
            d = m.groupdict()
            t = parse_ts(d["ts"], now)
            items.append((t, {
                "timestamp": t.isoformat(),
                "day_of_week": t.strftime("%A"),
                "hour": t.hour,
                "source_ip": d["ip"],
                "user": d["user"],
                "result": result,
                "auth_method": d.get("method") or "none",
                "port": d.get("port") or "",
            }))
            break

    items.sort(key=lambda x: x[0])  # sort by time, not by text
    records = [r for _, r in items]

    if not keep_invalid_user:
        failed = {(r["source_ip"], r["user"], r["port"])
                  for r in records if r["result"] == "failed" and r["port"]}
        records = [r for r in records
                   if not (r["result"] == "invalid_user" and r["port"]
                           and (r["source_ip"], r["user"], r["port"]) in failed)]
    return records


def print_table(records):
    print(f"{'TIMESTAMP':<27}{'DAY':<11}{'HR':<4}{'SOURCE_IP':<18}{'USER':<12}{'RESULT':<14}{'METHOD'}")
    print("-" * 95)
    for r in records:
        print(f"{r['timestamp']:<27}{r['day_of_week']:<11}{r['hour']:<4}{r['source_ip']:<18}"
              f"{r['user']:<12}{r['result']:<14}{r['auth_method']}")
    print(f"\nTotal: {len(records)} records")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--log", default=DEFAULT_LOG, help="SSH log file to read")
    ap.add_argument("--out", help="write JSON lines to this file instead of the screen")
    ap.add_argument("--json", action="store_true", help="print JSON lines instead of the table")
    ap.add_argument("--keep-invalid-user", action="store_true",
                    help="keep 'Invalid user' rows that a 'Failed' row already covers")
    args = ap.parse_args(argv)

    with open(args.log, errors="ignore") as f:
        records = parse_lines(f, keep_invalid_user=args.keep_invalid_user)

    if args.out:
        with open(args.out, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"Wrote {len(records)} records to {args.out}", file=sys.stderr)
    elif args.json:
        for r in records:
            print(json.dumps(r))
    else:
        print_table(records)


if __name__ == "__main__":
    main()
