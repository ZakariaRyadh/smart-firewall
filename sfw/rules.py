"""Hard rules. They run before the model; if one fires, the model is skipped.

Input is the recent knock history of ONE source IP, including the current
knock: a list of (timestamp, ok) sorted by time. `ok` is False for a wrong
knock sequence. Timestamps are datetime objects.

Thresholds are guesses, tune them with attack_sim.
"""
from datetime import timedelta

BLOCK = "block"
HARDER = "harder_knock"

RATE_1MIN_MAX = 5       # more than this in 1 min -> block
RATE_5MIN_MAX = 15      # more than this in 5 min -> block
BAD_KNOCK_STREAK = 3    # this many wrong knocks in a row -> block
TOO_FAST_GAP = 1.0      # seconds between two knocks
TOO_FAST_COUNT = 2      # this many fast gaps ...
TOO_FAST_WINDOW = 10    # ... within this many seconds -> harder knock


def _in_window(knocks, now, seconds):
    start = now - timedelta(seconds=seconds)
    return [(t, ok) for t, ok in knocks if start <= t <= now]


def rate_1min(knocks, now):
    return len(_in_window(knocks, now, 60)) > RATE_1MIN_MAX


def rate_5min(knocks, now):
    return len(_in_window(knocks, now, 300)) > RATE_5MIN_MAX


def bad_knock_x3(knocks, now):
    last = [ok for _, ok in knocks[-BAD_KNOCK_STREAK:]]
    return len(last) == BAD_KNOCK_STREAK and not any(last)


def too_fast(knocks, now):
    times = [t for t, _ in _in_window(knocks, now, TOO_FAST_WINDOW)]
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    return sum(g < TOO_FAST_GAP for g in gaps) >= TOO_FAST_COUNT


# Order matters: block rules first, so block wins over harder knock.
RULES = [
    ("rate_1min", rate_1min, BLOCK),
    ("rate_5min", rate_5min, BLOCK),
    ("bad_knock_x3", bad_knock_x3, BLOCK),
    ("too_fast", too_fast, HARDER),
]


def check_rules(knocks, now):
    """Return (rule_name, action) for the first rule that fires, else None."""
    knocks = sorted(knocks)
    for name, rule, action in RULES:
        if rule(knocks, now):
            return name, action
    return None
