"""One decision per knock: hard rules first, then the model bands.

`bundle` is the dict saved by pipeline/train.py (model, p5, lowest, features).
`feature_row` is a dict with the FEATURES for the current knock.
`knocks` is the recent history of that IP, see sfw/rules.py.
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from sfw.rules import BLOCK, HARDER, check_rules

ALLOW = "allow"


@dataclass
class Decision:
    action: str                    # allow, harder_knock or block
    reason: str                    # rule name, or "model"
    score: Optional[float] = None  # None when a rule fired (model skipped)


def decide(bundle, feature_row, knocks, now):
    hit = check_rules(knocks, now)
    if hit:
        name, action = hit
        return Decision(action, name)

    row = pd.DataFrame([feature_row])[bundle["features"]]
    score = float(bundle["model"].score_samples(row)[0])
    if score > bundle["p5"]:
        action = ALLOW
    elif score >= bundle["lowest"]:
        action = HARDER
    else:
        action = BLOCK
    return Decision(action, "model", score)
