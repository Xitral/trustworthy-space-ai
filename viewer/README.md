# BEACON Orbit Viewer

This directory contains a lightweight CesiumJS viewer for representative BEACON satellite conjunction events.

The viewer is intended for interpretation and communication. It is not an operational astrodynamics, maneuver-planning, or collision-avoidance tool.

## Generate viewer data

From the repository root, run:

```bash
python src/export_orbit_viewer.py
```

This reads:

```text
data/processed/horizon_snapshots.parquet
results/uncertainty_predictions.csv
```

and writes:

```text
viewer/data/conjunction_events.json
```

The generated JSON is intentionally ignored by Git because it is derived from local processed data.

## Open the viewer

Serve the directory from a local HTTP server:

```bash
cd viewer
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

Opening `index.html` directly from the filesystem may not work because browsers restrict local JSON fetches.

## Geometry modes

The exporter uses the most grounded geometry available from the processed dataset:

1. `absolute_position_columns` when target and secondary position columns are available.
2. `relative_state_approximation` when relative position columns are available.
3. `miss_distance_approximation` when only miss-distance style geometry is available.
4. `reference_orbit_approximation` as a deterministic display fallback.

Small separations may be visually scaled so the close-approach geometry remains visible at Earth scale. The original relative distance is preserved in the exported metadata.
