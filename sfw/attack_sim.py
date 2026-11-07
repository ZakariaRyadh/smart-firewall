"""Generated attacks for testing the gateway. All data is made by us.

    from sfw.attack_sim import generate
    atk = generate("burst", 50, seed=100, known_ips=[...])

Returns one row per knock: timestamp, source_ip, scenario, episode, source.
Known IPs are passed in so no real IP lives in git. Keep a tuning seed and a
separate seed for the final test set.
"""
import random

import pandas as pd

START = pd.Timestamp("2026-11-07", tz="+01:00")
DAYS = 14

# scenario: (hours (lo, hi), knocks per episode (lo, hi), gap seconds (lo, hi),
#            source IP: "new" or "known")
SCENARIOS = {
    "night_unknown": {"hours": (1, 5),  "knocks": (1, 1),   "gap": (0, 0),   "ip": "new"},
    "vpn_source":    {"hours": (9, 18), "knocks": (1, 1),   "gap": (0, 0),   "ip": "new"},
    "slow_known":    {"hours": (9, 18), "knocks": (1, 1),   "gap": (0, 0),   "ip": "known"},
    "burst":         {"hours": (9, 18), "knocks": (20, 40), "gap": (1, 2),   "ip": "known"},
    "volume":        {"hours": (9, 18), "knocks": (25, 35), "gap": (5, 15),  "ip": "known"},
    "slow_volume":   {"hours": (9, 18), "knocks": (25, 35), "gap": (14, 20), "ip": "known"},
}


def _new_ip(rng):
    return (f"{rng.randint(11, 99)}.{rng.randint(0, 255)}."
            f"{rng.randint(0, 255)}.{rng.randint(1, 254)}")


def generate(scenario, n, seed, known_ips=()):
    """n episodes of one scenario. Same seed gives the same rows."""
    cfg = SCENARIOS[scenario]
    if cfg["ip"] == "known" and not known_ips:
        raise ValueError(f"{scenario} needs known_ips")
    rng = random.Random(seed)
    rows = []
    for ep in range(n):
        day = START + pd.Timedelta(days=rng.randint(0, DAYS - 1))
        t = day + pd.Timedelta(hours=rng.randint(*cfg["hours"]),
                               minutes=rng.randint(0, 59),
                               seconds=rng.randint(0, 59))
        ip = _new_ip(rng) if cfg["ip"] == "new" else rng.choice(list(known_ips))
        for _ in range(rng.randint(*cfg["knocks"])):
            rows.append({"timestamp": t, "source_ip": ip, "scenario": scenario,
                         "episode": ep, "source": "attack_sim"})
            t += pd.Timedelta(seconds=rng.randint(*cfg["gap"]))
    return pd.DataFrame(rows)
