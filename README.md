# BEACON

**BEACON (Bayesian Event Assessment for Conjunction Observation and Notification)** is a reproducible research project focused on calibrated, probabilistic, and uncertainty-aware risk prediction for satellite conjunction assessment using public CDM data.

The goal is to study how machine learning can support safer space operations by producing predictions that are not only accurate, but also calibrated, uncertainty-aware, and useful for prioritizing rare high-risk events.

## Research Direction

This project explores **trustworthy AI for space operations**, especially:

- satellite conjunction risk prediction
- calibrated machine learning
- uncertainty-aware decision support
- rare-event prioritization
- space-domain safety and resilience
- bayesian uncertainty estimation

## Research Questions

**RQ1:** Can lightweight machine learning models predict high-risk satellite conjunction events from public CDM data?

**RQ2:** How does performance change when predictions are made earlier before closest approach?

**RQ3:** Are predicted risk scores calibrated enough to support decision-making?

**RQ4:** Can models rank the top 1%, 5%, and 10% riskiest conjunction events?

**RQ5:** Can uncertainty estimates identify predictions that should be escalated for human review?

## Why This Matters

Satellite collision avoidance is a high-consequence decision-support problem. As orbital environments become more congested, operators need tools that can help prioritize attention, identify risky events, and communicate uncertainty clearly.

This project does not attempt to replace operational conjunction assessment systems. Instead, it studies how machine learning models should be evaluated when used in space-safety contexts.

## Planned Methods

The project will compare several baseline models:

- naive current-risk baseline
- logistic regression
- random forest
- gradient boosting
- calibrated gradient boosting
- simple ensemble uncertainty estimation

The focus is not only on prediction accuracy, but also on whether the models produce useful and trustworthy risk scores.

## Evaluation Metrics

Planned metrics include:

- ROC-AUC
- PR-AUC
- Brier score
- Expected Calibration Error
- precision at top K
- recall at top K
- reliability diagrams
- early-warning horizon performance
- uncertainty-abstention analysis

## Key Design Rule

Train, validation, and test splits should be performed by `event_id`, not by individual CDM row.

This prevents information from the same conjunction event from leaking across splits.

## Repository Structure

```text
trustworthy-space-ai/
  README.md
  LICENSE
  .gitignore
  requirements.txt

  docs/
    experiment_plan.md

  paper/
    main.pdf

  notebooks/
    exploratory_analysis.ipynb

  src/
    config.py
    preprocess.py
    build_horizons.py
    train_models.py
    calibrate_models.py
    evaluate.py
    make_figures.py
    run_all.py

  data/
    README.md
    raw/
    processed/

  results/
    metrics.csv

  figures/
    reliability_diagram.png
    horizon_performance.png
    topk_risk_capture.png
```

## Project Status

This repository is an active independent research project.

## Limitations

BEACON is a research prototype only. It is not an operational collision-avoidance system, does not recommend maneuvers, and should not be used for real-world satellite operations.

## License

Code in this repository is released under the MIT License. Dataset use is governed by the original dataset provider’s license and terms.
