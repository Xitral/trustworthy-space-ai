# BEACON

[![CI](https://github.com/Xitral/beacon-space-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Xitral/beacon-space-ai/actions/workflows/ci.yml)
[![LaTeX Paper](https://github.com/Xitral/beacon-space-ai/actions/workflows/latex.yml/badge.svg)](https://github.com/Xitral/beacon-space-ai/actions/workflows/latex.yml)
[![Version DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21209120.svg)](https://doi.org/10.5281/zenodo.21209120)
[![Concept DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21209119.svg)](https://doi.org/10.5281/zenodo.21209119)
![Python](https://img.shields.io/badge/python-3.10-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-research%20prototype-orange)
![Release](https://img.shields.io/badge/release-v0.2.1-purple)

**BEACON (Bayesian Event Assessment for Conjunction Observation and Notification)** is a reproducible research project for calibrated, uncertainty-aware satellite conjunction triage using public CDM data.

BEACON is a research prototype only. It is not an operational collision-avoidance or space-safety system.

## Citation and Archived Release

The manuscript-ready BEACON research artifact is archived on Zenodo:

```text
Version DOI: 10.5281/zenodo.21209120
Concept DOI: 10.5281/zenodo.21209119
Version: v0.2.1
Repository: https://github.com/Xitral/beacon-space-ai
```

Use the version DOI to cite the exact v0.2.1 artifact used for reproducibility. Use the concept DOI to cite the overall BEACON archive across versions. If you use BEACON, also cite the original public dataset provider.

## What BEACON Studies

BEACON evaluates whether lightweight machine learning can support rare-event conjunction triage by improving:

- rare-event ranking
- probability calibration
- uncertainty-aware human-review escalation
- repeated event-level split robustness
- current-risk feature ablation
- leakage-safe evaluation design

## Research Questions

**RQ1:** Can lightweight machine learning models predict high-risk satellite conjunction events from public CDM data?

**RQ2:** How does performance change across early-warning horizons before closest approach?

**RQ3:** Do learned models improve rare-event ranking over direct current-risk ranking?

**RQ4:** Are predicted risk scores calibrated enough to support decision-making?

**RQ5:** Can uncertainty estimates identify predictions that should be escalated for human review?

**RQ6:** Are the main findings stable across repeated event-level train/validation/test splits?

**RQ7:** How much of the learned model's performance depends on the CDM-provided current `risk` feature?

## Key Design Rules

- Split by `event_id`, not by CDM row.
- Define labels from final available event risk.
- Exclude final-risk label metadata from features.
- Compare learned models against direct current-risk ranking.
- Treat uncertainty as a human-review signal, not an automated decision rule.
- Report repeated-split means and standard deviations because high-risk events are rare.

## Methods

BEACON compares:

- direct current-risk baseline
- logistic regression
- random forest
- gradient boosting
- sigmoid-calibrated gradient boosting
- Laplace-approximated Bayesian logistic regression
- bootstrap gradient boosting uncertainty
- current-risk feature ablation

The risk ablation compares:

```text
current_risk_baseline
gradient_boosting_with_risk
gradient_boosting_without_risk
```

## Current Findings

Across 20 repeated event-level train/validation/test splits, learned models improve rare-event ranking over the direct current-risk baseline at every evaluated horizon.

| Horizon | Best learned model | Best learned PR-AUC | Current-risk PR-AUC |
|---|---|---:|---:|
| `1d` | bootstrap gradient boosting ensemble | 0.806 +/- 0.091 | 0.581 +/- 0.085 |
| `2d` | bootstrap gradient boosting ensemble | 0.630 +/- 0.106 | 0.367 +/- 0.083 |
| `3d` | gradient boosting | 0.493 +/- 0.090 | 0.237 +/- 0.048 |
| `early` | gradient boosting | 0.233 +/- 0.082 | 0.109 +/- 0.031 |

The current-risk feature ablation shows that current `risk` is central but does not fully explain the learned model's gains. Removing `risk` reduces gradient-boosting PR-AUC at every horizon, but the no-risk model still exceeds direct current-risk PR-AUC.

| Horizon | Current-risk PR-AUC | GB with risk PR-AUC | GB without risk PR-AUC |
|---|---:|---:|---:|
| `1d` | 0.581 +/- 0.085 | 0.739 +/- 0.096 | 0.634 +/- 0.147 |
| `2d` | 0.367 +/- 0.083 | 0.610 +/- 0.129 | 0.439 +/- 0.107 |
| `3d` | 0.237 +/- 0.048 | 0.493 +/- 0.090 | 0.379 +/- 0.089 |
| `early` | 0.109 +/- 0.031 | 0.233 +/- 0.082 | 0.180 +/- 0.066 |

At the top 10% human-review escalation level, uncertainty-based escalation captures far more high-risk events than random escalation and remains competitive with current-risk escalation.

| Horizon | Uncertainty escalation | Current-risk escalation | Random escalation |
|---|---:|---:|---:|
| `1d` | 97.5% +/- 3.9% | 99.6% +/- 1.9% | 8.3% +/- 7.2% |
| `2d` | 96.3% +/- 4.3% | 97.9% +/- 3.7% | 9.6% +/- 7.8% |
| `3d` | 97.5% +/- 3.9% | 97.9% +/- 3.7% | 11.3% +/- 10.2% |
| `early` | 80.8% +/- 9.8% | 84.6% +/- 7.8% | 8.3% +/- 6.6% |

The strongest interpretation is not that machine learning replaces current risk. The stronger and more defensible claim is that learned models can combine current risk with additional CDM/context features to improve rare-event ranking, while uncertainty can help identify events that deserve human review.

## Reproducing the Pipeline

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Place the raw ESA Spacecraft Collision Avoidance Challenge training data in `data/raw/`. See `data/README.md` for expected filenames and required columns.

Run the full pipeline:

```bash
python src/run_all.py
```

Run the lightweight test suite:

```bash
python -m pytest -q
```

Run the repeated split experiment:

```bash
python src/repeated_splits.py --n-splits 20 --n-bootstraps 10 --max-iter 150 --n-jobs 8 --backend threading
```

Run the current-risk feature ablation:

```bash
python src/risk_ablation.py --n-splits 20 --max-iter 150 --n-jobs 8 --backend threading
```

Regenerate figures and summary tables:

```bash
python src/make_figures.py
```

## Paper

The manuscript is available in both Markdown and LaTeX form:

```text
paper/main.md
paper/main.tex
paper/references.bib
```

To build the LaTeX paper from inside the `paper/` directory:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The repository also includes a GitHub Actions workflow that builds the LaTeX manuscript and uploads `main.pdf` as an artifact.

## Repository Structure

```text
beacon-space-ai/
  README.md
  CHANGELOG.md
  CITATION.cff
  LICENSE
  .gitignore
  requirements.txt

  .github/
    workflows/
      ci.yml
      latex.yml

  docs/
    experiment_plan.md
    project_summary.md
    reproducibility_checklist.md

  paper/
    main.md
    main.tex
    references.bib

  tests/
    conftest.py
    test_preprocess.py
    test_risk_ablation.py
    test_splits_and_metrics.py

  src/
    inspect_data.py
    preprocess.py
    check_horizon_coverage.py
    train_models.py
    calibrate_models.py
    bayesian_logistic.py
    uncertainty.py
    repeated_splits.py
    risk_ablation.py
    make_figures.py
    run_all.py

  data/
    README.md
    raw/
      .gitkeep
    processed/
      .gitkeep

  results/
    .gitkeep

  figures/
    .gitkeep
    pr_auc_by_horizon.png
    top5_recall_by_horizon.png
    brier_score_by_horizon.png
    ece_by_horizon.png
    quantile_reliability_by_horizon.png
    quantile_reliability_comparison_1d.png
    horizon_timing.png
    horizon_coverage.png
    uncertainty_positive_vs_negative.png
    positive_escalation_rate.png
    uncertainty_abstention_coverage.png
    repeated_split_pr_auc.png
    repeated_split_top5_recall.png
    repeated_split_escalation_10pct.png
    risk_ablation_pr_auc.png
    risk_ablation_top5_recall.png
```

Generated processed data and result CSV files are intentionally not committed. The pipeline regenerates them from the raw dataset.

## Key Outputs

Processed data:

- `data/processed/event_labels.csv`
- `data/processed/horizon_snapshots.parquet`

Results:

- `results/horizon_coverage.csv`
- `results/horizon_post_tca_diagnostics.csv`
- `results/baseline_metrics.csv`
- `results/calibration_metrics.csv`
- `results/calibration_curves.csv`
- `results/calibration_curves_quantile.csv`
- `results/bayesian_logistic_metrics.csv`
- `results/bayesian_logistic_predictions.csv`
- `results/uncertainty_metrics.csv`
- `results/uncertainty_abstention.csv`
- `results/uncertainty_predictions.csv`
- `results/repeated_split_metrics.csv`
- `results/repeated_split_summary.csv`
- `results/repeated_split_escalation.csv`
- `results/repeated_split_escalation_summary.csv`
- `results/risk_ablation_metrics.csv`
- `results/risk_ablation_summary.csv`
- `results/risk_ablation_deltas.csv`

## Project Status

Current status:

- preprocessing pipeline implemented
- event-level splits implemented
- horizon diagnostics implemented
- baseline models implemented
- calibration experiments implemented
- Bayesian logistic regression baseline implemented
- bootstrap uncertainty estimation implemented
- repeated split robustness evaluation implemented
- current-risk feature ablation implemented
- synthetic test suite and CI implemented
- manuscript converted to LaTeX
- LaTeX paper build workflow implemented
- archived Zenodo version and concept DOIs available

## Limitations

BEACON is a research prototype only. Important limitations include public data only, small positive-event counts, no maneuver recommendation, no operational validation, a research-defined high-risk threshold, Bayesian-inspired uncertainty for the strongest model, and lack of external validation.

## License

Code in this repository is released under the MIT License. Dataset use is governed by the original dataset provider's license and terms.
