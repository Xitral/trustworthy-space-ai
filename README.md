# BEACON

[![CI](https://github.com/Xitral/beacon-space-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Xitral/beacon-space-ai/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-research%20prototype-orange)
![Release](https://img.shields.io/badge/release-v0.1.0-purple)

**BEACON (Bayesian Event Assessment for Conjunction Observation and Notification)** is a reproducible research project focused on calibrated, probabilistic, and uncertainty-aware risk prediction for satellite conjunction assessment using public CDM data.

The goal is to study how machine learning can support safer space operations by producing predictions that are not only accurate, but also calibrated, uncertainty-aware, robust across repeated event-level splits, and useful for prioritizing rare high-risk events.

BEACON is a research prototype only. It is not an operational space-safety system and should not be used for real-world operations.

## Release and Citation

The current release is **v0.1.0**, the first reproducible research-artifact release.

Citation metadata is available in:

```text
CITATION.cff
```

Release history is available in:

```text
CHANGELOG.md
```

A reviewer-facing reproducibility checklist is available in:

```text
docs/reproducibility_checklist.md
```

A short project summary is available in:

```text
docs/project_summary.md
```

## Research Direction

This project explores **trustworthy AI for space operations**, especially:

- satellite conjunction risk prediction
- calibrated machine learning
- uncertainty-aware decision support
- rare-event prioritization
- space-domain safety and resilience
- Bayesian logistic regression
- Bayesian-inspired uncertainty estimation
- human-in-the-loop escalation
- repeated split robustness evaluation
- leakage-safe evaluation design

## Research Questions

**RQ1:** Can lightweight machine learning models predict high-risk satellite conjunction events from public CDM data?

**RQ2:** How does performance change when predictions are made earlier before closest approach?

**RQ3:** Do learned models improve rare-event ranking over direct current-risk ranking?

**RQ4:** Are predicted risk scores calibrated enough to support decision-making?

**RQ5:** Can uncertainty estimates identify predictions that should be escalated for human review?

**RQ6:** Are the main results stable across repeated event-level train/validation/test splits?

## Why This Matters

Satellite conjunction triage is a high-consequence rare-event decision-support problem. Operators must prioritize a small number of potentially important events from a much larger stream of routine warnings.

Because high-risk conjunctions are rare, accuracy alone is not a useful measure of success. BEACON focuses on ranking, calibration, top-K recall, uncertainty-aware escalation, and robustness across repeated event-level splits.

## Task Definition

The dataset consists of public conjunction data messages grouped by event. Each event may contain multiple CDM observations before time of closest approach, or TCA.

BEACON defines a high-risk event using the final available event risk. An event is labeled high-risk if its final log10 risk is greater than or equal to `-5`, corresponding to a collision probability threshold of `10^-5`.

The resulting prediction task is highly imbalanced, with high-risk events making up less than 1% of the event-level dataset. Across the repeated-split test sets, the positive rate is about `0.006079`, or roughly 12 positive test events per horizon.

## Prediction Horizons

BEACON evaluates event snapshots at four warning horizons:

| Horizon | Definition |
|---|---|
| `early` | earliest available CDM for each event |
| `3d` | closest available CDM at least 3 days before TCA |
| `2d` | closest available CDM at least 2 days before TCA |
| `1d` | closest available CDM at least 1 day before TCA |

The original project direction considered a 7-day horizon, but the dataset did not support a reliable true 7-day snapshot for every event. The `early` horizon is used instead to honestly represent the earliest available observation for each event.

Preprocessing prefers pre-TCA rows. If an event has no pre-TCA rows, the pipeline falls back to an available row and records this in `results/horizon_post_tca_diagnostics.csv` rather than hiding the behavior.

## Methods

The project compares several models and evaluation approaches:

- current-risk baseline
- logistic regression
- random forest
- gradient boosting
- sigmoid-calibrated gradient boosting
- Laplace-approximated Bayesian logistic regression
- bootstrap ensemble uncertainty estimation
- repeated event-level split robustness evaluation

The current-risk baseline ranks events directly by the CDM-provided current risk estimate. This is an important baseline because the existing risk value is already domain-relevant.

Learned models are allowed to use the current CDM `risk` feature along with other numeric CDM/context features. The key comparison is therefore not “ML without risk versus current risk.” It is whether a learned model can improve triage over direct current-risk ranking by combining current risk with additional features.

Gradient boosting is evaluated both before and after sigmoid calibration. Calibration is measured using Brier score, Expected Calibration Error, and reliability curves.

BEACON includes a true Bayesian logistic regression baseline using a Gaussian prior, Bernoulli likelihood, MAP estimation, and a Laplace posterior approximation.

For uncertainty estimation, BEACON trains a bootstrap ensemble of gradient boosting models. Predictive standard deviation across ensemble members is used as an uncertainty score. This method is **Bayesian-inspired** because it estimates uncertainty through model disagreement rather than full posterior inference over the gradient boosting model.

To address split sensitivity in the rare-event setting, BEACON also runs repeated event-level splits and reports mean and standard deviation across splits. The figure pipeline generates repeated-split robustness plots for PR-AUC, top-5% recall, and 10% escalation policies.

## Evaluation Metrics

The project reports:

- ROC-AUC
- PR-AUC
- Brier score
- Expected Calibration Error
- precision at top 1%, 5%, and 10%
- recall at top 1%, 5%, and 10%
- reliability diagrams
- quantile-binned reliability curves
- early-warning horizon performance
- uncertainty-abstention analysis
- positive escalation rate under uncertainty-based review
- repeated split mean and standard deviation

Accuracy is not emphasized because the positive class is extremely rare.

## Key Design Rule

Train, validation, and test splits are performed by `event_id`, not by individual CDM row.

This prevents information from the same conjunction event from leaking across splits. The test suite includes checks for event-level split leakage, feature exclusion, top-K metric behavior, and horizon preprocessing diagnostics.

## Reproducing the Pipeline

First install dependencies:

```bash
python -m pip install -r requirements.txt
```

Place the raw ESA Spacecraft Collision Avoidance Challenge training data in `data/raw/`. See `data/README.md` for expected filenames and required columns.

Run the full BEACON experiment pipeline with:

```bash
python src/run_all.py
```

This runs:

1. raw data inspection
2. horizon preprocessing
3. horizon coverage diagnostics
4. baseline model training
5. model calibration
6. Bayesian logistic regression
7. uncertainty estimation
8. repeated split robustness evaluation
9. figure and summary table generation

Optional commands:

```bash
python src/run_all.py --skip-inspect
python src/run_all.py --skip-uncertainty
python src/run_all.py --skip-repeated-splits
python src/run_all.py --continue-on-error
```

Repeated-split runtime can be controlled through `run_all.py`:

```bash
python src/run_all.py --skip-inspect --repeated-n-jobs 8 --repeated-backend threading
```

A faster smoke-style repeated split run can be launched with:

```bash
python src/run_all.py --skip-inspect --repeated-n-splits 2 --repeated-n-bootstraps 2 --repeated-max-iter 30 --repeated-n-jobs 4 --repeated-backend threading
```

Individual scripts can also be run manually:

```bash
python src/inspect_data.py
python src/preprocess.py
python src/check_horizon_coverage.py
python src/train_models.py
python src/calibrate_models.py
python src/bayesian_logistic.py
python src/uncertainty.py
python src/repeated_splits.py
python src/make_figures.py
```

For the repeated split robustness run used in the current results:

```bash
python src/repeated_splits.py --n-splits 20 --n-bootstraps 10 --max-iter 150
```

On CPU-only laptops, this can be sped up with parallel workers:

```bash
python src/repeated_splits.py --n-splits 20 --n-bootstraps 10 --max-iter 150 --n-jobs 8 --backend threading
```

## Running Tests

Run the lightweight synthetic test suite with:

```bash
python -m pytest -q
```

The tests do not require the raw dataset. They cover:

- event-level split isolation
- leakage-prone feature exclusion
- top-K metric semantics
- horizon selection behavior
- post-TCA diagnostic counting

A GitHub Actions workflow runs the same tests on push and pull request.

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

  docs/
    experiment_plan.md
    project_summary.md
    reproducibility_checklist.md

  paper/
    main.md

  notebooks/
    exploratory_analysis.ipynb

  tests/
    conftest.py
    test_preprocess.py
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
    make_figures.py
    run_all.py

  data/
    README.md
    raw/
      .gitkeep
    processed/
      event_labels.csv
      horizon_snapshots.parquet

  results/
    horizon_coverage.csv
    horizon_post_tca_diagnostics.csv
    baseline_metrics.csv
    calibration_metrics.csv
    calibration_curves.csv
    calibration_curves_quantile.csv
    bayesian_logistic_metrics.csv
    bayesian_logistic_predictions.csv
    uncertainty_metrics.csv
    uncertainty_abstention.csv
    uncertainty_predictions.csv
    repeated_split_metrics.csv
    repeated_split_summary.csv
    repeated_split_escalation.csv
    repeated_split_escalation_summary.csv
    baseline_test_summary.csv
    calibration_test_summary.csv
    uncertainty_test_summary.csv
    uncertainty_abstention_test_summary.csv

  figures/
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
```

Some generated files may be excluded from version control depending on repository settings and data-size constraints. The pipeline is designed to regenerate processed data, results, and figures from the raw dataset.

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
- `results/baseline_test_summary.csv`
- `results/calibration_test_summary.csv`
- `results/uncertainty_test_summary.csv`
- `results/uncertainty_abstention_test_summary.csv`

Figures:

- `figures/pr_auc_by_horizon.png`
- `figures/top5_recall_by_horizon.png`
- `figures/brier_score_by_horizon.png`
- `figures/ece_by_horizon.png`
- `figures/quantile_reliability_by_horizon.png`
- `figures/quantile_reliability_comparison_1d.png`
- `figures/horizon_timing.png`
- `figures/horizon_coverage.png`
- `figures/uncertainty_positive_vs_negative.png`
- `figures/positive_escalation_rate.png`
- `figures/uncertainty_abstention_coverage.png`
- `figures/repeated_split_pr_auc.png`
- `figures/repeated_split_top5_recall.png`
- `figures/repeated_split_escalation_10pct.png`

## Current Findings

Across 20 repeated event-level train/validation/test splits, learned models improve rare-event ranking over the direct current-risk baseline at every evaluated horizon.

| Horizon | Best learned model | Best learned PR-AUC | Current-risk PR-AUC |
|---|---|---:|---:|
| `1d` | bootstrap gradient boosting ensemble | 0.806 +/- 0.091 | 0.581 +/- 0.085 |
| `2d` | bootstrap gradient boosting ensemble | 0.630 +/- 0.106 | 0.367 +/- 0.083 |
| `3d` | gradient boosting | 0.493 +/- 0.090 | 0.237 +/- 0.048 |
| `early` | gradient boosting | 0.233 +/- 0.082 | 0.109 +/- 0.031 |

At the top 10% human-review escalation level, uncertainty-based escalation captures far more high-risk events than random escalation and remains competitive with current-risk escalation.

| Horizon | Uncertainty escalation | Current-risk escalation | Random escalation |
|---|---:|---:|---:|
| `1d` | 97.5% +/- 3.9% | 99.6% +/- 1.9% | 8.3% +/- 7.2% |
| `2d` | 96.3% +/- 4.3% | 97.9% +/- 3.7% | 9.6% +/- 7.8% |
| `3d` | 97.5% +/- 3.9% | 97.9% +/- 3.7% | 11.3% +/- 10.2% |
| `early` | 80.8% +/- 9.8% | 84.6% +/- 7.8% | 8.3% +/- 6.6% |

Current results suggest:

- learned models improve rare-event ranking over direct current-risk ranking across repeated event-level splits
- gradient boosting is a strong lightweight triage model
- sigmoid calibration improves probability quality while preserving ranking performance
- quantile-binned reliability curves are more informative than linear-bin curves in this rare-event setting
- Bayesian logistic regression provides a true Bayesian probabilistic baseline
- bootstrap ensemble uncertainty is concentrated on high-risk events
- uncertainty-based escalation substantially outperforms random escalation
- current-risk escalation remains very strong, so uncertainty should be framed as a complementary human-review signal rather than a replacement for current-risk ranking

These findings are stronger than a single held-out split result because they persist across 20 repeated event-level splits. They are still preliminary because the number of high-risk events per test horizon remains small.

## Technical Report

The main technical report draft is available at:

```text
paper/main.md
```

It describes the task, methods, results, figures, limitations, and future work.

## Project Status

This repository is an active independent research project.

Current status:

- preprocessing pipeline implemented
- event-level splits implemented
- horizon coverage diagnostics implemented
- post-TCA selected-row diagnostics implemented
- baseline models implemented
- calibration experiments implemented
- quantile reliability curves implemented
- Bayesian logistic regression baseline implemented
- bootstrap uncertainty estimation implemented
- uncertainty escalation analysis implemented
- repeated split robustness evaluation implemented
- repeated split robustness figures implemented
- synthetic test suite implemented
- GitHub Actions CI implemented
- release metadata implemented
- reproducibility checklist implemented
- figure generation implemented
- technical report draft updated with repeated split results
- one-command reproducibility pipeline added

## Limitations

BEACON is a research prototype only. It is not an operational space-safety system and should not be used for real-world operations.

Important limitations include:

- public dataset only
- small number of positive test events
- no maneuver recommendation
- no operational validation
- research-defined high-risk threshold
- Bayesian-inspired bootstrap uncertainty rather than full Bayesian inference over the strongest model
- repeated split evaluation reduces single-split sensitivity but does not replace independent external validation
- rare events without pre-TCA rows require explicit diagnostic handling

Future work should include external validation, true Bayesian nonlinear models, cost-sensitive decision metrics, operationally informed escalation policies, and evaluation on additional conjunction datasets.

## License

Code in this repository is released under the MIT License. Dataset use is governed by the original dataset provider's license and terms.
