# Data

Raw data is not committed to this repository.

BEACON is designed around the public ESA Spacecraft Collision Avoidance Challenge dataset, a curated set of conjunction data messages released for machine learning research. The challenge dataset contains CDM-style rows grouped by `event_id`, with time-to-TCA, current risk, relative state, covariance, and environment features.

## Expected raw files

Place the raw training file in:

```text
data/raw/
```

The preprocessing script searches for the first `.csv` or `.zip` file whose name contains `train`, so either of these patterns works:

```text
data/raw/train_data.csv
data/raw/train_data.zip
```

The file must contain at least these columns:

```text
event_id
time_to_tca
risk
```

The current pipeline was developed against a raw training table with 162,634 rows and 103 columns. After grouping by `event_id`, the processed event-level dataset contains 13,154 unique events.

## Processed outputs

Run:

```bash
python src/preprocess.py
```

This writes:

```text
data/processed/event_labels.csv
data/processed/horizon_snapshots.parquet
results/horizon_post_tca_diagnostics.csv
```

`event_labels.csv` contains the final event-level high-risk label. `horizon_snapshots.parquet` contains one row per event per prediction horizon. `horizon_post_tca_diagnostics.csv` reports how many selected horizon rows have `time_to_tca < 0`, which can happen only when an event lacks a pre-TCA observation and the pipeline falls back to the available row.

## Label definition

BEACON defines the event label from the final available event risk. A conjunction is labeled high-risk when:

```text
final_risk >= -5
```

The `risk` column is interpreted as log10 collision probability, so `-5` corresponds to a collision probability threshold of `10^-5`.

## Horizon definitions

BEACON constructs these prediction snapshots:

| Horizon | Definition |
|---|---|
| `early` | earliest available pre-TCA CDM for each event |
| `3d` | closest available pre-TCA CDM at least 3 days before TCA |
| `2d` | closest available pre-TCA CDM at least 2 days before TCA |
| `1d` | closest available pre-TCA CDM at least 1 day before TCA |
| `final` | closest available pre-TCA CDM to TCA, used only for labeling |

If no pre-TCA rows exist for an event, preprocessing falls back to an available row and records that situation in the post-TCA diagnostics. This keeps the behavior explicit instead of silently dropping events.

## Citation and license

Use the dataset only under the terms provided by the original data provider. If you publish or cite this project, also cite the original Spacecraft Collision Avoidance Challenge paper:

```text
Thomas Uriot, Dario Izzo, Luís F. Simões, Rasit Abay, Nils Einecke,
Sven Rebhan, Jose Martinez-Heras, Francesca Letizia, Jan Siminski,
and Klaus Merz. Spacecraft Collision Avoidance Challenge: design and
results of a machine learning competition. 2020.
```
