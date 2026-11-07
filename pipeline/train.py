"""Train the Isolation Forest and save it. Run from the repo root:

    python -m pipeline.train
    python -m pipeline.train --out models/model_v2.joblib
"""
import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from sfw.features import FEATURES, build_features

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# Setup noise on the Pi (wrong usernames, many fails): not normal behavior.
NOISE_START = pd.Timestamp("2026-10-23 15:10", tz="+01:00")
NOISE_END = pd.Timestamp("2026-10-23 15:30", tz="+01:00")


def load_normal():
    """Normal rows: real without the setup noise, and synthetic."""
    real = pd.read_json(DATA / "real.jsonl", lines=True)
    noise = (real["timestamp"] >= NOISE_START) & (real["timestamp"] <= NOISE_END)
    real = real[~noise]

    synth_files = sorted(DATA.glob("synthetic*.jsonl"))
    synth = pd.concat([pd.read_json(f, lines=True) for f in synth_files],
                      ignore_index=True)
    return real, synth, len(synth_files)


def load_training_features():
    real, synth, n_files = load_normal()

    # Real and synthetic are separate timelines, features are built per table.
    train = pd.concat([build_features(real)[FEATURES],
                       build_features(synth)[FEATURES]], ignore_index=True)
    print(f"real {len(real)} + synthetic {len(synth)} ({n_files} files)"
          f" = {len(train)} rows")
    return train


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "models" / "model.joblib"))
    args = ap.parse_args()

    train = load_training_features()
    model = IsolationForest(n_estimators=200, random_state=42).fit(train)

    scores = model.score_samples(train)
    p5 = np.percentile(scores, 5)
    lowest = scores.min()
    print(f"allow above {p5:.4f}, block below {lowest:.4f}")

    joblib.dump({"model": model, "p5": p5, "lowest": lowest,
                 "features": FEATURES}, args.out)
    print("saved", args.out)


if __name__ == "__main__":
    main()
