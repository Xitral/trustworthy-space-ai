import math

import pandas as pd
import pytest

from export_orbit_viewer import (
    HORIZONS,
    build_payload,
    display_scale,
    geometry,
    load_predictions,
    log10_to_probability,
    selected_events,
)


REQUIRED_GEOMETRY_KEYS = {
    "mode",
    "target_position_km",
    "secondary_position_km",
    "closest_approach_km",
    "target_orbit_km",
    "secondary_orbit_km",
    "relative_position_km",
    "relative_distance_km",
    "display_relative_scale",
}


def test_log10_to_probability_clips_to_probability_range() -> None:
    assert log10_to_probability(-5.0) == pytest.approx(1e-5)
    assert log10_to_probability(2.0) == pytest.approx(1.0)
    assert log10_to_probability(None) is None


def test_display_scale_makes_small_separations_visible_but_preserves_larger_distances() -> None:
    assert display_scale([0.1, 0.0, 0.0]) == 400.0
    assert display_scale([5.0, 0.0, 0.0]) == 120.0
    assert display_scale([50.0, 0.0, 0.0]) == 30.0
    assert display_scale([500.0, 0.0, 0.0]) == 1.0


def test_geometry_uses_absolute_position_columns_when_available() -> None:
    row = pd.Series(
        {
            "event_id": "abs-1",
            "time_to_tca": 1.0,
            "risk": -6.0,
            "t_position_x": 7_000_000.0,
            "t_position_y": 0.0,
            "t_position_z": 0.0,
            "c_position_x": 7_000_010.0,
            "c_position_y": 0.0,
            "c_position_z": 0.0,
        }
    )

    g = geometry(row, row.index, points=16)

    assert g["mode"] == "absolute_position_columns"
    assert g["display_relative_scale"] == 1.0
    assert g["relative_distance_km"] == pytest.approx(0.01)
    assert len(g["target_orbit_km"]) == 16
    assert len(g["secondary_orbit_km"]) == 16


def test_geometry_preserves_original_relative_distance_when_display_scaled() -> None:
    row = pd.Series(
        {
            "event_id": "rel-1",
            "time_to_tca": 2.0,
            "risk": -5.5,
            "relative_position_x": 0.5,
            "relative_position_y": 0.0,
            "relative_position_z": 0.0,
        }
    )

    g = geometry(row, row.index, points=12)

    assert g["mode"] == "relative_state_approximation"
    assert g["relative_distance_km"] == pytest.approx(0.5)
    assert g["display_relative_scale"] == 400.0
    assert g["display_relative_distance_km"] == pytest.approx(200.0)


def test_selected_events_prioritizes_high_risk_events() -> None:
    rows = []
    for i in range(6):
        rows.append(
            {
                "event_id": f"e{i}",
                "horizon": "1d",
                "risk": -7.0 + i,
                "final_risk": -6.0,
                "high_risk": 1 if i in {2, 4} else 0,
                "mean_probability": 0.1 * i,
                "predictive_std": 0.01 * i,
            }
        )
    df = pd.DataFrame(rows)

    ids = selected_events(df, max_events=2)

    assert set(ids) == {"e2", "e4"}


def test_build_payload_contains_required_viewer_schema() -> None:
    df = pd.DataFrame(
        [
            {
                "event_id": "demo",
                "horizon": horizon,
                "time_to_tca": float(index + 1),
                "risk": -6.0 + index * 0.2,
                "final_risk": -4.9,
                "high_risk": 1,
                "mean_probability": 0.2 + index * 0.05,
                "predictive_std": 0.03 + index * 0.01,
                "relative_position_x": 2.0 + index,
                "relative_position_y": 0.5,
                "relative_position_z": 0.25,
                "meets_requested_horizon": True,
                "is_horizon_fallback": False,
            }
            for index, horizon in enumerate(HORIZONS)
        ]
    )

    payload = build_payload(df, max_events=1, points=10)

    assert set(payload) == {"metadata", "events"}
    assert payload["metadata"]["horizon_order"] == HORIZONS
    assert payload["metadata"]["geometry_modes"] == ["relative_state_approximation"]
    assert len(payload["events"]) == 1

    event = payload["events"][0]
    assert event["event_id"] == "demo"
    assert len(event["snapshots"]) == len(HORIZONS)

    for snapshot in event["snapshots"]:
        assert snapshot["horizon"] in HORIZONS
        assert isinstance(snapshot["current_risk_probability"], float)
        assert isinstance(snapshot["model_probability"], float)
        assert isinstance(snapshot["predictive_std"], float)
        assert REQUIRED_GEOMETRY_KEYS.issubset(snapshot["geometry"])
        assert len(snapshot["geometry"]["target_position_km"]) == 3
        assert len(snapshot["geometry"]["secondary_position_km"]) == 3
        assert len(snapshot["geometry"]["target_orbit_km"]) == 10
        assert len(snapshot["geometry"]["secondary_orbit_km"]) == 10
        assert math.isfinite(snapshot["geometry"]["relative_distance_km"])


def test_load_predictions_returns_empty_schema_for_missing_file(tmp_path) -> None:
    missing = tmp_path / "missing.csv"

    preds = load_predictions(missing)

    assert list(preds.columns) == ["event_id", "horizon", "mean_probability", "predictive_std"]
    assert preds.empty
