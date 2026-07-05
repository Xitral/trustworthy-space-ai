from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_STEPS = [
    {
        "name": "Inspect raw data",
        "script": "src/inspect_data.py",
        "optional": False,
    },
    {
        "name": "Preprocess horizon snapshots",
        "script": "src/preprocess.py",
        "optional": False,
    },
    {
        "name": "Check horizon coverage",
        "script": "src/check_horizon_coverage.py",
        "optional": False,
    },
    {
        "name": "Train baseline models",
        "script": "src/train_models.py",
        "optional": False,
    },
    {
        "name": "Calibrate models",
        "script": "src/calibrate_models.py",
        "optional": False,
    },
    {
        "name": "Run Bayesian logistic baseline",
        "script": "src/bayesian_logistic.py",
        "optional": False,
    },
    {
        "name": "Run uncertainty experiment",
        "script": "src/uncertainty.py",
        "optional": False,
    },
    {
        "name": "Run repeated split robustness evaluation",
        "script": "src/repeated_splits.py",
        "optional": False,
    },
    {
        "name": "Generate figures and summary tables",
        "script": "src/make_figures.py",
        "optional": False,
    },
]


CORE_EXPECTED_OUTPUTS = [
    "data/processed/event_labels.csv",
    "data/processed/horizon_snapshots.parquet",
    "results/horizon_coverage.csv",
    "results/horizon_post_tca_diagnostics.csv",
    "results/baseline_metrics.csv",
    "results/calibration_metrics.csv",
    "results/calibration_curves.csv",
    "results/calibration_curves_quantile.csv",
    "results/bayesian_logistic_metrics.csv",
    "results/bayesian_logistic_predictions.csv",
    "results/baseline_test_summary.csv",
    "results/calibration_test_summary.csv",
]

UNCERTAINTY_EXPECTED_OUTPUTS = [
    "results/uncertainty_metrics.csv",
    "results/uncertainty_abstention.csv",
    "results/uncertainty_predictions.csv",
    "results/uncertainty_test_summary.csv",
    "results/uncertainty_abstention_test_summary.csv",
]

REPEATED_SPLIT_EXPECTED_OUTPUTS = [
    "results/repeated_split_metrics.csv",
    "results/repeated_split_summary.csv",
    "results/repeated_split_escalation.csv",
    "results/repeated_split_escalation_summary.csv",
    "figures/repeated_split_pr_auc.png",
    "figures/repeated_split_top5_recall.png",
    "figures/repeated_split_escalation_10pct.png",
]

FIGURE_EXPECTED_OUTPUTS = [
    "figures/pr_auc_by_horizon.png",
    "figures/top5_recall_by_horizon.png",
    "figures/brier_score_by_horizon.png",
    "figures/ece_by_horizon.png",
    "figures/quantile_reliability_by_horizon.png",
    "figures/quantile_reliability_comparison_1d.png",
    "figures/horizon_timing.png",
    "figures/horizon_coverage.png",
    "figures/uncertainty_positive_vs_negative.png",
    "figures/positive_escalation_rate.png",
    "figures/uncertainty_abstention_coverage.png",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full BEACON experiment pipeline."
    )

    parser.add_argument(
        "--skip-inspect",
        action="store_true",
        help="Skip raw data inspection.",
    )

    parser.add_argument(
        "--skip-uncertainty",
        action="store_true",
        help="Skip bootstrap uncertainty estimation.",
    )

    parser.add_argument(
        "--skip-repeated-splits",
        action="store_true",
        help="Skip repeated event-level split robustness evaluation.",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue running later steps after a failed step.",
    )

    parser.add_argument(
        "--repeated-n-splits",
        type=int,
        default=None,
        help="Override repeated_splits.py --n-splits.",
    )

    parser.add_argument(
        "--repeated-n-bootstraps",
        type=int,
        default=None,
        help="Override repeated_splits.py --n-bootstraps.",
    )

    parser.add_argument(
        "--repeated-max-iter",
        type=int,
        default=None,
        help="Override repeated_splits.py --max-iter.",
    )

    parser.add_argument(
        "--repeated-n-jobs",
        type=int,
        default=None,
        help="Override repeated_splits.py --n-jobs.",
    )

    parser.add_argument(
        "--repeated-backend",
        choices=["loky", "threading"],
        default=None,
        help="Override repeated_splits.py --backend.",
    )

    parser.add_argument(
        "--repeated-skip-uncertainty",
        action="store_true",
        help="Pass --skip-uncertainty to repeated_splits.py only.",
    )

    return parser.parse_args()


def repeated_split_args(args: argparse.Namespace) -> list[str]:
    command_args = []

    if args.repeated_n_splits is not None:
        command_args.extend(["--n-splits", str(args.repeated_n_splits)])

    if args.repeated_n_bootstraps is not None:
        command_args.extend(["--n-bootstraps", str(args.repeated_n_bootstraps)])

    if args.repeated_max_iter is not None:
        command_args.extend(["--max-iter", str(args.repeated_max_iter)])

    if args.repeated_n_jobs is not None:
        command_args.extend(["--n-jobs", str(args.repeated_n_jobs)])

    if args.repeated_backend is not None:
        command_args.extend(["--backend", args.repeated_backend])

    if args.repeated_skip_uncertainty:
        command_args.append("--skip-uncertainty")

    return command_args


def build_steps(args: argparse.Namespace) -> list[dict]:
    steps = []

    for step in DEFAULT_STEPS:
        if args.skip_inspect and step["script"] == "src/inspect_data.py":
            continue

        if args.skip_uncertainty and step["script"] == "src/uncertainty.py":
            continue

        if args.skip_repeated_splits and step["script"] == "src/repeated_splits.py":
            continue

        step_copy = dict(step)

        if step_copy["script"] == "src/repeated_splits.py":
            step_copy["args"] = repeated_split_args(args)
        else:
            step_copy["args"] = []

        steps.append(step_copy)

    return steps


def expected_outputs(args: argparse.Namespace) -> list[str]:
    outputs = []
    outputs.extend(CORE_EXPECTED_OUTPUTS)

    if not args.skip_uncertainty:
        outputs.extend(UNCERTAINTY_EXPECTED_OUTPUTS)

    if not args.skip_repeated_splits:
        outputs.extend(REPEATED_SPLIT_EXPECTED_OUTPUTS)

    outputs.extend(FIGURE_EXPECTED_OUTPUTS)

    return outputs


def ensure_script_exists(script_path: str) -> None:
    path = REPO_ROOT / script_path

    if not path.exists():
        raise FileNotFoundError(f"Missing required script: {script_path}")


def run_step(step: dict) -> bool:
    name = step["name"]
    script = step["script"]
    step_args = step.get("args", [])

    ensure_script_exists(script)

    command = [sys.executable, "-u", script, *step_args]

    env = os.environ.copy()

    existing_pythonpath = env.get("PYTHONPATH", "")
    src_path = str(REPO_ROOT / "src")

    if existing_pythonpath:
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing_pythonpath}"
    else:
        env["PYTHONPATH"] = src_path

    print("\n" + "=" * 80)
    print(f"Running: {name}")
    print(f"Command: {' '.join(command)}")
    print("=" * 80)

    start_time = time.perf_counter()

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
    )

    elapsed = time.perf_counter() - start_time

    if result.returncode == 0:
        print(f"\nFinished: {name} in {elapsed:.1f} seconds")
        return True

    print(f"\nFailed: {name}")
    print(f"Exit code: {result.returncode}")
    print(f"Elapsed: {elapsed:.1f} seconds")

    return False


def print_output_summary(args: argparse.Namespace) -> None:
    print("\n" + "=" * 80)
    print("Pipeline output summary")
    print("=" * 80)

    found = []
    missing = []

    for output in expected_outputs(args):
        path = REPO_ROOT / output

        if path.exists():
            found.append(output)
        else:
            missing.append(output)

    print("\nFound outputs:")
    for output in found:
        print(f"  ✓ {output}")

    if missing:
        print("\nMissing outputs:")
        for output in missing:
            print(f"  - {output}")
    else:
        print("\nAll expected outputs were found.")


def main() -> None:
    args = parse_args()
    steps = build_steps(args)

    print("BEACON full experiment pipeline")
    print(f"Repository root: {REPO_ROOT}")
    print(f"Python executable: {sys.executable}")

    failed_steps = []

    pipeline_start = time.perf_counter()

    for step in steps:
        success = run_step(step)

        if not success:
            failed_steps.append(step["name"])

            if not args.continue_on_error:
                print("\nStopping pipeline because a step failed.")
                print("Use --continue-on-error to run later steps anyway.")
                print_output_summary(args)
                sys.exit(1)

    total_elapsed = time.perf_counter() - pipeline_start

    print("\n" + "=" * 80)

    if failed_steps:
        print("Pipeline finished with failed steps:")
        for step_name in failed_steps:
            print(f"  - {step_name}")
        print(f"Total elapsed time: {total_elapsed:.1f} seconds")
        print_output_summary(args)
        sys.exit(1)

    print("Pipeline completed successfully.")
    print(f"Total elapsed time: {total_elapsed:.1f} seconds")

    print_output_summary(args)


if __name__ == "__main__":
    main()
