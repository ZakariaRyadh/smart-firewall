"""Features shared by training and the live gateway.

Each feature only looks at earlier rows, so the live hook sees the same
numbers the model was trained on.
"""
import pandas as pd

FEATURES = ["hour", "dow", "is_known_ip", "time_since_last", "attempts_last_5min"]

CAP_SECONDS = 604800  # 7 days, also used for an IP's first-ever row


def build_features(df):
    """df needs the columns `timestamp` (tz-aware) and `source_ip`."""
    df = df.sort_values("timestamp").copy()
    df["hour"] = df["timestamp"].dt.hour
    df["dow"] = df["timestamp"].dt.day_of_week
    df["is_known_ip"] = df.duplicated("source_ip").astype(int)

    gap = df.groupby("source_ip")["timestamp"].diff().dt.total_seconds()
    df["time_since_last"] = gap.fillna(CAP_SECONDS).clip(upper=CAP_SECONDS)

    def count_recent(row):
        same_ip = df["source_ip"] == row["source_ip"]
        before = df["timestamp"] < row["timestamp"]
        recent = df["timestamp"] >= row["timestamp"] - pd.Timedelta(minutes=5)
        return (same_ip & before & recent).sum()

    df["attempts_last_5min"] = df.apply(count_recent, axis=1)
    return df
