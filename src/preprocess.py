from pathlib import Path

import numpy as np
import pandas as pd


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
RESULTS_DIR = Path("results")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# "early" means earliest available CDM for the event.
# Requested horizons choose the closest available CDM at or before that many days before TCA.
# "final" means closest available CDM to TCA, preferably before TCA.
HORIZONS = {
    "early": None,
    "3d": 3.0,
    "2d": 2.0,
    "1d": 1.0,
    "final": 0.0,
}

# ESA risk is log10(probability), so -5 means 10^-5.
HIGH_RISK_THRESHOLD_LOG10 = -5.0

POST_TCA_DIAGNOSTICS_PATH = RESULTS_DIR / "horizon_post_tca_diagnostics.csv"


def find_file(name_part: str) -> Path:
    matches = sorted(RAW_DIR.glob(f"*{name_part}*"))

    if not matches:
        raise FileNotFoundError(f"No file containing '{name_part}' found in {RAW_DIR}")

    return matches[0]


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path)

    if path.suffix == ".zip":
        return pd.read_csv(path, compression="zip")

    raise ValueError(f"Unsupported file type: {path}")


def validate_columns(df: pd.DataFrame) -> None:
    required = {"event_id", "time_to_tca", "risk"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    print("Required columns found: event_id, time_to_tca, risk")


def clean_base_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["event_id"] = df["event_id"].astype(str)
    df["time_to_tca"] = pd.to_numeric(df["time_to_tca"], errors="coerce")
    df["risk"] = pd.to_numeric(df["risk"], errors="coerce")

    df = df.dropna(subset=["event_id", "time_to_tca", "risk"])

    return df


def prefer_pre_tca_rows(event_df: pd.DataFrame) -> pd.DataFrame:
    pre_tca = event_df[event_df["time_to_tca"] >= 0].copy()

    if len(pre_tca) > 0:
        return pre_tca

    return event_df.copy()


def event_has_pre_tca_row(event_df: pd.DataFrame) -> bool:
    return bool((event_df["time_to_tca"] >= 0).any())


def select_final_row(event_df: pd.DataFrame) -> pd.Series:
    candidate_df = prefer_pre_tca_rows(event_df)

    # Closest to TCA, preferably without using post-TCA rows.
    return candidate_df.sort_values("time_to_tca", ascending=True).iloc[0]


def select_early_row(event_df: pd.DataFrame) -> pd.Series:
    candidate_df = prefer_pre_tca_rows(event_df)

    # Earliest available CDM, meaning farthest before TCA.
    return candidate_df.sort_values("time_to_tca", ascending=False).iloc[0]


def select_requested_horizon_row(
    event_df: pd.DataFrame,
    requested_days: float,
) -> tuple[pd.Series, bool, bool]:
    candidate_df = prefer_pre_tca_rows(event_df)

    eligible = candidate_df[candidate_df["time_to_tca"] >= requested_days]

    if len(eligible) > 0:
        # Closest available CDM at or before the requested warning horizon.
        row = eligible.sort_values("time_to_tca", ascending=True).iloc[0]
        return row, True, False

    # Fallback: event does not reach the requested horizon.
    # Use earliest available CDM and record that this was a fallback.
    row = candidate_df.sort_values("time_to_tca", ascending=False).iloc[0]
    return row, False, True


def select_horizon_row(
    event_df: pd.DataFrame,
    horizon_name: str,
    requested_days: float | None,
) -> tuple[pd.Series, bool, bool]:
    if horizon_name == "early":
        row = select_early_row(event_df)
        return row, True, False

    if horizon_name == "final":
        row = select_final_row(event_df)
        return row, True, False

    if requested_days is None:
        raise ValueError(f"Requested days cannot be None for horizon {horizon_name}")

    return select_requested_horizon_row(event_df, requested_days)


def get_final_event_risk(train: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for event_id, event_df in train.groupby("event_id"):
        final_row = select_final_row(event_df)

        rows.append(
            {
                "event_id": str(event_id),
                "final_risk": final_row["risk"],
                "final_time_to_tca": final_row["time_to_tca"],
                "final_row_is_post_tca": bool(final_row["time_to_tca"] < 0),
            }
        )

    final_risk = pd.DataFrame(rows)

    final_risk["high_risk"] = (
        final_risk["final_risk"] >= HIGH_RISK_THRESHOLD_LOG10
    ).astype(int)

    return final_risk


def build_horizon_snapshots(
    train: pd.DataFrame,
    final_risk: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for event_id, event_df in train.groupby("event_id"):
        has_pre_tca = event_has_pre_tca_row(event_df)

        for horizon_name, requested_days in HORIZONS.items():
            selected_row, meets_requested, is_fallback = select_horizon_row(
                event_df=event_df,
                horizon_name=horizon_name,
                requested_days=requested_days,
            )

            row = selected_row.copy()
            row["event_id"] = str(event_id)
            row["horizon"] = horizon_name
            row["requested_horizon_days"] = (
                np.nan if requested_days is None else requested_days
            )
            row["meets_requested_horizon"] = bool(meets_requested)
            row["is_horizon_fallback"] = bool(is_fallback)
            row["event_has_pre_tca_row"] = bool(has_pre_tca)
            row["selected_row_is_post_tca"] = bool(row["time_to_tca"] < 0)

            rows.append(row)

    snapshots = pd.DataFrame(rows)
    snapshots = snapshots.merge(final_risk, on="event_id", how="left")

    return snapshots


def build_post_tca_diagnostics(snapshots: pd.DataFrame) -> pd.DataFrame:
    diagnostics = (
        snapshots.groupby("horizon")
        .agg(
            rows=("event_id", "count"),
            unique_events=("event_id", "nunique"),
            post_tca_rows=("selected_row_is_post_tca", "sum"),
            fallback_rows=("is_horizon_fallback", "sum"),
            events_without_pre_tca=("event_has_pre_tca_row", lambda x: int((~x).sum())),
            min_time_to_tca=("time_to_tca", "min"),
            median_time_to_tca=("time_to_tca", "median"),
            max_time_to_tca=("time_to_tca", "max"),
        )
        .reset_index()
    )

    diagnostics["percent_post_tca_rows"] = (
        diagnostics["post_tca_rows"] / diagnostics["rows"] * 100.0
    )
    diagnostics["percent_events_without_pre_tca"] = (
        diagnostics["events_without_pre_tca"] / diagnostics["rows"] * 100.0
    )

    return diagnostics


def print_horizon_summary(snapshots: pd.DataFrame) -> None:
    print("\nHorizon snapshot counts:")
    print(snapshots["horizon"].value_counts().sort_index())

    print("\nHorizon timing summary:")
    summary = (
        snapshots.groupby("horizon")
        .agg(
            rows=("event_id", "count"),
            unique_events=("event_id", "nunique"),
            median_time_to_tca=("time_to_tca", "median"),
            min_time_to_tca=("time_to_tca", "min"),
            max_time_to_tca=("time_to_tca", "max"),
            percent_meeting_requested_horizon=(
                "meets_requested_horizon",
                lambda x: float(x.mean() * 100),
            ),
            percent_fallback_rows=(
                "is_horizon_fallback",
                lambda x: float(x.mean() * 100),
            ),
        )
        .reset_index()
    )

    print(summary.to_string(index=False))


def main() -> None:
    train_path = find_file("train")
    train = load_table(train_path)

    print(f"Loaded train data from {train_path}")
    print(f"Rows: {len(train):,}")
    print(f"Columns: {len(train.columns):,}")

    validate_columns(train)

    train = clean_base_columns(train)

    final_risk = get_final_event_risk(train)
    snapshots = build_horizon_snapshots(train, final_risk)
    post_tca_diagnostics = build_post_tca_diagnostics(snapshots)

    final_risk.to_csv(PROCESSED_DIR / "event_labels.csv", index=False)
    snapshots.to_parquet(PROCESSED_DIR / "horizon_snapshots.parquet", index=False)
    post_tca_diagnostics.to_csv(POST_TCA_DIAGNOSTICS_PATH, index=False)

    print("\nWrote:")
    print(PROCESSED_DIR / "event_labels.csv")
    print(PROCESSED_DIR / "horizon_snapshots.parquet")
    print(POST_TCA_DIAGNOSTICS_PATH)

    print("\nEvent label summary:")
    print(final_risk["high_risk"].value_counts(normalize=True).rename("rate"))
    print(final_risk["high_risk"].value_counts().rename("count"))

    print_horizon_summary(snapshots)

    print("\nPost-TCA selected-row diagnostics:")
    print(post_tca_diagnostics.to_string(index=False))


if __name__ == "__main__":
    main()
