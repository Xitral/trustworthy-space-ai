from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
OUT_DIR = Path("results")
OUT_DIR.mkdir(exist_ok=True)


def find_file(name_part: str, *, required: bool = True) -> Path | None:
    matches = sorted(RAW_DIR.glob(f"*{name_part}*"))

    if not matches:
        if required:
            raise FileNotFoundError(f"No file containing '{name_part}' found in {RAW_DIR}")
        return None

    return matches[0]


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".zip":
        return pd.read_csv(path, compression="zip")
    raise ValueError(f"Unsupported file type: {path}")


def summarize(df: pd.DataFrame, name: str) -> None:
    print(f"\n=== {name} ===")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns):,}")
    print("\nColumns:")
    for col in df.columns:
        print(f"- {col}")

    summary = pd.DataFrame(
        {
            "column": df.columns,
            "dtype": [str(df[col].dtype) for col in df.columns],
            "missing_count": [df[col].isna().sum() for col in df.columns],
            "missing_rate": [df[col].isna().mean() for col in df.columns],
            "unique_count": [df[col].nunique(dropna=True) for col in df.columns],
        }
    )

    summary.to_csv(OUT_DIR / f"{name}_column_summary.csv", index=False)

    if "event_id" in df.columns:
        event_counts = df.groupby("event_id").size()
        print(f"\nUnique events: {df['event_id'].nunique():,}")
        print(f"Median CDMs per event: {event_counts.median():.1f}")
        print(f"Max CDMs per event: {event_counts.max():,}")

    if "risk" in df.columns:
        print("\nRisk summary:")
        print(df["risk"].describe())

    if "time_to_tca" in df.columns:
        print("\nTime-to-TCA summary:")
        print(df["time_to_tca"].describe())


def write_column_comparison(train: pd.DataFrame, test: pd.DataFrame) -> None:
    shared_cols = sorted(set(train.columns) & set(test.columns))
    train_only = sorted(set(train.columns) - set(test.columns))
    test_only = sorted(set(test.columns) - set(train.columns))

    pd.DataFrame({"shared_columns": shared_cols}).to_csv(
        OUT_DIR / "shared_columns.csv",
        index=False,
    )
    pd.DataFrame({"train_only_columns": train_only}).to_csv(
        OUT_DIR / "train_only_columns.csv",
        index=False,
    )
    pd.DataFrame({"test_only_columns": test_only}).to_csv(
        OUT_DIR / "test_only_columns.csv",
        index=False,
    )

    print("\n=== Column comparison ===")
    print(f"Shared columns: {len(shared_cols)}")
    print(f"Train-only columns: {train_only}")
    print(f"Test-only columns: {test_only}")


def main() -> None:
    train_path = find_file("train")
    test_path = find_file("test", required=False)

    print(f"Train file: {train_path}")

    train = load_table(train_path)
    summarize(train, "train")

    if test_path is None:
        print("\nNo optional raw test file found. Skipping test-data inspection and column comparison.")
        return

    print(f"Test file: {test_path}")
    test = load_table(test_path)
    summarize(test, "test")
    write_column_comparison(train, test)


if __name__ == "__main__":
    main()
