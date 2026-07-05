# Changelog

All notable project changes are documented here.

## v0.1.0 - 2026-07-04

Initial reproducible research artifact release of BEACON.

### Added

- Leakage-safe event-level preprocessing by `event_id`.
- Early, 3-day, 2-day, 1-day, and final horizon snapshot construction.
- Post-TCA selected-row diagnostics.
- Current-risk baseline, logistic regression, random forest, and gradient boosting models.
- Sigmoid calibration and reliability diagnostics.
- Quantile-binned reliability curves for rare-event calibration analysis.
- Laplace-approximated Bayesian logistic regression baseline.
- Bootstrap gradient boosting uncertainty estimation.
- Uncertainty-based human-review escalation analysis.
- Repeated event-level split robustness evaluation.
- Repeated-split PR-AUC, top-5% recall, and 10% escalation figures.
- One-command pipeline runner through `src/run_all.py`.
- Synthetic pytest suite for split leakage, feature exclusion, metrics, and preprocessing behavior.
- GitHub Actions CI workflow.
- Technical report draft in `paper/main.md`.
- Data reproduction notes in `data/README.md`.

### Notes

- BEACON is a research prototype only and is not an operational space-safety system.
- Raw data is not committed to the repository.
- Public results should be interpreted as preliminary rare-event decision-support evidence, not deployment-ready validation.
