import numpy as np
import pandas as pd
import pytest

from train_models import (
    evaluate_predictions,
    get_feature_columns,
    make_event_splits,
    top_k_metrics,
)


def test_make_event_splits_has_no_event_leakage() -> None:
    n_events = 80
    horizons = ["early", "3d", "2d", "1d"]
    df = pd.DataFrame(
        {
            "event_id": [str(i) for i in range(n_events) for _ in horizons],
            "horizon": horizons * n_events,
            "high_risk": [1 if i % 5 == 0 else 0 for i in range(n_events) for _ in horizons],
            "risk": np.linspace(-8.0, -3.0, n_events * len(horizons)),
        }
    )

    split_df = make_event_splits(df, random_state=7)

    event_split_counts = split_df.groupby("event_id")["split"].nunique()
    assert event_split_counts.max() == 1
    assert set(split_df["split"].unique()) == {"train", "validation", "test"}

    train_events = set(split_df.loc[split_df["split"] == "train", "event_id"])
    val_events = set(split_df.loc[split_df["split"] == "validation", "event_id"])
    test_events = set(split_df.loc[split_df["split"] == "test", "event_id"])

    assert train_events.isdisjoint(val_events)
    assert train_events.isdisjoint(test_events)
    assert val_events.isdisjoint(test_events)


def test_get_feature_columns_excludes_labels_metadata_and_non_numeric_columns() -> None:
    df = pd.DataFrame(
        {
            "event_id": ["a", "b"],
            "horizon": ["1d", "1d"],
            "split": ["train", "test"],
            "high_risk": [0, 1],
            "final_risk": [-8.0, -4.0],
            "final_time_to_tca": [0.2, 0.1],
            "requested_horizon_days": [1.0, 1.0],
            "meets_requested_horizon": [True, True],
            "is_horizon_fallback": [False, False],
            "event_has_pre_tca_row": [True, True],
            "selected_row_is_post_tca": [False, False],
            "final_row_is_post_tca": [False, False],
            "risk": [-7.0, -4.5],
            "miss_distance": [12.0, 5.0],
            "object_name": ["A", "B"],
        }
    )

    feature_cols = get_feature_columns(df)

    assert feature_cols == ["risk", "miss_distance"]


def test_top_k_metrics_capture_expected_positive_rate_and_recall() -> None:
    y_true = np.array([0, 1, 0, 1, 0])
    y_prob = np.array([0.1, 0.9, 0.2, 0.8, 0.3])

    metrics = top_k_metrics(y_true, y_prob, fractions=(0.4,))

    assert metrics["precision_top_40"] == pytest.approx(1.0)
    assert metrics["recall_top_40"] == pytest.approx(1.0)


def test_evaluate_predictions_returns_rare_event_metrics() -> None:
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.05, 0.10, 0.80, 0.90])

    metrics = evaluate_predictions(y_true, y_prob)

    for key in [
        "roc_auc",
        "pr_auc",
        "brier_score",
        "ece",
        "precision_top_1",
        "recall_top_1",
        "precision_top_5",
        "recall_top_5",
        "precision_top_10",
        "recall_top_10",
    ]:
        assert key in metrics

    assert metrics["roc_auc"] == pytest.approx(1.0)
    assert metrics["pr_auc"] == pytest.approx(1.0)
