from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0
HORIZONS = ["early", "3d", "2d", "1d"]

TARGET_TRIPLES = [
    ("t_position_x", "t_position_y", "t_position_z"),
    ("target_position_x", "target_position_y", "target_position_z"),
    ("primary_position_x", "primary_position_y", "primary_position_z"),
]
SECONDARY_TRIPLES = [
    ("c_position_x", "c_position_y", "c_position_z"),
    ("chaser_position_x", "chaser_position_y", "chaser_position_z"),
    ("secondary_position_x", "secondary_position_y", "secondary_position_z"),
]
RELATIVE_TRIPLES = [
    ("relative_position_x", "relative_position_y", "relative_position_z"),
    ("relative_position_r", "relative_position_t", "relative_position_n"),
    ("rel_pos_x", "rel_pos_y", "rel_pos_z"),
    ("rel_pos_r", "rel_pos_t", "rel_pos_n"),
]
VELOCITY_TRIPLES = [
    ("relative_velocity_x", "relative_velocity_y", "relative_velocity_z"),
    ("relative_velocity_r", "relative_velocity_t", "relative_velocity_n"),
    ("rel_vel_x", "rel_vel_y", "rel_vel_z"),
    ("rel_vel_r", "rel_vel_t", "rel_vel_n"),
]
MISS_DISTANCE_COLUMNS = ["miss_distance", "miss_distance_km", "miss_distance_m", "minimum_distance", "distance_at_tca"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export BEACON CesiumJS conjunction viewer data.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/horizon_snapshots.parquet"))
    parser.add_argument("--predictions", type=Path, default=Path("results/uncertainty_predictions.csv"))
    parser.add_argument("--output", type=Path, default=Path("viewer/data/conjunction_events.json"))
    parser.add_argument("--max-events", type=int, default=24)
    parser.add_argument("--orbit-points", type=int, default=144)
    return parser.parse_args()


def to_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def clean(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def log10_to_probability(value: float | None) -> float | None:
    if value is None:
        return None
    return float(10.0 ** max(min(value, 0.0), -320.0))


def stable_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def first_triple(columns, triples):
    available = set(columns)
    for triple in triples:
        if all(col in available for col in triple):
            return triple
    return None


def read_vector(row: pd.Series, triple) -> list[float] | None:
    if triple is None:
        return None
    values = [to_float(row.get(col)) for col in triple]
    if any(value is None for value in values):
        return None
    return [float(value) for value in values]


def norm(vector) -> float:
    return float(np.linalg.norm(np.asarray(vector, dtype=float)))


def unit(vector) -> np.ndarray:
    arr = np.asarray(vector, dtype=float)
    length = np.linalg.norm(arr)
    if not np.isfinite(length) or length == 0:
        return np.array([1.0, 0.0, 0.0])
    return arr / length


def km_absolute(vector: list[float]) -> list[float]:
    return [value / 1000.0 for value in vector] if norm(vector) > 100_000.0 else vector


def km_relative(vector: list[float]) -> list[float]:
    return [value / 1000.0 for value in vector] if norm(vector) > 1000.0 else vector


def display_scale(relative_km: list[float]) -> float:
    distance = max(norm(relative_km), 1e-6)
    if distance < 1.0:
        return 400.0
    if distance < 10.0:
        return 120.0
    if distance < 100.0:
        return 30.0
    return 1.0


def rot_z(angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def rot_x(angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def orbit_point(radius: float, inc_deg: float, raan_deg: float, phase_deg: float) -> np.ndarray:
    theta = math.radians(phase_deg)
    base = np.array([radius * math.cos(theta), radius * math.sin(theta), 0.0])
    return rot_z(math.radians(raan_deg)) @ rot_x(math.radians(inc_deg)) @ base


def orbit_path(radius: float, inc_deg: float, raan_deg: float, points: int) -> list[list[float]]:
    return [orbit_point(radius, inc_deg, raan_deg, phase).round(6).tolist() for phase in np.linspace(0, 360, points)]


def reference_frame(event_id: str, time_to_tca: float | None) -> dict:
    rng = np.random.default_rng(stable_seed(event_id))
    altitude = float(rng.choice([550.0, 700.0, 900.0, 1200.0, 20000.0, 35786.0], p=[0.35, 0.25, 0.15, 0.10, 0.05, 0.10]))
    inc = float(rng.uniform(0.0, 98.0))
    raan = float(rng.uniform(0.0, 360.0))
    phase = float(rng.uniform(0.0, 360.0))
    if time_to_tca is not None:
        period_days = 0.065 if altitude < 2000.0 else 1.0
        phase -= time_to_tca / period_days * 360.0
    return {"radius": EARTH_RADIUS_KM + altitude, "altitude": altitude, "inc": inc, "raan": raan, "phase": phase}


def local_rtn(position: np.ndarray, frame: dict):
    radial = unit(position)
    normal_seed = orbit_point(1.0, frame["inc"] + 90.0, frame["raan"], frame["phase"])
    cross_track = unit(normal_seed)
    along_track = unit(np.cross(cross_track, radial))
    cross_track = unit(np.cross(radial, along_track))
    return radial, along_track, cross_track


def miss_distance_km(row: pd.Series) -> float | None:
    for column in MISS_DISTANCE_COLUMNS:
        if column not in row.index:
            continue
        value = to_float(row.get(column))
        if value is None:
            continue
        return abs(value) / 1000.0 if column.endswith("_m") or abs(value) > 1000.0 else abs(value)
    return None


def relative_geometry(row: pd.Series, columns, points: int) -> dict:
    event_id = str(row["event_id"])
    frame = reference_frame(event_id, to_float(row.get("time_to_tca")))
    target = orbit_point(frame["radius"], frame["inc"], frame["raan"], frame["phase"])
    radial, along, cross = local_rtn(target, frame)

    rel_triple = first_triple(columns, RELATIVE_TRIPLES)
    vel_triple = first_triple(columns, VELOCITY_TRIPLES)
    rel_raw = read_vector(row, rel_triple)
    source_columns = {}

    if rel_raw is not None:
        rel_km = km_relative(rel_raw)
        mode = "relative_state_approximation"
        source_columns["relative_position"] = list(rel_triple)
    else:
        miss = miss_distance_km(row)
        if miss is not None:
            rel_km = [0.0, 0.0, max(miss, 0.001)]
            mode = "miss_distance_approximation"
            source_columns["miss_distance"] = [col for col in MISS_DISTANCE_COLUMNS if col in row.index]
        else:
            risk_prob = log10_to_probability(to_float(row.get("risk"))) or 0.0
            rel_km = [0.0, max(0.5, min(250.0, 25.0 / (1.0 + risk_prob * 1e5))), 10.0]
            mode = "reference_orbit_approximation"

    rel = np.asarray(rel_km[0] * radial + rel_km[1] * along + rel_km[2] * cross)
    scale = display_scale(rel_km)
    shown_rel = rel * scale
    secondary = target + shown_rel

    vel_raw = read_vector(row, vel_triple)
    if vel_raw is not None:
        vel = np.asarray(km_relative(vel_raw))
        vel = vel[0] * radial + vel[1] * along + vel[2] * cross
        source_columns["relative_velocity"] = list(vel_triple)
    else:
        vel = along * 0.02 + cross * 0.01

    target_path = orbit_path(frame["radius"], frame["inc"], frame["raan"], points)
    half = max((points - 1) / 2.0, 1.0)
    secondary_path = []
    for index, point in enumerate(target_path):
        drift = (index - half) / half
        secondary_path.append((np.asarray(point) + shown_rel + vel * drift * 600.0).round(6).tolist())

    return {
        "mode": mode,
        "target_position_km": target.round(6).tolist(),
        "secondary_position_km": secondary.round(6).tolist(),
        "closest_approach_km": ((target + secondary) / 2.0).round(6).tolist(),
        "target_orbit_km": target_path,
        "secondary_orbit_km": secondary_path,
        "relative_position_km": [round(x, 6) for x in rel_km],
        "relative_distance_km": round(norm(rel_km), 6),
        "display_relative_scale": scale,
        "display_relative_distance_km": round(norm(shown_rel), 6),
        "reference_orbit": {"altitude_km": round(frame["altitude"], 3), "inclination_deg": round(frame["inc"], 3), "raan_deg": round(frame["raan"], 3)},
        "source_columns": source_columns,
    }


def absolute_geometry(row: pd.Series, columns, points: int) -> dict | None:
    target_cols = first_triple(columns, TARGET_TRIPLES)
    secondary_cols = first_triple(columns, SECONDARY_TRIPLES)
    target_raw = read_vector(row, target_cols)
    secondary_raw = read_vector(row, secondary_cols)
    if target_raw is None or secondary_raw is None:
        return None

    target = np.asarray(km_absolute(target_raw), dtype=float)
    secondary = np.asarray(km_absolute(secondary_raw), dtype=float)
    radius = max(norm(target), EARTH_RADIUS_KM + 400.0)
    radial = unit(target)
    normal = np.array([0.0, 0.0, 1.0]) if abs(np.dot(radial, [0, 0, 1])) < 0.95 else np.array([0.0, 1.0, 0.0])
    normal = unit(np.cross(radial, normal))
    along = unit(np.cross(normal, radial))
    phases = np.linspace(0.0, 2.0 * math.pi, points)
    target_path = [(radius * (math.cos(t) * radial + math.sin(t) * along)).round(6).tolist() for t in phases]
    offset = secondary - target
    secondary_path = [(np.asarray(point) + offset).round(6).tolist() for point in target_path]
    return {
        "mode": "absolute_position_columns",
        "target_position_km": target.round(6).tolist(),
        "secondary_position_km": secondary.round(6).tolist(),
        "closest_approach_km": ((target + secondary) / 2.0).round(6).tolist(),
        "target_orbit_km": target_path,
        "secondary_orbit_km": secondary_path,
        "relative_position_km": offset.round(6).tolist(),
        "relative_distance_km": round(norm(offset), 6),
        "display_relative_scale": 1.0,
        "source_columns": {"target_position": list(target_cols), "secondary_position": list(secondary_cols)},
    }


def geometry(row: pd.Series, columns, points: int) -> dict:
    return absolute_geometry(row, columns, points) or relative_geometry(row, columns, points)


def load_predictions(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["event_id", "horizon", "mean_probability", "predictive_std"])
    preds = pd.read_csv(path)
    required = {"event_id", "horizon", "mean_probability", "predictive_std"}
    if not required.issubset(preds.columns):
        return pd.DataFrame(columns=list(required))
    preds = preds.copy()
    preds["event_id"] = preds["event_id"].astype(str)
    if "split" in preds.columns and (preds["split"] == "test").any():
        preds = preds[preds["split"] == "test"]
    return preds[["event_id", "horizon", "mean_probability", "predictive_std"]].groupby(["event_id", "horizon"], as_index=False).mean(numeric_only=True)


def load_snapshots(input_path: Path, predictions_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Missing {input_path}. Run python src/preprocess.py first.")
    df = pd.read_parquet(input_path).copy()
    df["event_id"] = df["event_id"].astype(str)
    df = df[df["horizon"].isin(HORIZONS)].copy()
    preds = load_predictions(predictions_path)
    if len(preds):
        df = df.merge(preds, on=["event_id", "horizon"], how="left")
    else:
        df["mean_probability"] = np.nan
        df["predictive_std"] = np.nan
    return df


def selected_events(df: pd.DataFrame, max_events: int) -> list[str]:
    scored = df.copy()
    scored["risk_score"] = pd.to_numeric(scored.get("risk"), errors="coerce").fillna(-50.0)
    scored["final_risk_score"] = pd.to_numeric(scored.get("final_risk"), errors="coerce").fillna(-50.0)
    scored["model_score"] = pd.to_numeric(scored.get("mean_probability"), errors="coerce").fillna(0.0)
    scored["uncertainty_score"] = pd.to_numeric(scored.get("predictive_std"), errors="coerce").fillna(0.0)
    scored["high_risk_score"] = pd.to_numeric(scored.get("high_risk"), errors="coerce").fillna(0.0)
    scored["viewer_priority"] = scored["high_risk_score"] * 1000 + scored["model_score"] * 100 + scored["uncertainty_score"] * 50 + scored["final_risk_score"] + scored["risk_score"] * 0.25
    return scored.groupby("event_id", as_index=False).agg(viewer_priority=("viewer_priority", "max")).sort_values("viewer_priority", ascending=False).head(max_events)["event_id"].tolist()


def snapshot(row: pd.Series, columns, points: int) -> dict:
    risk = to_float(row.get("risk"))
    final_risk = to_float(row.get("final_risk"))
    return {
        "horizon": clean(row.get("horizon")),
        "time_to_tca_days": clean(to_float(row.get("time_to_tca"))),
        "current_risk_log10": clean(risk),
        "current_risk_probability": clean(log10_to_probability(risk)),
        "final_risk_log10": clean(final_risk),
        "final_risk_probability": clean(log10_to_probability(final_risk)),
        "model_probability": clean(to_float(row.get("mean_probability"))),
        "predictive_std": clean(to_float(row.get("predictive_std"))),
        "meets_requested_horizon": clean(row.get("meets_requested_horizon")),
        "is_horizon_fallback": clean(row.get("is_horizon_fallback")),
        "geometry": geometry(row, columns, points),
    }


def build_payload(df: pd.DataFrame, max_events: int, points: int) -> dict:
    ids = selected_events(df, max_events)
    df = df[df["event_id"].isin(ids)].copy()
    df["horizon_order"] = df["horizon"].map({h: i for i, h in enumerate(HORIZONS)})
    df = df.sort_values(["event_id", "horizon_order"])
    events = []
    for event_id in ids:
        event_df = df[df["event_id"] == event_id]
        if event_df.empty:
            continue
        first = event_df.iloc[0]
        events.append({
            "event_id": str(event_id),
            "display_name": f"Event {event_id}",
            "high_risk": clean(int(first.get("high_risk", 0))),
            "final_risk_log10": clean(to_float(first.get("final_risk"))),
            "snapshots": [snapshot(row, df.columns, points) for _, row in event_df.iterrows()],
        })
    modes = sorted({snap["geometry"]["mode"] for event in events for snap in event["snapshots"]})
    return {
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "viewer": "BEACON CesiumJS conjunction triage viewer",
            "horizon_order": HORIZONS,
            "geometry_modes": modes,
            "coordinate_note": "Absolute position columns are used when available. Otherwise relative-state or miss-distance columns are displayed in a deterministic reference orbit for physically grounded interpretation, not operational propagation.",
            "display_scale_note": "Very small separations may be scaled for visibility; original relative_distance_km is preserved.",
        },
        "events": events,
    }


def main() -> None:
    args = parse_args()
    df = load_snapshots(args.input, args.predictions)
    payload = build_payload(df, args.max_events, args.orbit_points)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Events exported: {len(payload['events'])}")
    print(f"Geometry modes: {', '.join(payload['metadata']['geometry_modes'])}")


if __name__ == "__main__":
    main()
