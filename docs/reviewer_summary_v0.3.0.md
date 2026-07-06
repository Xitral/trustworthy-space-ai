# BEACON v0.3.0 Reviewer Summary

## One-sentence summary

BEACON is a reproducible research artifact for trustworthy satellite conjunction triage that combines leakage-safe rare-event ML evaluation, uncertainty-aware human-review escalation, and an interactive 3D visual analytics viewer for research-only model-grounded inspection.

## Problem

Satellite conjunction assessment is a rare-event decision-support problem. Most conjunction warnings are routine, but a very small number may deserve additional human review. Accuracy is not a useful primary metric because the positive class is extremely rare.

## What is new in this artifact

BEACON emphasizes research-validity rather than operational deployment:

1. Event-level train/validation/test splitting by `event_id` to prevent leakage across multiple CDM observations from the same conjunction.
2. Early-warning horizon snapshots at `early`, `3d`, `2d`, and `1d`.
3. Comparison against direct current-risk ranking as a strong domain baseline.
4. Probability calibration and rare-event ranking metrics.
5. Bootstrap predictive uncertainty as a human-review escalation signal.
6. Repeated event-level split robustness across 20 random seeds.
7. Current-risk feature ablation to separate learned-model gains from direct use of the CDM risk feature.
8. Interactive 3D visual analytics viewer with uncertainty proxies, data-validity guardrails, display-scale warnings, and exportable research snapshots.

## Core results

Across 20 repeated event-level splits, learned models improve PR-AUC over direct current-risk ranking at every evaluated horizon:

| Horizon | Best learned PR-AUC | Current-risk PR-AUC |
|---|---:|---:|
| `1d` | `0.806 +/- 0.091` | `0.581 +/- 0.085` |
| `2d` | `0.630 +/- 0.106` | `0.367 +/- 0.083` |
| `3d` | `0.493 +/- 0.090` | `0.237 +/- 0.048` |
| `early` | `0.233 +/- 0.082` | `0.109 +/- 0.031` |

At the 10% human-review escalation level, uncertainty-based escalation captures far more high-risk events than random escalation and remains competitive with current-risk escalation. Current-risk escalation remains a strong comparator, so the result should be interpreted as complementary human-review support rather than replacement of domain risk estimates.

## Viewer contribution

The viewer is a research-only visual analytics interface. It helps inspect selected conjunction triage cases across horizons, showing:

- target and secondary path overlays,
- displayed separation,
- model probability,
- predictive uncertainty,
- uncertainty proxy volumes,
- geometry mode and source/fallback guardrails,
- display scale and original-distance preservation,
- screenshot/JSON/HTML research exports.

The viewer is not an operational propagator. If absolute target/secondary positions are unavailable, it uses relative-state, miss-distance, or deterministic reference-orbit approximations for interpretability.

## Limitations

- Raw data is not redistributed.
- The number of high-risk events is small.
- The results use public challenge data and are not externally operationally validated.
- The main learned models include the CDM current-risk feature.
- Bootstrap uncertainty is Bayesian-inspired, not fully Bayesian.
- Viewer uncertainty volumes are probability-space visual proxies, not orbital covariance ellipsoids.
- Viewer geometry is for interpretation and communication only.
- BEACON does not recommend maneuvers.

## Reproduction

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run tests:

```bash
python -m pytest -q
```

Run the full pipeline:

```bash
python src/run_all.py
```

Run the viewer:

```bash
python src/export_orbit_viewer.py
cd viewer
python -m http.server 8000
```

Then open `http://localhost:8000`, hard refresh, and run:

```javascript
runBeaconViewerSmokeTest()
```

See `REPRODUCIBILITY.md` and `docs/viewer_demo_checklist.md` for full details.

## Recommended reviewer lens

BEACON should be reviewed as a research artifact for trustworthy evaluation and visual analytics, not as an operational space-safety product.

The key evaluation question is:

```text
Does the artifact make rare-event conjunction triage more reproducible, leakage-aware, uncertainty-aware, and inspectable?
```
