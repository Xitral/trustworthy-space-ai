# BEACON Reproducibility Guide

This guide defines the expected environment, commands, outputs, and validation steps for reproducing the BEACON research artifact.

## Artifact scope

BEACON is a research prototype for calibrated, uncertainty-aware satellite conjunction triage using public conjunction data message data. It is not an operational orbit propagator, collision-avoidance system, or maneuver-recommendation tool.

The v0.3.0 release-candidate scope includes:

- leakage-safe event-level preprocessing,
- horizon snapshot construction for `early`, `3d`, `2d`, and `1d`,
- rare-event ranking and calibration baselines,
- Bayesian logistic and bootstrap uncertainty experiments,
- repeated event-level split robustness,
- current-risk feature ablation,
- 3D visual analytics viewer export,
- viewer validity guardrails,
- screenshot/JSON/HTML export mode,
- browser smoke-test helper for the viewer.

## Environment

Recommended environment:

```text
Python: 3.10
OS: Windows 11, macOS, or Linux
Browser for viewer: current Chrome or Edge
LaTeX: MiKTeX, TeX Live, or equivalent if building paper/main.pdf locally
```

Install Python dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

## Data requirements

Raw data is not committed to this repository.

Place the public ESA Spacecraft Collision Avoidance Challenge training file in:

```text
data/raw/
```

The preprocessing script searches for a `.csv` or `.zip` file whose name contains `train`, such as:

```text
data/raw/train_data.csv
data/raw/train_data.zip
```

The training file must contain at least:

```text
event_id
time_to_tca
risk
```

A raw test file is optional. If a file whose name contains `test` is present, `src/inspect_data.py` will inspect it and write train/test column-comparison summaries. If it is absent, inspection continues with training data only.

## Fast validation

Run the test suite from the repository root:

```bash
python -m pytest -q
```

Expected result:

```text
all tests pass
```

The tests cover preprocessing behavior, event-level split leakage, feature exclusion, rare-event metrics, viewer export schema, optional raw test inspection, consolidated viewer scripts, and viewer export/smoke-test contracts.

## Full pipeline reproduction

Run the full pipeline from the repository root:

```bash
python src/run_all.py
```

The full pipeline performs inspection, preprocessing, horizon diagnostics, model training, calibration, Bayesian logistic baseline, bootstrap uncertainty, repeated split robustness, current-risk ablation, figure generation, and viewer data export.

For faster local iteration, repeated split parameters can be reduced:

```bash
python src/run_all.py --repeated-n-splits 3 --repeated-n-bootstraps 3 --risk-ablation-n-splits 3
```

Use full settings before publishing or archiving.

## Expected core outputs

A successful full run should produce these core outputs:

```text
data/processed/event_labels.csv
data/processed/horizon_snapshots.parquet
results/horizon_coverage.csv
results/horizon_post_tca_diagnostics.csv
results/baseline_metrics.csv
results/calibration_metrics.csv
results/bayesian_logistic_metrics.csv
results/uncertainty_metrics.csv
results/repeated_split_summary.csv
results/repeated_split_escalation_summary.csv
results/risk_ablation_summary.csv
figures/repeated_split_pr_auc.png
figures/repeated_split_top5_recall.png
figures/repeated_split_escalation_10pct.png
figures/risk_ablation_pr_auc.png
figures/risk_ablation_top5_recall.png
viewer/data/conjunction_events.json
```

`src/run_all.py` prints a pipeline output summary and reports missing files if any expected output was not created.

## Expected published-result ranges

The archived v0.2.2/v0.3.0 candidate findings should remain qualitatively consistent with these repeated-split results when run with the same data and full settings:

| Horizon | Best learned PR-AUC | Current-risk PR-AUC |
|---|---:|---:|
| `1d` | about `0.806 +/- 0.091` | about `0.581 +/- 0.085` |
| `2d` | about `0.630 +/- 0.106` | about `0.367 +/- 0.083` |
| `3d` | about `0.493 +/- 0.090` | about `0.237 +/- 0.048` |
| `early` | about `0.233 +/- 0.082` | about `0.109 +/- 0.031` |

Small differences can occur from library versions, platform differences, and stochastic model training, but the main qualitative claims should remain stable:

- learned models improve PR-AUC over direct current-risk ranking,
- uncertainty escalation greatly outperforms random escalation,
- current-risk escalation remains a strong comparator,
- risk ablation shows current risk is central but not the only useful signal.

## Viewer reproduction

Generate viewer data:

```bash
python src/export_orbit_viewer.py
```

Serve the viewer locally:

```bash
cd viewer
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

Hard refresh the browser, then open DevTools Console and run:

```javascript
runBeaconViewerSmokeTest()
```

Expected result:

```javascript
{ pass: true, failed: [], results: [...] }
```

See `docs/viewer_demo_checklist.md` for the manual demo/export QA sequence.

## Paper build

From the repository root:

```bash
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Expected output:

```text
paper/main.pdf
```

If `pdflatex` is not available, install MiKTeX or TeX Live and reopen the terminal before retrying.

## Known nondeterminism and caveats

- Some model outputs can vary slightly with platform, library versions, and stochastic training.
- The dataset is not redistributed, so exact reproduction requires the same public raw data files.
- Viewer geometry is an interpretability aid and may use fallback/reference-orbit geometry when absolute position columns are unavailable.
- Uncertainty volumes are probability-space visual proxies derived from predictive standard deviation and forecast horizon; they are not physical covariance ellipsoids.
- Small separations may be display-scaled for visibility, but the original `relative_distance_km` is preserved in exported data.
- The artifact has not been operationally validated and must not be used for real collision-avoidance decisions.

## Release-candidate validation record

Before publishing a new archive, fill in `docs/release_validation_v0.3.0.md` with:

- commit SHA,
- test command and result,
- full pipeline command and result,
- paper build result,
- viewer smoke-test result,
- PNG/JSON/HTML export result,
- unresolved caveats.
