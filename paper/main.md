# BEACON: Bayesian Event Assessment for Conjunction Observation and Notification

## Abstract

Satellite conjunction assessment is a rare-event decision-support problem in which operators must prioritize a small number of potentially high-risk events from a much larger set of routine conjunction warnings. This work introduces **BEACON**, a reproducible study of calibrated, uncertainty-aware machine learning for satellite conjunction triage using public conjunction data message data.

BEACON evaluates event-level risk prediction across early, 3-day, 2-day, and 1-day warning horizons using leakage-safe event splits. The study compares learned models against a direct current-risk baseline, evaluates probability calibration, and tests whether bootstrap ensemble uncertainty can identify events that should be escalated for human review.

The results suggest that learned models can improve rare-event ranking over direct current-risk ranking at several horizons. Sigmoid calibration improves probability quality while preserving ranking performance. Bootstrap ensemble uncertainty is strongly concentrated on high-risk events, and escalating the most uncertain predictions captures most high-risk conjunctions in the held-out test split.

## 1. Introduction

Satellite operators face an increasingly congested orbital environment. Collision avoidance decisions are high-consequence, time-sensitive, and uncertainty-heavy. Because truly high-risk conjunctions are rare, the task is not simply classification. It is rare-event triage.

A useful decision-support system should do more than maximize accuracy. It should rank risky events effectively, produce probabilities that are reasonably calibrated, and communicate uncertainty so that ambiguous cases can be escalated for human review.

This project studies whether lightweight machine learning models can support conjunction assessment by improving:

1. rare-event risk ranking,
2. probability calibration,
3. and uncertainty-aware escalation.

BEACON is not intended to replace operational conjunction assessment systems. It is a research prototype for evaluating how machine learning should be tested when applied to space-safety decision support.

## 2. Research Questions

**RQ1:** Can lightweight machine learning models predict high-risk satellite conjunction events from public CDM data?

**RQ2:** How does performance change across early-warning horizons before closest approach?

**RQ3:** Do learned models improve rare-event ranking over direct current-risk ranking?

**RQ4:** Are predicted risk scores calibrated enough to support decision-making?

**RQ5:** Can uncertainty estimates identify predictions that should be escalated for human review?

## 3. Data

The dataset consists of public conjunction data messages grouped by event. Each event contains one or more CDM observations before time of closest approach.

The high-risk label is defined using the final available pre-TCA event risk. A conjunction is labeled high-risk if its final log10 risk is greater than or equal to `-5`, corresponding to a collision probability threshold of `10^-5`.

The resulting task is highly imbalanced. In the event-level split used here, only about **0.58%** of events are labeled high-risk. This makes accuracy a poor evaluation metric. A model that predicts every event as non-high-risk would achieve very high accuracy while being operationally useless.

## 4. Horizon Construction

BEACON evaluates prediction snapshots at four warning horizons:

- **early:** earliest available CDM per event
- **3d:** closest available CDM at least 3 days before TCA
- **2d:** closest available CDM at least 2 days before TCA
- **1d:** closest available CDM at least 1 day before TCA

A horizon coverage diagnostic is included because not every event contains observations at every requested warning horizon.

![Actual timing of selected horizon snapshots](../figures/horizon_timing.png)

![Horizon coverage diagnostics](../figures/horizon_coverage.png)

The original plan included a 7-day horizon, but the dataset did not contain valid 7-day snapshots for the events in this split. Instead, BEACON reports an `early` horizon, defined as the earliest available CDM for each event. This is more honest than labeling the earliest available observations as true 7-day predictions.

## 5. Methods

### 5.1 Event-level splitting

Train, validation, and test splits are performed by `event_id`, not by individual CDM row. This prevents observations from the same conjunction event from leaking across splits.

This design rule is critical because each event may have multiple CDM observations. If rows from the same event appeared in both training and test sets, the model could appear to perform well by recognizing event-specific information rather than learning generalizable risk structure.

### 5.2 Baselines

The study compares four baseline approaches:

- current-risk baseline
- logistic regression
- random forest
- gradient boosting

The **current-risk baseline** ranks events directly by the CDM-provided current risk estimate. This is an important baseline because the existing risk value is already highly informative. A learned model is only useful if it improves over simply sorting events by current estimated risk.

### 5.3 Calibration

Gradient boosting probabilities are calibrated using sigmoid calibration on the validation split. Calibration is evaluated on held-out test events using:

- Brier score
- Expected Calibration Error
- reliability curves
- quantile-binned reliability curves

Calibration is important because a model can rank events well while still producing probabilities that are poorly aligned with observed event frequencies.

### 5.4 Bayesian-inspired uncertainty estimation

BEACON uses a bootstrap gradient boosting ensemble as a Bayesian-inspired uncertainty estimator. Multiple gradient boosting models are trained on bootstrapped samples of the training data. For each event, BEACON computes:

- mean predicted probability across ensemble members
- predictive standard deviation across ensemble members

The predictive standard deviation is used as an uncertainty score. Events with the highest uncertainty can be escalated for human review.

This method is called **Bayesian-inspired** rather than fully Bayesian because it does not explicitly define priors, likelihoods, or posterior inference. Instead, it approximates uncertainty by measuring disagreement across models trained on plausible resampled versions of the data.

## 6. Metrics

The primary metrics are:

- ROC-AUC
- PR-AUC
- Brier score
- Expected Calibration Error
- precision at top 1%, 5%, and 10%
- recall at top 1%, 5%, and 10%
- positive escalation rate under uncertainty-based review

Accuracy is not emphasized because the positive class is extremely rare.

For rare-event triage, the most important operational question is not whether the model predicts every event correctly. The more important question is whether it helps prioritize the small number of events most deserving of attention.

## 7. Results

### 7.1 Rare-event ranking

Gradient boosting improves PR-AUC over the current-risk baseline across several horizons. This suggests that learned models can improve rare-event prioritization beyond simply ranking by the CDM-provided current risk estimate.

![PR-AUC by prediction horizon](../figures/pr_auc_by_horizon.png)

The current-risk baseline remains strong, which is expected. The CDM risk estimate is already a meaningful domain signal. However, learned models provide additional value at several horizons, especially for early, 3-day, and 2-day prediction snapshots.

### 7.2 Top-K triage

Top-K recall measures how many high-risk events are captured when reviewing only the highest-ranked events. This is especially relevant for operational triage, where human attention is limited.

![Top 5% recall by prediction horizon](../figures/top5_recall_by_horizon.png)

The results show that a small top-ranked review set can capture a large fraction of high-risk events. This supports the framing of conjunction assessment as a ranking and prioritization problem rather than a standard classification problem.

### 7.3 Probability calibration

Sigmoid calibration preserves ranking performance while improving probability quality. This is expected because calibration mostly adjusts the probability scale rather than changing the ordering of predictions.

![Brier score by prediction horizon](../figures/brier_score_by_horizon.png)

![Expected Calibration Error by prediction horizon](../figures/ece_by_horizon.png)

Brier score and Expected Calibration Error improve after calibration across the evaluated horizons. This suggests that calibrated gradient boosting produces probabilities that are more useful for decision support than raw model outputs.

The quantile-binned reliability curves provide a clearer view of calibration in the rare-event setting.

![Quantile-binned reliability by horizon](../figures/quantile_reliability_by_horizon.png)

The 1-day reliability comparison shows how the current-risk baseline, raw gradient boosting, and calibrated gradient boosting differ in probability behavior.

![Quantile-binned reliability comparison at 1 day](../figures/quantile_reliability_comparison_1d.png)

### 7.4 Uncertainty-aware escalation

Bootstrap ensemble uncertainty is strongly concentrated on high-risk events. High-risk events have much larger predictive standard deviation than non-high-risk events.

![Predictive uncertainty for high-risk vs non-high-risk events](../figures/uncertainty_positive_vs_negative.png)

This result suggests that uncertainty itself is a useful triage signal. The model is not merely assigning higher risk to some events; it is also expressing greater uncertainty on events that are more likely to matter.

Escalating the most uncertain predictions captures a large fraction of high-risk events.

![Positive escalation rate from uncertainty-based review](../figures/positive_escalation_rate.png)

At the 10% escalation level, the uncertainty method captures most high-risk events across horizons in the held-out test split. This supports the idea that uncertainty-aware models can help decide which events deserve human review.

The coverage tradeoff shows how many high-risk events are escalated as the automated coverage rate decreases.

![Uncertainty abstention coverage tradeoff](../figures/uncertainty_abstention_coverage.png)

These results should not be interpreted as a final operational policy. Instead, they show that uncertainty can act as a meaningful signal for human-in-the-loop decision support.

## 8. Discussion

The results suggest that calibrated and uncertainty-aware machine learning can support rare-event triage in satellite conjunction assessment.

The strongest use case is not replacing operational systems. Instead, BEACON is best understood as a decision-support framework for prioritizing which events deserve closer human review.

Three findings are especially important.

First, the task is extremely imbalanced, with high-risk events representing less than 1% of events. This makes accuracy an inappropriate primary metric. PR-AUC, top-K recall, calibration, and uncertainty-aware escalation are more meaningful.

Second, learned models improve rare-event ranking over the current-risk baseline at several horizons. This matters because the current-risk baseline is a strong and realistic comparator.

Third, uncertainty-based escalation captures most high-risk events by reviewing only a small fraction of the most uncertain predictions. This suggests that uncertainty estimates can help identify cases where automated prediction should defer to human judgment.

## 9. Limitations

This project is a research prototype only.

Key limitations include:

- The number of positive test events is small.
- Results are based on public data only.
- The system does not recommend maneuvers.
- The system has not been validated in an operational environment.
- Bootstrap uncertainty is Bayesian-inspired, not fully Bayesian.
- Results may vary under different event splits.
- The high-risk threshold is a research definition and not an operational decision rule.
- The figures and metrics should be interpreted as preliminary evidence, not deployment-ready validation.

Because each test horizon contains only a small number of high-risk events, strong-looking recall results should be interpreted cautiously. Future work should repeat the evaluation over multiple event-level splits or cross-validation folds.

## 10. Conclusion

BEACON demonstrates a reproducible framework for evaluating trustworthy AI in satellite conjunction triage.

The project shows that rare-event ranking, calibration, and uncertainty-aware escalation provide a more appropriate evaluation lens than accuracy alone. Learned models can improve prioritization over direct current-risk ranking, calibration improves probability quality, and bootstrap ensemble uncertainty can identify many high-risk events for human review.

Future work should add:

- true Bayesian baselines,
- repeated split evaluation,
- external validation,
- cost-sensitive metrics,
- operationally informed escalation policies,
- and richer uncertainty decomposition.

BEACON is not an operational collision-avoidance system. It is a research artifact showing how trustworthy machine learning methods can be evaluated for high-consequence space-domain decision support.
