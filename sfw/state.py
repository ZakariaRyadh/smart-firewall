"""Live state in SQLite: knocks, known IPs, decisions.

The gateway hook starts fresh on every knock, so it keeps its memory here.
Order for one knock:

    feats = live_features(db, ip, now)     # before recording this knock
    record_knock(db, ip, now, ok)
    knocks = recent_knocks(db, ip, now)    # includes this knock, for the rules
    d = decide(bundle, feats, knocks, now)
    log_decision(db, ip, now, d)
    if d.action == "allow": mark_known(db, ip, now)

`now` must be a timezone-aware datetime (local time, so hour and weekday
match training). Times are stored as epoch seconds.
Only normal history and allowed knocks make an IP known, so an attacker never
becomes known by knocking.
"""
import sqlite3
from datetime import datetime, timezone

from sfw.features import CAP_SECONDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS knocks (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, ip TEXT NOT NULL, ok INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS knocks_ip_ts ON knocks (ip, ts);
CREATE TABLE IF NOT EXISTS known_ips (
    ip TEXT PRIMARY KEY, first_seen REAL NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, ip TEXT NOT NULL,
    action TEXT NOT NULL, reason TEXT NOT NULL, score REAL);
"""


def connect(path):
    """Open (and create) the database. Use ':memory:' in tests."""
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")  # dashboard can read while the hook writes
    db.executescript(SCHEMA)
    return db


def record_knock(db, ip, now, ok=True):
    with db:
        db.execute("INSERT INTO knocks (ts, ip, ok) VALUES (?, ?, ?)",
                   (now.timestamp(), ip, int(ok)))


def mark_known(db, ip, now):
    with db:
        db.execute("INSERT OR IGNORE INTO known_ips (ip, first_seen) VALUES (?, ?)",
                   (ip, now.timestamp()))


def is_known(db, ip):
    return db.execute("SELECT 1 FROM known_ips WHERE ip = ?", (ip,)).fetchone() is not None


def recent_knocks(db, ip, now, seconds=300):
    """(datetime, ok) of this IP in the last `seconds`, oldest first."""
    rows = db.execute(
        "SELECT ts, ok FROM knocks WHERE ip = ? AND ts >= ? AND ts <= ? ORDER BY ts, id",
        (ip, now.timestamp() - seconds, now.timestamp())).fetchall()
    return [(datetime.fromtimestamp(ts, timezone.utc), bool(ok)) for ts, ok in rows]


def live_features(db, ip, now):
    """The same 5 features as sfw.features.build_features, for one knock.

    Call it BEFORE record_knock, so this knock is not counted.
    """
    t = now.timestamp()
    last = db.execute("SELECT MAX(ts) FROM knocks WHERE ip = ? AND ts <= ?",
                      (ip, t)).fetchone()[0]
    gap = CAP_SECONDS if last is None else min(t - last, CAP_SECONDS)
    attempts = db.execute(
        "SELECT COUNT(*) FROM knocks WHERE ip = ? AND ts < ? AND ts >= ?",
        (ip, t, t - 300)).fetchone()[0]
    return {"hour": now.hour, "dow": now.weekday(),
            "is_known_ip": int(is_known(db, ip)),
            "time_since_last": gap, "attempts_last_5min": attempts}


def log_decision(db, ip, now, decision):
    with db:
        db.execute("INSERT INTO decisions (ts, ip, action, reason, score) "
                   "VALUES (?, ?, ?, ?, ?)",
                   (now.timestamp(), ip, decision.action, decision.reason,
                    decision.score))
