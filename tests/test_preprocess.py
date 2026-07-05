import pandas as pd

from preprocess import (
    build_post_tca_diagnostics,
    select_final_row,
    select_requested_horizon_row,
)


def test_final_row_prefers_pre_tca_when_available() -> None:
    event_df = pd.DataFrame(
        {
            "event_id": ["a", "a", "a"],
            "time_to_tca": [2.0, 0.2, -0.1],
            "risk": [-7.0, -6.0, -4.0],
        }
    )

    final_row = select_final_row(event_df)

    assert final_row["time_to_tca"] == 0.2
    assert final_row["risk"] == -6.0


def test_requested_horizon_uses_earliest_pre_tca_fallback() -> None:
    event_df = pd.DataFrame(
        {
            "event_id": ["a", "a"],
            "time_to_tca": [1.5, 0.2],
            "risk": [-7.0, -6.0],
        }
    )

    selected_row, meets_requested, is_fallback = select_requested_horizon_row(
        event_df,
        requested_days=3.0,
    )

    assert selected_row["time_to_tca"] == 1.5
    assert meets_requested is False
    assert is_fallback is True


def test_post_tca_diagnostics_count_selected_post_tca_rows() -> None:
    snapshots = pd.DataFrame(
        {
            "event_id": ["a", "b", "c"],
            "horizon": ["1d", "1d", "1d"],
            "time_to_tca": [1.2, -0.1, 0.5],
            "selected_row_is_post_tca": [False, True, False],
            "is_horizon_fallback": [False, True, False],
            "event_has_pre_tca_row": [True, False, True],
        }
    )

    diagnostics = build_post_tca_diagnostics(snapshots)
    row = diagnostics.iloc[0]

    assert row["rows"] == 3
    assert row["post_tca_rows"] == 1
    assert row["fallback_rows"] == 1
    assert row["events_without_pre_tca"] == 1
    assert row["percent_post_tca_rows"] == 100 / 3
