from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


warnings.filterwarnings("ignore")

PROCESSED_DIR = Path("data/processed")
RESULTS_DIR = Path("results")
MODELS_DIR = Path("models")

RESULTS_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

INPUT_PATH = PROCESSED_DIR / "horizon_snapshots.parquet"

EARLY_HORIZONS = ["early", "3d", "2d", "1d"]

EXCLUDE_COLUMNS = {
    "event_id",
    "horizon",
    "high_risk",
    "final_risk",
    "final_collision_risk",
    "final_time_to_tca",

    # Diagnostic metadata, not real CDM prediction features.
    "requested_horizon_days",
    "meets_requested_horizon",
    "is_horizon_fallback",
}


def expected_calibration_error(y_true, y_prob, n_bins=10):
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0

    for left, right in zip(bins[:-1], bins[1:]):
        in_bin = (y_prob >= left) & (y_prob < right)

        if right == 1.0:
            in_bin = (y_prob >= left) & (y_prob <= right)

        if not np.any(in_bin):
            continue

        bin_confidence = y_prob[in_bin].mean()
        bin_accuracy = y_true[in_bin].mean()
        bin_weight = in_bin.mean()

        ece += bin_weight * abs(bin_accuracy - bin_confidence)

    return float(ece)


def top_k_metrics(y_true, y_prob, fractions=(0.01, 0.05, 0.10)):
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    order = np.argsort(-y_prob)
    positives = y_true.sum()

    output = {}

    for frac in fractions:
        k = max(1, int(np.ceil(len(y_true) * frac)))
        selected = order[:k]
        selected_true = y_true[selected]

        label = int(frac * 100)

        output[f"precision_top_{label}"] = float(selected_true.mean())
        output[f"recall_top_{label}"] = (
            float(selected_true.sum() / positives) if positives > 0 else np.nan
        )

    return output


def safe_roc_auc(y_true, y_prob):
    if len(np.unique(y_true)) < 2:
        return np.nan
    return float(roc_auc_score(y_true, y_prob))


def safe_pr_auc(y_true, y_prob):
    if np.asarray(y_true).sum() == 0:
        return np.nan
    return float(average_precision_score(y_true, y_prob))


def evaluate_predictions(y_true, y_prob):
    y_pred = (y_prob >= 0.5).astype(int)

    metrics = {
        "roc_auc": safe_roc_auc(y_true, y_prob),
        "pr_auc": safe_pr_auc(y_true, y_prob),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "ece": expected_calibration_error(y_true, y_prob),
        "precision_0_5": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall_0_5": float(recall_score(y_true, y_pred, zero_division=0)),
    }

    metrics.update(top_k_metrics(y_true, y_prob))
    return metrics


def make_event_splits(df, random_state: int = 42):
    event_labels = (
        df[["event_id", "high_risk"]]
        .drop_duplicates("event_id")
        .reset_index(drop=True)
    )

    stratify = event_labels["high_risk"]

    train_events, temp_events = train_test_split(
        event_labels,
        test_size=0.30,
        random_state=random_state,
        stratify=stratify if stratify.nunique() == 2 else None,
    )

    temp_stratify = temp_events["high_risk"]

    val_events, test_events = train_test_split(
        temp_events,
        test_size=0.50,
        random_state=random_state,
        stratify=temp_stratify if temp_stratify.nunique() == 2 else None,
    )

    split_map = {}

    for event_id in train_events["event_id"]:
        split_map[event_id] = "train"

    for event_id in val_events["event_id"]:
        split_map[event_id] = "validation"

    for event_id in test_events["event_id"]:
        split_map[event_id] = "test"

    df = df.copy()
    df["split"] = df["event_id"].map(split_map)

    return df


def get_feature_columns(df):
    feature_cols = []

    for col in df.columns:
        if col in EXCLUDE_COLUMNS or col == "split":
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            feature_cols.append(col)

    return feature_cols


def build_models():
    return {
        "logistic_regression": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=300,
                        class_weight="balanced",
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "gradient_boosting": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    HistGradientBoostingClassifier(
                        max_iter=300,
                        learning_rate=0.05,
                        random_state=42,
                    ),
                ),
            ]
        ),
    }


def predict_proba(model, x):
    return model.predict_proba(x)[:, 1]


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {INPUT_PATH}. Run python src/preprocess.py first."
        )

    df = pd.read_parquet(INPUT_PATH)

    required = {"event_id", "horizon", "high_risk"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["event_id"] = df["event_id"].astype(str)
    df = df[df["horizon"].isin(EARLY_HORIZONS)].copy()

    df = df.replace([np.inf, -np.inf], np.nan)

    df = make_event_splits(df)
    feature_cols = get_feature_columns(df)

    # Force feature columns to clean numeric values.
    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Replace infinities with missing values.
    df[feature_cols] = df[feature_cols].replace([np.inf, -np.inf], np.nan)

    # RandomForest internally uses float32 in parts of sklearn, so extremely
    # large values can crash even if they are technically finite.
    FLOAT32_SAFE_MAX = 1e30
    df[feature_cols] = df[feature_cols].clip(
        lower=-FLOAT32_SAFE_MAX,
        upper=FLOAT32_SAFE_MAX,
        axis=1,
    )

    # Drop columns that are effectively unusable.
    missing_rate = df[feature_cols].isna().mean()
    feature_cols = [col for col in feature_cols if missing_rate[col] < 0.99]

    nunique = df[feature_cols].nunique(dropna=True)
    feature_cols = [col for col in feature_cols if nunique[col] > 1]

    print("Feature columns:")
    for col in feature_cols:
        print(f"- {col}")

    print(f"\nRows: {len(df):,}")
    print(f"Events: {df['event_id'].nunique():,}")
    print("\nClass balance:")
    print(df[["event_id", "high_risk"]].drop_duplicates()["high_risk"].value_counts())
    print(df[["event_id", "high_risk"]].drop_duplicates()["high_risk"].value_counts(normalize=True))

    rows = []

    for horizon in EARLY_HORIZONS:
        horizon_df = df[df["horizon"] == horizon].copy()

        if horizon_df.empty:
            print(f"\n=== Horizon: {horizon} ===")
            print("No rows found for this horizon. Skipping.")
            continue

        train_df = horizon_df[horizon_df["split"] == "train"]
        val_df = horizon_df[horizon_df["split"] == "validation"]
        test_df = horizon_df[horizon_df["split"] == "test"]

        x_train = train_df[feature_cols]
        y_train = train_df["high_risk"].astype(int).to_numpy()

        print(f"\n=== Horizon: {horizon} ===")
        print(f"Train rows: {len(train_df):,}")
        print(f"Validation rows: {len(val_df):,}")
        print(f"Test rows: {len(test_df):,}")

        # Baseline: use the current CDM risk estimate directly.
        # ESA risk is log10(probability), so convert it back to probability.
        # Higher risk values, such as -4, mean higher collision probability than -6.
        if "risk" in feature_cols:
            for split_name, split_df in [
                ("validation", val_df),
                ("test", test_df),
            ]:
                y = split_df["high_risk"].astype(int).to_numpy()

                risk_log10 = pd.to_numeric(split_df["risk"], errors="coerce")
                risk_log10 = risk_log10.replace([np.inf, -np.inf], np.nan)
                risk_log10 = risk_log10.fillna(risk_log10.median())
                risk_log10 = risk_log10.clip(lower=-30, upper=0)

                y_prob = np.power(10.0, risk_log10.to_numpy())

                metrics = evaluate_predictions(y, y_prob)

                rows.append(
                    {
                        "model": "current_risk_baseline",
                        "horizon": horizon,
                        "split": split_name,
                        "n": len(split_df),
                        "positive_rate": float(y.mean()),
                        **metrics,
                    }
                )

        models = build_models()

        for model_name, model in models.items():
            print(f"Training {model_name} at {horizon}...")

            model.fit(x_train, y_train)

            for split_name, split_df in [
                ("validation", val_df),
                ("test", test_df),
            ]:
                x = split_df[feature_cols]
                y = split_df["high_risk"].astype(int).to_numpy()
                y_prob = predict_proba(model, x)

                metrics = evaluate_predictions(y, y_prob)

                rows.append(
                    {
                        "model": model_name,
                        "horizon": horizon,
                        "split": split_name,
                        "n": len(split_df),
                        "positive_rate": float(y.mean()),
                        **metrics,
                    }
                )

    metrics_df = pd.DataFrame(rows)
    metrics_df.to_csv(RESULTS_DIR / "baseline_metrics.csv", index=False)

    print("\nWrote:")
    print(RESULTS_DIR / "baseline_metrics.csv")

    print("\nTest metrics:")
    print(
        metrics_df[metrics_df["split"] == "test"]
        .sort_values(["horizon", "pr_auc"], ascending=[True, False])
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
