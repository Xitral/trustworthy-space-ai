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

from train_models import EARLY_HORIZONS, evaluate_predictions, get_feature_columns, make_event_splits

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
METRICS_OUTPUT_PATH = RESULTS_DIR / "repeated_split_metrics.csv"
METRICS_SUMMARY_OUTPUT_PATH = RESULTS_DIR / "repeated_split_summary.csv"
ESCALATION_OUTPUT_PATH = RESULTS_DIR / "repeated_split_escalation.csv"
ESCALATION_SUMMARY_OUTPUT_PATH = RESULTS_DIR / "repeated_split_escalation_summary.csv"

DEFAULT_N_SPLITS = 20
DEFAULT_N_BOOTSTRAPS = 10
DEFAULT_START_SEED = 42
DEFAULT_MAX_ITER = 150
DEFAULT_N_JOBS = max(1, min(4, (os.cpu_count() or 2) - 1))
DEFAULT_BACKEND = "loky"
ESCALATION_FRACTIONS = [0.05, 0.10, 0.20, 0.30]
EXTRA_EXCLUDE_COLUMNS = {"final_time_to_tca", "requested_horizon_days", "meets_requested_horizon", "is_horizon_fallback"}
SUMMARY_METRICS = ["positive_rate", "roc_auc", "pr_auc", "brier_score", "ece", "precision_top_5", "recall_top_5", "precision_top_10", "recall_top_10"]
ESCALATION_SUMMARY_METRICS = ["coverage_rate", "positives_total", "positives_escalated", "positive_escalation_rate"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeated event-level split robustness evaluation.")
    parser.add_argument("--n-splits", type=int, default=DEFAULT_N_SPLITS, help="Number of repeated event-level splits.")
    parser.add_argument("--n-bootstraps", type=int, default=DEFAULT_N_BOOTSTRAPS, help="Number of bootstrap ensemble members per split/horizon.")
    parser.add_argument("--start-seed", type=int, default=DEFAULT_START_SEED, help="First split seed. Later splits use consecutive seeds.")
    parser.add_argument("--max-iter", type=int, default=DEFAULT_MAX_ITER, help="HistGradientBoosting max_iter for repeated-split models.")
    parser.add_argument("--n-jobs", type=int, default=DEFAULT_N_JOBS, help="Parallel split/horizon workers. Use 1 for serial execution or a positive number such as 4, 6, or 8.")
    parser.add_argument("--backend", choices=["loky", "threading"], default=DEFAULT_BACKEND, help="Joblib backend. 'loky' uses processes. 'threading' avoids copying DataFrames on Windows.")
    parser.add_argument("--skip-uncertainty", action="store_true", help="Skip bootstrap uncertainty escalation and only run repeated ranking metrics.")
    return parser.parse_args()


def build_gradient_boosting_model(random_state: int, max_iter: int) -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", HistGradientBoostingClassifier(max_iter=max_iter, learning_rate=0.05, random_state=random_state)),
    ])


def sanitize_features(df: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()
    feature_cols = [col for col in feature_cols if col not in EXTRA_EXCLUDE_COLUMNS]
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


def bootstrap_ensemble_predict(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, n_bootstraps: int, random_seed: int, max_iter: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(random_seed)
    predictions = []
    attempts = 0
    max_attempts = n_bootstraps * 10
    while len(predictions) < n_bootstraps and attempts < max_attempts:
        attempts += 1
        sample_indices = rng.integers(low=0, high=len(y_train), size=len(y_train))
        y_sample = y_train[sample_indices]
        if len(np.unique(y_sample)) < 2:
            continue
        model = build_gradient_boosting_model(random_state=random_seed + attempts, max_iter=max_iter)
        model.fit(x_train[sample_indices], y_sample)
        predictions.append(model.predict_proba(x_test)[:, 1])
    if not predictions:
        raise RuntimeError("Could not fit any bootstrap models.")
    all_predictions = np.vstack(predictions)
    return all_predictions.mean(axis=0), all_predictions.std(axis=0)


def add_metric_row(rows: list[dict], split_seed: int, model_name: str, horizon: str, test_df: pd.DataFrame, y_prob: np.ndarray) -> None:
    y = test_df["high_risk"].astype(int).to_numpy()
    rows.append({
        "split_seed": split_seed,
        "model": model_name,
        "horizon": horizon,
        "split": "test",
        "n": len(test_df),
        "positives": int(y.sum()),
        "positive_rate": float(y.mean()),
        **evaluate_predictions(y, y_prob),
    })


def positive_escalation_row(split_seed: int, horizon: str, policy: str, fraction: float, y_true: np.ndarray, score: np.ndarray) -> dict:
    y_true = np.asarray(y_true)
    score = np.asarray(score)
    n_escalated = max(1, int(np.ceil(len(y_true) * fraction)))
    selected = np.argsort(-score)[:n_escalated]
    positives_total = int(y_true.sum())
    positives_escalated = int(y_true[selected].sum())
    return {
        "split_seed": split_seed,
        "horizon": horizon,
        "split": "test",
        "policy": policy,
        "escalated_fraction": fraction,
        "coverage_rate": float(1.0 - n_escalated / len(y_true)),
        "test_n": int(len(y_true)),
        "escalated_n": int(n_escalated),
        "positives_total": positives_total,
        "positives_escalated": positives_escalated,
        "positive_escalation_rate": float(positives_escalated / positives_total) if positives_total > 0 else np.nan,
    }


def run_horizon_job(job_index: int, total_jobs: int, split_index: int, split_seed: int, n_splits: int, horizon_index: int, horizon: str, horizon_df: pd.DataFrame, feature_cols: list[str], n_bootstraps: int, max_iter: int, skip_uncertainty: bool) -> tuple[list[dict], list[dict]]:
    metrics_rows = []
    escalation_rows = []
    print(f"[{job_index}/{total_jobs}] split {split_index}/{n_splits} seed={split_seed} horizon={horizon}")
    if horizon_df.empty:
        print(f"Skipping empty horizon {horizon}.")
        return metrics_rows, escalation_rows

    train_df = horizon_df[horizon_df["split"] == "train"]
    test_df = horizon_df[horizon_df["split"] == "test"]
    y_train = train_df["high_risk"].astype(int).to_numpy()
    y_test = test_df["high_risk"].astype(int).to_numpy()
    print(f"{horizon}: train={len(train_df):,}, test={len(test_df):,}, test positives={int(y_test.sum())}")
    if len(np.unique(y_train)) < 2:
        print("Training split has one class. Skipping horizon.")
        return metrics_rows, escalation_rows

    x_train = train_df[feature_cols].to_numpy()
    x_test = test_df[feature_cols].to_numpy()

    with threadpool_limits(limits=1):
        current_prob = current_risk_probability(test_df)
        add_metric_row(metrics_rows, split_seed, "current_risk_baseline", horizon, test_df, current_prob)

        model_seed = split_seed + horizon_index * 1000
        gb_model = build_gradient_boosting_model(random_state=model_seed, max_iter=max_iter)
        gb_model.fit(x_train, y_train)
        gb_prob = gb_model.predict_proba(x_test)[:, 1]
        add_metric_row(metrics_rows, split_seed, "gradient_boosting", horizon, test_df, gb_prob)

        rng = np.random.default_rng(split_seed + horizon_index * 10_000)
        random_scores = rng.random(len(test_df))
        for fraction in ESCALATION_FRACTIONS:
            escalation_rows.append(positive_escalation_row(split_seed, horizon, "random_escalation", fraction, y_test, random_scores))
            escalation_rows.append(positive_escalation_row(split_seed, horizon, "current_risk_escalation", fraction, y_test, current_prob))

        if skip_uncertainty:
            return metrics_rows, escalation_rows

        bootstrap_seed = split_seed + horizon_index * 100_000
        ensemble_mean_prob, ensemble_std_prob = bootstrap_ensemble_predict(x_train, y_train, x_test, n_bootstraps, bootstrap_seed, max_iter)
        add_metric_row(metrics_rows, split_seed, "bootstrap_gradient_boosting_ensemble", horizon, test_df, ensemble_mean_prob)
        for fraction in ESCALATION_FRACTIONS:
            escalation_rows.append(positive_escalation_row(split_seed, horizon, "bootstrap_uncertainty_escalation", fraction, y_test, ensemble_std_prob))
    return metrics_rows, escalation_rows


def build_horizon_jobs(df: pd.DataFrame, split_seeds: list[int]) -> list[dict]:
    jobs = []
    total_jobs = len(split_seeds) * len(EARLY_HORIZONS)
    job_index = 0
    for split_index, split_seed in enumerate(split_seeds, start=1):
        split_df = make_event_splits(df, random_state=split_seed)
        for horizon_index, horizon in enumerate(EARLY_HORIZONS):
            job_index += 1
            jobs.append({
                "job_index": job_index,
                "total_jobs": total_jobs,
                "split_index": split_index,
                "split_seed": split_seed,
                "horizon_index": horizon_index,
                "horizon": horizon,
                "horizon_df": split_df[split_df["horizon"] == horizon].copy(),
            })
    return jobs


def summarize_metric_rows(metrics_df: pd.DataFrame) -> pd.DataFrame:
    summary = metrics_df.groupby(["model", "horizon", "split"])[SUMMARY_METRICS].agg(["mean", "std"]).reset_index()
    summary.columns = ["_".join(col).strip("_") if isinstance(col, tuple) else col for col in summary.columns]
    split_counts = metrics_df.groupby(["model", "horizon", "split"])["split_seed"].nunique().reset_index(name="n_repeated_splits")
    return summary.merge(split_counts, on=["model", "horizon", "split"], how="left")


def summarize_escalation_rows(escalation_df: pd.DataFrame) -> pd.DataFrame:
    if escalation_df.empty:
        return pd.DataFrame()
    summary = escalation_df.groupby(["policy", "horizon", "split", "escalated_fraction"])[ESCALATION_SUMMARY_METRICS].agg(["mean", "std"]).reset_index()
    summary.columns = ["_".join(col).strip("_") if isinstance(col, tuple) else col for col in summary.columns]
    split_counts = escalation_df.groupby(["policy", "horizon", "split", "escalated_fraction"])["split_seed"].nunique().reset_index(name="n_repeated_splits")
    return summary.merge(split_counts, on=["policy", "horizon", "split", "escalated_fraction"], how="left")


def main() -> None:
    args = parse_args()
    if args.n_splits < 1:
        raise ValueError("--n-splits must be at least 1.")
    if args.n_bootstraps < 1 and not args.skip_uncertainty:
        raise ValueError("--n-bootstraps must be at least 1 unless uncertainty is skipped.")
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
    df, feature_cols = sanitize_features(df, feature_cols)

    print("Repeated split feature columns:")
    for col in feature_cols:
        print(f"- {col}")

    split_seeds = [args.start_seed + i for i in range(args.n_splits)]
    jobs = build_horizon_jobs(df=df, split_seeds=split_seeds)
    print("\nRepeated split configuration:")
    print(f"- splits: {args.n_splits}")
    print(f"- horizons: {len(EARLY_HORIZONS)}")
    print(f"- split/horizon jobs: {len(jobs)}")
    print(f"- bootstraps per split/horizon: {args.n_bootstraps}")
    print(f"- max_iter: {args.max_iter}")
    print(f"- n_jobs: {args.n_jobs}")
    print(f"- backend: {args.backend}")
    print(f"- skip_uncertainty: {args.skip_uncertainty}")

    if args.n_jobs == 1:
        results = [
            run_horizon_job(job["job_index"], job["total_jobs"], job["split_index"], job["split_seed"], args.n_splits, job["horizon_index"], job["horizon"], job["horizon_df"], feature_cols, args.n_bootstraps, args.max_iter, args.skip_uncertainty)
            for job in jobs
        ]
    else:
        results = Parallel(n_jobs=args.n_jobs, backend=args.backend, verbose=10)(
            delayed(run_horizon_job)(job["job_index"], job["total_jobs"], job["split_index"], job["split_seed"], args.n_splits, job["horizon_index"], job["horizon"], job["horizon_df"], feature_cols, args.n_bootstraps, args.max_iter, args.skip_uncertainty)
            for job in jobs
        )

    metrics_rows = []
    escalation_rows = []
    for job_metric_rows, job_escalation_rows in results:
        metrics_rows.extend(job_metric_rows)
        escalation_rows.extend(job_escalation_rows)

    metrics_df = pd.DataFrame(metrics_rows)
    escalation_df = pd.DataFrame(escalation_rows)
    summary_df = summarize_metric_rows(metrics_df)
    escalation_summary_df = summarize_escalation_rows(escalation_df)
    metrics_df.to_csv(METRICS_OUTPUT_PATH, index=False)
    summary_df.to_csv(METRICS_SUMMARY_OUTPUT_PATH, index=False)
    escalation_df.to_csv(ESCALATION_OUTPUT_PATH, index=False)
    escalation_summary_df.to_csv(ESCALATION_SUMMARY_OUTPUT_PATH, index=False)

    print("\nWrote:")
    print(METRICS_OUTPUT_PATH)
    print(METRICS_SUMMARY_OUTPUT_PATH)
    print(ESCALATION_OUTPUT_PATH)
    print(ESCALATION_SUMMARY_OUTPUT_PATH)
    print("\nRepeated split metric summary:")
    print(summary_df.sort_values(["horizon", "pr_auc_mean"], ascending=[True, False]).to_string(index=False))
    if not escalation_summary_df.empty:
        print("\nRepeated split escalation summary:")
        print(
            escalation_summary_df[escalation_summary_df["escalated_fraction"].isin([0.10, 0.20, 0.30])]
            .sort_values(["horizon", "escalated_fraction", "positive_escalation_rate_mean"], ascending=[True, True, False])
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
