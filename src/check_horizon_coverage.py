from pathlib import Path

import numpy as np
import pandas as pd


PROCESSED_DIR = Path("data/processed")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

INPUT_PATH = PROCESSED_DIR / "horizon_snapshots.parquet"
OUTPUT_PATH = RESULTS_DIR / "horizon_coverage.csv"

REQUESTED_HORIZONS = {
    "7d": 7.0,
    "3d": 3.0,
    "2d": 2.0,
    "1d": 1.0,
    "final": 0.0,
}


def summarize_horizon_coverage(df: pd.DataFrame) -> pd.DataFrame:
    required = {"event_id", "horizon", "time_to_tca"}

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()
    df["event_id"] = df["event_id"].astype(str)
    df["time_to_tca"] = pd.to_numeric(df["time_to_tca"], errors="coerce")

    rows = []

    for horizon, requested_days in REQUESTED_HORIZONS.items():
        horizon_df = df[df["horizon"] == horizon].copy()

        if horizon_df.empty:
            rows.append(
                {
                    "horizon": horizon,
                    "requested_days_before_tca": requested_days,
                    "rows": 0,
                    "unique_events": 0,
                    "median_time_to_tca": np.nan,
                    "min_time_to_tca": np.nan,
                    "max_time_to_tca": np.nan,
                    "p10_time_to_tca": np.nan,
                    "p90_time_to_tca": np.nan,
                    "percent_meeting_requested_horizon": np.nan,
                    "percent_fallback_rows": np.nan,
                }
            )
            continue

        valid_time = horizon_df["time_to_tca"].dropna()

        if horizon == "final":
            meets_requested = pd.Series(True, index=horizon_df.index)
            fallback_rows = pd.Series(False, index=horizon_df.index)
        else:
            meets_requested = horizon_df["time_to_tca"] >= requested_days
            fallback_rows = ~meets_requested

        rows.append(
            {
                "horizon": horizon,
                "requested_days_before_tca": requested_days,
                "rows": len(horizon_df),
                "unique_events": horizon_df["event_id"].nunique(),
                "median_time_to_tca": valid_time.median(),
                "min_time_to_tca": valid_time.min(),
                "max_time_to_tca": valid_time.max(),
                "p10_time_to_tca": valid_time.quantile(0.10),
                "p90_time_to_tca": valid_time.quantile(0.90),
                "percent_meeting_requested_horizon": meets_requested.mean() * 100,
                "percent_fallback_rows": fallback_rows.mean() * 100,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {INPUT_PATH}. Run python src/preprocess.py first."
        )

    df = pd.read_parquet(INPUT_PATH)
    coverage = summarize_horizon_coverage(df)

    coverage.to_csv(OUTPUT_PATH, index=False)

    print("\nHorizon coverage:")
    print(coverage.to_string(index=False))

    print("\nWrote:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()