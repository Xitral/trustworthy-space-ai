# BEACON v0.3.0 Release Notes Draft

Status: release candidate draft. Do not publish these notes as final until `docs/release_validation_v0.3.0.md` is completed.

## Summary

BEACON v0.3.0 turns the project from a modeling-only research artifact into a more complete uncertainty-aware visual analytics system for research-only satellite conjunction triage.

This release candidate adds viewer runtime consolidation, research-validity guardrails, exportable research snapshots, stronger test coverage, full-pipeline viewer export, reproducibility documentation, and paper framing for the interactive visual analytics contribution.

BEACON remains a research prototype. It is not an operational collision-avoidance system, orbit propagator, or maneuver recommendation system.

## Highlights

### Research pipeline

- Added explicit `scipy` dependency for Bayesian logistic regression.
- Added `src/export_orbit_viewer.py` to the full `src/run_all.py` pipeline.
- Added `viewer/data/conjunction_events.json` to expected full-pipeline outputs.
- Made optional raw test-data inspection non-blocking.
- Clarified raw training/test data expectations in `data/README.md`.

### Viewer and visual analytics

- Consolidated replaced viewer hotfix behavior into named runtime modules.
- Added scientifically explicit uncertainty-proxy visualization.
- Added screenshot/export mode with PNG, JSON, and HTML research snapshots.
- Added research-validity guardrails for data source, geometry mode, display scale, fallback/sample data, and non-operational constraints.
- Removed duplicate export controls and standardized on the `Screenshot / Export Mode` card.
- Added WebGL drawing-buffer preservation for more reliable PNG export.
- Added browser-console smoke test helper through `runBeaconViewerSmokeTest()`.
- Added viewer demo/export checklist.

### Tests

- Added event-level split leakage contract tests.
- Added feature exclusion / leakage metadata tests.
- Added rare-event metric contract tests.
- Added orbit viewer export schema tests.
- Added viewer static contract tests for runtime modules and export helpers.
- Added optional raw test-data inspection tests.

### Paper and documentation

- Added visual analytics framing to the abstract, research questions, methods, discussion, limitations, and conclusion.
- Added a formal interactive visual analytics viewer section to Markdown and LaTeX paper sources.
- Added `REPRODUCIBILITY.md`.
- Added `docs/release_validation_v0.3.0.md`.
- Added `docs/release_notes_v0.3.0.md`.

## Research claims to preserve

Use this framing:

```text
BEACON combines leakage-safe rare-event ML evaluation, uncertainty-aware human-review escalation, and an interactive 3D visual analytics viewer for research-only model-grounded conjunction triage inspection.
```

The strongest claims are:

- Learned models improve rare-event ranking over direct current-risk ranking across repeated event-level splits.
- Bootstrap predictive uncertainty is useful as a human-review escalation signal and greatly outperforms random escalation.
- Current-risk escalation remains a strong comparator; BEACON complements rather than replaces domain risk estimates.
- The viewer supports research inspection by exposing horizon evolution, uncertainty proxies, geometry provenance, display scaling, and non-operational guardrails.

## Claims to avoid

Do not claim:

- BEACON is operationally validated.
- BEACON recommends maneuvers.
- BEACON predicts collisions for operational use.
- Viewer uncertainty volumes are physical covariance ellipsoids.
- Display-scaled separations are true physical separations.
- Machine learning replaces CDM current risk.

## Validation before final release

Before publishing v0.3.0:

- Complete `docs/release_validation_v0.3.0.md`.
- Run `python -m pytest -q`.
- Run `python src/run_all.py` with full settings.
- Build `paper/main.pdf`.
- Run `runBeaconViewerSmokeTest()` in the browser.
- Export PNG/JSON/HTML snapshots and confirm they are usable.
- Review README, paper, reproducibility guide, and changelog for version consistency.

## Citation / DOI note

The current `CITATION.cff` still points to the archived v0.2.2 Zenodo version DOI. Keep it that way until the final v0.3.0 archive is minted on Zenodo. After Zenodo issues a new version DOI, update:

- `CITATION.cff`,
- README DOI/version text,
- release notes,
- paper artifact availability section if needed.

The concept DOI should remain the same across versions.
