import numpy as np
import pandas as pd

from train_models import get_feature_columns, make_event_splits, top_k_metrics


def make_synthetic_event_frame(n_events: int = 40) -> pd.DataFrame:
    rows = []

    for event_index in range(n_events):
        event_id = f"event-{event_index:03d}"
        high_risk = int(event_index % 5 == 0)

        for horizon in ["early", "3d", "2d", "1d"]:
            rows.append(
                {
                    "event_id": event_id,
                    "horizon": horizon,
                    "high_risk": high_risk,
                    "risk": -4.5 if high_risk else -7.0,
                    "time_to_tca": 3.0,
                    "feature_a": float(event_index),
                    "final_risk": -4.5 if high_risk else -7.0,
                    "final_time_to_tca": 0.1,
                    "requested_horizon_days": 1.0,
                    "meets_requested_horizon": True,
                    "is_horizon_fallback": False,
                }
            )

    return pd.DataFrame(rows)


def test_event_splits_do_not_leak_event_ids_across_splits() -> None:
    df = make_synthetic_event_frame()
    split_df = make_event_splits(df, random_state=7)

    split_events = {
        split: set(split_df.loc[split_df["split"] == split, "event_id"])
        for split in ["train", "validation", "test"]
    }

    assert split_events["train"].isdisjoint(split_events["validation"])
    assert split_events["train"].isdisjoint(split_events["test"])
    assert split_events["validation"].isdisjoint(split_events["test"])

    all_events = set(df["event_id"])
    assert split_events["train"] | split_events["validation"] | split_events["test"] == all_events


def test_feature_columns_exclude_label_and_horizon_metadata() -> None:
    df = make_synthetic_event_frame()
    feature_cols = get_feature_columns(df)

    assert "feature_a" in feature_cols
    assert "risk" in feature_cols
    assert "event_id" not in feature_cols
    assert "horizon" not in feature_cols
    assert "high_risk" not in feature_cols
    assert "final_risk" not in feature_cols
    assert "final_time_to_tca" not in feature_cols
    assert "requested_horizon_days" not in feature_cols
    assert "meets_requested_horizon" not in feature_cols
    assert "is_horizon_fallback" not in feature_cols


def test_top_k_metrics_use_fraction_of_all_test_rows() -> None:
    y_true = np.zeros(100, dtype=int)
    y_true[:3] = 1
    y_prob = np.linspace(1.0, 0.0, 100)

    metrics = top_k_metrics(y_true, y_prob, fractions=(0.05, 0.10))

    assert metrics["precision_top_5"] == 3 / 5
    assert metrics["recall_top_5"] == 1.0
    assert metrics["precision_top_10"] == 3 / 10
    assert metrics["recall_top_10"] == 1.0
