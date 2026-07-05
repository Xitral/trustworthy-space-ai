# BEACON Methodology

## Title

**BEACON: Bayesian Event Assessment for Conjunction Observation and Notification**

BEACON studies calibrated, uncertainty-aware machine learning for satellite conjunction triage using public conjunction data message data.

## Research Questions

RQ1: Can lightweight ML models predict high-risk satellite conjunction events from public CDM data?

RQ2: How does performance change at early-warning horizons before closest approach?

RQ3: Do learned models improve rare-event ranking over direct current-risk ranking?

RQ4: Are predicted risk scores calibrated enough to support decision-making?

RQ5: Can uncertainty estimates identify predictions that should be escalated for human review?

RQ6: Are the main findings stable across repeated event-level train/validation/test splits?

## Core Design Rules

1. Split by `event_id`, never by individual CDM row.
2. Define labels from the final available event risk only.
3. Exclude final-risk label metadata from model features.
4. Keep the CDM-provided current `risk` as an allowed feature, but compare learned models against direct current-risk ranking.
5. Report rare-event ranking and top-K recall instead of accuracy.
6. Treat uncertainty escalation as a human-review signal, not an automated decision rule.
7. Report repeated-split mean and standard deviation because the positive class is very small.

## Data and Labeling

The raw data is grouped by `event_id`. Each event can have multiple CDM observations before time of closest approach.

The event label is defined as:

```text
high_risk = final_risk >= -5
```

Because `risk` is log10 collision probability, this corresponds to a collision probability threshold of `10^-5`.

The preprocessing pipeline also writes `results/horizon_post_tca_diagnostics.csv` to make any selected rows with `time_to_tca < 0` explicit.

## Prediction Horizons

BEACON evaluates:

| Horizon | Definition |
|---|---|
| `early` | earliest available pre-TCA CDM per event |
| `3d` | closest available pre-TCA CDM at least 3 days before TCA |
| `2d` | closest available pre-TCA CDM at least 2 days before TCA |
| `1d` | closest available pre-TCA CDM at least 1 day before TCA |
| `final` | closest available pre-TCA CDM to TCA, used for labeling |

The `early` horizon replaces an initial 7-day plan because the dataset does not support a reliable true 7-day snapshot for all events.

## Models

BEACON evaluates:

- direct current-risk baseline
- logistic regression
- random forest
- gradient boosting
- sigmoid-calibrated gradient boosting
- Laplace-approximated Bayesian logistic regression
- bootstrap gradient boosting ensemble

## Calibration

Calibration is evaluated with:

- Brier score
- Expected Calibration Error
- linear reliability curves
- quantile-binned reliability curves

Quantile-binned reliability is included because rare-event probabilities are highly concentrated near zero.

## Uncertainty and Escalation

Bootstrap ensemble uncertainty is measured as the predictive standard deviation across ensemble members.

Escalation policies compare:

- random escalation
- current-risk escalation
- bootstrap uncertainty escalation

The key interpretation is conservative: uncertainty escalation is useful if it performs far above random escalation and remains competitive with current-risk escalation. It should not be framed as replacing current-risk ranking.

## Repeated Split Robustness

The main robustness run uses:

```bash
python src/repeated_splits.py --n-splits 20 --n-bootstraps 10 --max-iter 150
```

On CPU-only machines, the same experiment can be parallelized with:

```bash
python src/repeated_splits.py --n-splits 20 --n-bootstraps 10 --max-iter 150 --n-jobs 8 --backend threading
```

The repeated split outputs are:

```text
results/repeated_split_metrics.csv
results/repeated_split_summary.csv
results/repeated_split_escalation.csv
results/repeated_split_escalation_summary.csv
```

The figure pipeline generates:

```text
figures/repeated_split_pr_auc.png
figures/repeated_split_top5_recall.png
figures/repeated_split_escalation_10pct.png
```

## Metrics

BEACON reports:

- ROC-AUC
- PR-AUC
- Brier score
- Expected Calibration Error
- precision at top 1%, 5%, and 10%
- recall at top 1%, 5%, and 10%
- positive escalation rate
- repeated-split mean and standard deviation

## Current Result Summary

Across 20 repeated event-level splits, learned models improve PR-AUC over the direct current-risk baseline at every evaluated horizon.

At the top 10% escalation level, uncertainty escalation captures far more high-risk events than random escalation and is competitive with current-risk escalation. Current-risk escalation remains very strong, so the correct claim is that uncertainty is complementary to domain risk estimates.

## Limitations

- Public dataset only.
- Small number of positive events.
- Research-defined high-risk threshold.
- No maneuver recommendation.
- No operational validation.
- Bootstrap uncertainty is Bayesian-inspired, not fully Bayesian.
- Repeated split robustness reduces single-split sensitivity but does not replace external validation.
