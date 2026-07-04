from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


RESULTS_DIR = Path("results")
FIGURES_DIR = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)

BASELINE_METRICS_PATH = RESULTS_DIR / "baseline_metrics.csv"
CALIBRATION_METRICS_PATH = RESULTS_DIR / "calibration_metrics.csv"
QUANTILE_CURVES_PATH = RESULTS_DIR / "calibration_curves_quantile.csv"
HORIZON_COVERAGE_PATH = RESULTS_DIR / "horizon_coverage.csv"

HORIZON_ORDER = ["early", "3d", "2d", "1d"]
CALIBRATION_MODEL_ORDER = [
    "current_risk_baseline",
    "gradient_boosting_raw",
    "gradient_boosting_sigmoid_calibrated",
]
BASELINE_MODEL_ORDER = [
    "current_risk_baseline",
    "logistic_regression",
    "random_forest",
    "gradient_boosting",
]


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run the relevant experiment script first.")


def save_current_figure(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Wrote {path}")


def prepare_metric_table(
    df: pd.DataFrame,
    metric: str,
    model_order: list[str],
    split: str = "test",
) -> pd.DataFrame:
    required = {"model", "horizon", "split", metric}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns for {metric}: {missing}")

    filtered = df[
        (df["split"] == split)
        & (df["horizon"].isin(HORIZON_ORDER))
        & (df["model"].isin(model_order))
    ].copy()

    filtered["horizon"] = pd.Categorical(
        filtered["horizon"],
        categories=HORIZON_ORDER,
        ordered=True,
    )

    filtered["model"] = pd.Categorical(
        filtered["model"],
        categories=model_order,
        ordered=True,
    )

    filtered = filtered.sort_values(["horizon", "model"])

    table = filtered.pivot(index="horizon", columns="model", values=metric)
    table = table.reindex(HORIZON_ORDER)

    return table


def plot_metric_lines(
    table: pd.DataFrame,
    metric_label: str,
    title: str,
    output_path: Path,
    y_min: float | None = None,
    y_max: float | None = None,
) -> None:
    x = np.arange(len(table.index))

    plt.figure(figsize=(9, 5))

    for model in table.columns:
        y = table[model].to_numpy(dtype=float)
        plt.plot(x, y, marker="o", label=model)

    plt.xticks(x, table.index)
    plt.xlabel("Prediction horizon")
    plt.ylabel(metric_label)
    plt.title(title)

    if y_min is not None or y_max is not None:
        plt.ylim(y_min, y_max)

    plt.grid(True, alpha=0.3)
    plt.legend()
    save_current_figure(output_path)


def plot_pr_auc_by_horizon(baseline_metrics: pd.DataFrame) -> None:
    table = prepare_metric_table(
        baseline_metrics,
        metric="pr_auc",
        model_order=BASELINE_MODEL_ORDER,
    )

    plot_metric_lines(
        table=table,
        metric_label="PR-AUC",
        title="Rare-event ranking performance by horizon",
        output_path=FIGURES_DIR / "pr_auc_by_horizon.png",
        y_min=0.0,
        y_max=1.0,
    )


def plot_top5_recall_by_horizon(baseline_metrics: pd.DataFrame) -> None:
    table = prepare_metric_table(
        baseline_metrics,
        metric="recall_top_5",
        model_order=BASELINE_MODEL_ORDER,
    )

    plot_metric_lines(
        table=table,
        metric_label="Recall in top 5% review set",
        title="High-risk event capture in top 5% by horizon",
        output_path=FIGURES_DIR / "top5_recall_by_horizon.png",
        y_min=0.0,
        y_max=1.05,
    )


def plot_brier_score_by_horizon(calibration_metrics: pd.DataFrame) -> None:
    table = prepare_metric_table(
        calibration_metrics,
        metric="brier_score",
        model_order=CALIBRATION_MODEL_ORDER,
    )

    plot_metric_lines(
        table=table,
        metric_label="Brier score",
        title="Probability quality by horizon",
        output_path=FIGURES_DIR / "brier_score_by_horizon.png",
        y_min=0.0,
        y_max=None,
    )


def plot_ece_by_horizon(calibration_metrics: pd.DataFrame) -> None:
    table = prepare_metric_table(
        calibration_metrics,
        metric="ece",
        model_order=CALIBRATION_MODEL_ORDER,
    )

    plot_metric_lines(
        table=table,
        metric_label="Expected Calibration Error",
        title="Calibration error by horizon",
        output_path=FIGURES_DIR / "ece_by_horizon.png",
        y_min=0.0,
        y_max=None,
    )


def plot_horizon_coverage(horizon_coverage: pd.DataFrame) -> None:
    required = {
        "horizon",
        "median_time_to_tca",
        "percent_meeting_requested_horizon",
        "percent_fallback_rows",
    }
    missing = required - set(horizon_coverage.columns)

    if missing:
        raise ValueError(f"Missing required horizon coverage columns: {missing}")

    df = horizon_coverage[horizon_coverage["horizon"].isin(HORIZON_ORDER)].copy()

    df["horizon"] = pd.Categorical(
        df["horizon"],
        categories=HORIZON_ORDER,
        ordered=True,
    )

    df = df.sort_values("horizon")

    x = np.arange(len(df))

    plt.figure(figsize=(9, 5))
    plt.plot(x, df["median_time_to_tca"], marker="o")
    plt.xticks(x, df["horizon"])
    plt.xlabel("Prediction horizon")
    plt.ylabel("Median time to TCA, days")
    plt.title("Actual timing of selected horizon snapshots")
    plt.grid(True, alpha=0.3)

    save_current_figure(FIGURES_DIR / "horizon_timing.png")

    plt.figure(figsize=(9, 5))
    plt.plot(x, df["percent_meeting_requested_horizon"], marker="o", label="Meets requested horizon")
    plt.plot(x, df["percent_fallback_rows"], marker="o", label="Fallback rows")
    plt.xticks(x, df["horizon"])
    plt.xlabel("Prediction horizon")
    plt.ylabel("Percent of events")
    plt.title("Horizon coverage diagnostics")
    plt.ylim(0.0, 105.0)
    plt.grid(True, alpha=0.3)
    plt.legend()

    save_current_figure(FIGURES_DIR / "horizon_coverage.png")


def plot_quantile_reliability_by_horizon(quantile_curves: pd.DataFrame) -> None:
    required = {
        "model",
        "horizon",
        "split",
        "bin_id",
        "mean_predicted_probability",
        "observed_positive_rate",
    }
    missing = required - set(quantile_curves.columns)

    if missing:
        raise ValueError(f"Missing required quantile curve columns: {missing}")

    model_name = "gradient_boosting_sigmoid_calibrated"

    df = quantile_curves[
        (quantile_curves["split"] == "test")
        & (quantile_curves["model"] == model_name)
        & (quantile_curves["horizon"].isin(HORIZON_ORDER))
    ].copy()

    df = df.dropna(
        subset=[
            "mean_predicted_probability",
            "observed_positive_rate",
        ]
    )

    df["horizon"] = pd.Categorical(
        df["horizon"],
        categories=HORIZON_ORDER,
        ordered=True,
    )

    df = df.sort_values(["horizon", "bin_id"])

    plt.figure(figsize=(8, 6))

    for horizon in HORIZON_ORDER:
        horizon_df = df[df["horizon"] == horizon]

        if horizon_df.empty:
            continue

        plt.plot(
            horizon_df["mean_predicted_probability"],
            horizon_df["observed_positive_rate"],
            marker="o",
            label=horizon,
        )

    max_value = max(
        float(df["mean_predicted_probability"].max()),
        float(df["observed_positive_rate"].max()),
        0.01,
    )

    plt.plot([0, max_value], [0, max_value], linestyle="--", label="Perfect calibration")

    plt.xlabel("Mean predicted probability")
    plt.ylabel("Observed high-risk rate")
    plt.title("Quantile-binned reliability: calibrated gradient boosting")
    plt.xlim(0.0, max_value)
    plt.ylim(0.0, max_value)
    plt.grid(True, alpha=0.3)
    plt.legend()

    save_current_figure(FIGURES_DIR / "quantile_reliability_by_horizon.png")


def plot_quantile_reliability_comparison_1d(quantile_curves: pd.DataFrame) -> None:
    required = {
        "model",
        "horizon",
        "split",
        "bin_id",
        "mean_predicted_probability",
        "observed_positive_rate",
    }
    missing = required - set(quantile_curves.columns)

    if missing:
        raise ValueError(f"Missing required quantile curve columns: {missing}")

    model_order = [
        "current_risk_baseline",
        "gradient_boosting_raw",
        "gradient_boosting_sigmoid_calibrated",
    ]

    df = quantile_curves[
        (quantile_curves["split"] == "test")
        & (quantile_curves["horizon"] == "1d")
        & (quantile_curves["model"].isin(model_order))
    ].copy()

    df = df.dropna(
        subset=[
            "mean_predicted_probability",
            "observed_positive_rate",
        ]
    )

    df["model"] = pd.Categorical(
        df["model"],
        categories=model_order,
        ordered=True,
    )

    df = df.sort_values(["model", "bin_id"])

    plt.figure(figsize=(8, 6))

    for model in model_order:
        model_df = df[df["model"] == model]

        if model_df.empty:
            continue

        plt.plot(
            model_df["mean_predicted_probability"],
            model_df["observed_positive_rate"],
            marker="o",
            label=model,
        )

    max_value = max(
        float(df["mean_predicted_probability"].max()),
        float(df["observed_positive_rate"].max()),
        0.01,
    )

    plt.plot([0, max_value], [0, max_value], linestyle="--", label="Perfect calibration")

    plt.xlabel("Mean predicted probability")
    plt.ylabel("Observed high-risk rate")
    plt.title("Quantile-binned reliability comparison at 1d")
    plt.xlim(0.0, max_value)
    plt.ylim(0.0, max_value)
    plt.grid(True, alpha=0.3)
    plt.legend()

    save_current_figure(FIGURES_DIR / "quantile_reliability_comparison_1d.png")


def write_summary_tables(
    baseline_metrics: pd.DataFrame,
    calibration_metrics: pd.DataFrame,
) -> None:
    baseline_test = baseline_metrics[
        (baseline_metrics["split"] == "test")
        & (baseline_metrics["horizon"].isin(HORIZON_ORDER))
    ].copy()

    calibration_test = calibration_metrics[
        (calibration_metrics["split"] == "test")
        & (calibration_metrics["horizon"].isin(HORIZON_ORDER))
    ].copy()

    baseline_summary = baseline_test[
        [
            "model",
            "horizon",
            "positive_rate",
            "roc_auc",
            "pr_auc",
            "precision_top_1",
            "recall_top_1",
            "precision_top_5",
            "recall_top_5",
            "precision_top_10",
            "recall_top_10",
        ]
    ].sort_values(["horizon", "pr_auc"], ascending=[True, False])

    calibration_summary = calibration_test[
        [
            "model",
            "horizon",
            "positive_rate",
            "roc_auc",
            "pr_auc",
            "brier_score",
            "ece",
            "precision_top_5",
            "recall_top_5",
        ]
    ].sort_values(["horizon", "model"])

    baseline_summary.to_csv(RESULTS_DIR / "baseline_test_summary.csv", index=False)
    calibration_summary.to_csv(RESULTS_DIR / "calibration_test_summary.csv", index=False)

    print(f"Wrote {RESULTS_DIR / 'baseline_test_summary.csv'}")
    print(f"Wrote {RESULTS_DIR / 'calibration_test_summary.csv'}")


def main() -> None:
    require_file(BASELINE_METRICS_PATH)
    require_file(CALIBRATION_METRICS_PATH)
    require_file(QUANTILE_CURVES_PATH)

    baseline_metrics = pd.read_csv(BASELINE_METRICS_PATH)
    calibration_metrics = pd.read_csv(CALIBRATION_METRICS_PATH)
    quantile_curves = pd.read_csv(QUANTILE_CURVES_PATH)

    plot_pr_auc_by_horizon(baseline_metrics)
    plot_top5_recall_by_horizon(baseline_metrics)
    plot_brier_score_by_horizon(calibration_metrics)
    plot_ece_by_horizon(calibration_metrics)
    plot_quantile_reliability_by_horizon(quantile_curves)
    plot_quantile_reliability_comparison_1d(quantile_curves)

    if HORIZON_COVERAGE_PATH.exists():
        horizon_coverage = pd.read_csv(HORIZON_COVERAGE_PATH)
        plot_horizon_coverage(horizon_coverage)
    else:
        print(f"Skipping horizon coverage figures because {HORIZON_COVERAGE_PATH} is missing.")

    write_summary_tables(
        baseline_metrics=baseline_metrics,
        calibration_metrics=calibration_metrics,
    )


if __name__ == "__main__":
    main()