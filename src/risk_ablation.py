from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import warnings

from joblib import Parallel, delayed
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from train_models import (
    EARLY_HORIZONS,
    evaluate_predictions,
    get_feature_columns,
    make_event_splits,
)

try:
    from threadpoolctl import threadpool_limits
except Exception:

    @contextmanager
    def threadpool_limits(limits=None):
        yield


warnings.filterwarnings("ignore")

PROCESSED_DIR = Path("data/processed")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

INPUT_PATH = PROCESSED_DIR / "horizon_snapshots.parquet"
METRICS_OUTPUT_PATH = RESULTS_DIR / "risk_ablation_metrics.csv"
SUMMARY_OUTPUT_PATH = RESULTS_DIR / "risk_ablation_summary.csv"
DELTAS_OUTPUT_PATH = RESULTS_DIR / "risk_ablation_deltas.csv"

DEFAULT_N_SPLITS = 20
DEFAULT_START_SEED = 42
DEFAULT_MAX_ITER = 150
DEFAULT_N_JOBS = max(1, min(4, (os.cpu_count() or 2) - 1))
DEFAULT_BACKEND = "loky"

MODEL_ORDER = [
    "current_risk_baseline",
    "gradient_boosting_with_risk",
    "gradient_boosting_without_risk",
]

SUMMARY_METRICS = [
    "positive_rate",
    "roc_auc",
    "pr_auc",
    "brier_score",
    "ece",
    "precision_top_5",
    "recall_top_5",
    "precision_top_10",
    "recall_top_10",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run current-risk feature ablation across repeated event-level splits."
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=DEFAULT_N_SPLITS,
        help="Number of repeated event-level splits.",
    )
    parser.add_argument(
        "--start-seed",
        type=int,
        default=DEFAULT_START_SEED,
        help="First split seed. Later splits use consecutive seeds.",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=DEFAULT_MAX_ITER,
        help="HistGradientBoosting max_iter for ablation models.",
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=DEFAULT_N_JOBS,
        help="Parallel split/horizon workers. Use 1 for serial execution.",
    )
    parser.add_argument(
        "--backend",
        choices=["loky", "threading"],
        default=DEFAULT_BACKEND,
        help="Joblib backend. 'threading' can be faster on Windows laptops.",
    )
    return parser.parse_args()


def build_gradient_boosting_model(random_state: int, max_iter: int) -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                HistGradientBoostingClassifier(
                    max_iter=max_iter,
                    learning_rate=0.05,
                    random_state=random_state,
                ),
            ),
        ]
    )


def sanitize_features(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()

    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[feature_cols] = df[feature_cols].replace([np.inf, -np.inf], np.nan)
    df[feature_cols] = df[feature_cols].clip(lower=-1e30, upper=1e30, axis=1)

    missing_rate = df[feature_cols].isna().mean()
    feature_cols = [col for col in feature_cols if missing_rate[col] < 0.99]

    nunique = df[feature_cols].nunique(dropna=True)
    feature_cols = [col for col in feature_cols if nunique[col] > 1]

    return df, feature_cols


def current_risk_probability(split_df: pd.DataFrame) -> np.ndarray:
    risk_log10 = pd.to_numeric(split_df["risk"], errors="coerce")
    risk_log10 = risk_log10.replace([np.inf, -np.inf], np.nan)
    risk_log10 = risk_log10.fillna(risk_log10.median())
    risk_log10 = risk_log10.clip(lower=-30, upper=0)
    return np.power(10.0, risk_log10.to_numpy())


def add_metric_row(
    rows: list[dict],
    split_seed: int,
    model_name: str,
    horizon: str,
    test_df: pd.DataFrame,
    y_prob: np.ndarray,
) -> None:
    y = test_df["high_risk"].astype(int).to_numpy()
    rows.append(
        {
            "split_seed": split_seed,
            "model": model_name,
            "horizon": horizon,
            "split": "test",
            "n": len(test_df),
            "positives": int(y.sum()),
            "positive_rate": float(y.mean()),
            **evaluate_predictions(y, y_prob),
        }
    )


def run_horizon_job(
    job_index: int,
    total_jobs: int,
    split_index: int,
    split_seed: int,
    n_splits: int,
    horizon_index: int,
    horizon: str,
    horizon_df: pd.DataFrame,
    feature_cols_with_risk: list[str],
    feature_cols_without_risk: list[str],
    max_iter: int,
) -> list[dict]:
    metrics_rows = []

    print(
        f"[{job_index}/{total_jobs}] split {split_index}/{n_splits} "
        f"seed={split_seed} horizon={horizon}"
    )

    train_df = horizon_df[horizon_df["split"] == "train"]
    test_df = horizon_df[horizon_df["split"] == "test"]

    y_train = train_df["high_risk"].astype(int).to_numpy()
    y_test = test_df["high_risk"].astype(int).to_numpy()

    print(
        f"{horizon}: train={len(train_df):,}, test={len(test_df):,}, "
        f"test positives={int(y_test.sum())}"
    )

    if len(np.unique(y_train)) < 2:
        print("Training split has one class. Skipping horizon.")
        return metrics_rows

    with threadpool_limits(limits=1):
        current_prob = current_risk_probability(test_df)
        add_metric_row(
            rows=metrics_rows,
            split_seed=split_seed,
            model_name="current_risk_baseline",
            horizon=horizon,
            test_df=test_df,
            y_prob=current_prob,
        )

        model_seed = split_seed + horizon_index * 1000

        model_with_risk = build_gradient_boosting_model(model_seed, max_iter)
        model_with_risk.fit(
            train_df[feature_cols_with_risk].to_numpy(),
            y_train,
        )
        with_risk_prob = model_with_risk.predict_proba(
            test_df[feature_cols_with_risk].to_numpy()
        )[:, 1]
        add_metric_row(
            rows=metrics_rows,
            split_seed=split_seed,
            model_name="gradient_boosting_with_risk",
            horizon=horizon,
            test_df=test_df,
            y_prob=with_risk_prob,
        )

        model_without_risk = build_gradient_boosting_model(model_seed + 101, max_iter)
        model_without_risk.fit(
            train_df[feature_cols_without_risk].to_numpy(),
            y_train,
        )
        without_risk_prob = model_without_risk.predict_proba(
            test_df[feature_cols_without_risk].to_numpy()
        )[:, 1]
        add_metric_row(
            rows=metrics_rows,
            split_seed=split_seed,
            model_name="gradient_boosting_without_risk",
            horizon=horizon,
            test_df=test_df,
            y_prob=without_risk_prob,
        )

    return metrics_rows


def build_horizon_jobs(df: pd.DataFrame, split_seeds: list[int]) -> list[dict]:
    jobs = []
    total_jobs = len(split_seeds) * len(EARLY_HORIZONS)
    job_index = 0

    for split_index, split_seed in enumerate(split_seeds, start=1):
        split_df = make_event_splits(df, random_state=split_seed)

        for horizon_index, horizon in enumerate(EARLY_HORIZONS):
            job_index += 1
            horizon_df = split_df[split_df["horizon"] == horizon].copy()
            jobs.append(
                {
                    "job_index": job_index,
                    "total_jobs": total_jobs,
                    "split_index": split_index,
                    "split_seed": split_seed,
                    "horizon_index": horizon_index,
                    "horizon": horizon,
                    "horizon_df": horizon_df,
                }
            )

    return jobs


def summarize_metric_rows(metrics_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        metrics_df.groupby(["model", "horizon", "split"])[SUMMARY_METRICS]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.columns = [
        "_".join(col).strip("_") if isinstance(col, tuple) else col
        for col in summary.columns
    ]

    split_counts = (
        metrics_df.groupby(["model", "horizon", "split"])["split_seed"]
        .nunique()
        .reset_index(name="n_repeated_splits")
    )

    return summary.merge(split_counts, on=["model", "horizon", "split"], how="left")


def build_delta_rows(metrics_df: pd.DataFrame) -> pd.DataFrame:
    pivot = metrics_df.pivot_table(
        index=["split_seed", "horizon", "split"],
        columns="model",
        values=["pr_auc", "recall_top_5", "recall_top_10"],
    )

    rows = []
    for (split_seed, horizon, split), row in pivot.iterrows():
        output = {
            "split_seed": split_seed,
            "horizon": horizon,
            "split": split,
        }

        for metric in ["pr_auc", "recall_top_5", "recall_top_10"]:
            current = row[(metric, "current_risk_baseline")]
            with_risk = row[(metric, "gradient_boosting_with_risk")]
            without_risk = row[(metric, "gradient_boosting_without_risk")]

            output[f"{metric}_with_risk_minus_current_risk"] = with_risk - current
            output[f"{metric}_with_risk_minus_without_risk"] = with_risk - without_risk
            output[f"{metric}_without_risk_minus_current_risk"] = without_risk - current

        rows.append(output)

    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()

    if args.n_splits < 1:
        raise ValueError("--n-splits must be at least 1.")

    if args.n_jobs == 0:
        raise ValueError("--n-jobs cannot be 0. Use 1, -1, or a positive worker count.")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing {INPUT_PATH}. Run python src/preprocess.py first.")

    df = pd.read_parquet(INPUT_PATH)
    required = {"event_id", "horizon", "high_risk", "risk"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["event_id"] = df["event_id"].astype(str)
    df = df[df["horizon"].isin(EARLY_HORIZONS)].copy()
    df = df.replace([np.inf, -np.inf], np.nan)

    feature_cols = get_feature_columns(df)
    df, feature_cols_with_risk = sanitize_features(df, feature_cols)
    feature_cols_without_risk = [col for col in feature_cols_with_risk if col != "risk"]

    if "risk" not in feature_cols_with_risk:
        raise ValueError("Expected current CDM risk feature named 'risk' to be present.")

    if not feature_cols_without_risk:
        raise ValueError("No non-risk feature columns remain for the ablation model.")

    print("\nRisk ablation feature sets:")
    print(f"- with current risk: {len(feature_cols_with_risk)} feature(s)")
    print(f"- without current risk: {len(feature_cols_without_risk)} feature(s)")

    split_seeds = [args.start_seed + i for i in range(args.n_splits)]
    jobs = build_horizon_jobs(df=df, split_seeds=split_seeds)

    print("\nRisk ablation configuration:")
    print(f"- splits: {args.n_splits}")
    print(f"- horizons: {len(EARLY_HORIZONS)}")
    print(f"- split/horizon jobs: {len(jobs)}")
    print(f"- max_iter: {args.max_iter}")
    print(f"- n_jobs: {args.n_jobs}")
    print(f"- backend: {args.backend}")

    if args.n_jobs == 1:
        results = [
            run_horizon_job(
                job_index=job["job_index"],
                total_jobs=job["total_jobs"],
                split_index=job["split_index"],
                split_seed=job["split_seed"],
                n_splits=args.n_splits,
                horizon_index=job["horizon_index"],
                horizon=job["horizon"],
                horizon_df=job["horizon_df"],
                feature_cols_with_risk=feature_cols_with_risk,
                feature_cols_without_risk=feature_cols_without_risk,
                max_iter=args.max_iter,
            )
            for job in jobs
        ]
    else:
        results = Parallel(n_jobs=args.n_jobs, backend=args.backend, verbose=10)(
            delayed(run_horizon_job)(
                job_index=job["job_index"],
                total_jobs=job["total_jobs"],
                split_index=job["split_index"],
                split_seed=job["split_seed"],
                n_splits=args.n_splits,
                horizon_index=job["horizon_index"],
                horizon=job["horizon"],
                horizon_df=job["horizon_df"],
                feature_cols_with_risk=feature_cols_with_risk,
                feature_cols_without_risk=feature_cols_without_risk,
                max_iter=args.max_iter,
            )
            for job in jobs
        )

    metrics_rows = []
    for job_metric_rows in results:
        metrics_rows.extend(job_metric_rows)

    metrics_df = pd.DataFrame(metrics_rows)
    summary_df = summarize_metric_rows(metrics_df)
    deltas_df = build_delta_rows(metrics_df)

    metrics_df.to_csv(METRICS_OUTPUT_PATH, index=False)
    summary_df.to_csv(SUMMARY_OUTPUT_PATH, index=False)
    deltas_df.to_csv(DELTAS_OUTPUT_PATH, index=False)

    print("\nWrote:")
    print(METRICS_OUTPUT_PATH)
    print(SUMMARY_OUTPUT_PATH)
    print(DELTAS_OUTPUT_PATH)

    print("\nRisk ablation metric summary:")
    print(
        summary_df.sort_values(["horizon", "pr_auc_mean"], ascending=[True, False])
        .to_string(index=False)
    )

    print("\nRisk ablation delta summary:")
    delta_summary = deltas_df.groupby(["horizon", "split"]).agg(["mean", "std"])
    delta_summary.columns = ["_".join(col).strip("_") for col in delta_summary.columns]
    print(delta_summary.reset_index().to_string(index=False))


if __name__ == "__main__":
    main()
