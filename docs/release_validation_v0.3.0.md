# BEACON v0.3.0 Release Validation Record

This file records the release-candidate validation status for the v0.3.0 research artifact.

Pending fields indicate validation evidence that has not yet been recorded for the candidate archive.

## Release candidate

```text
Release candidate: v0.3.0-rc1
Validation status: pending local validation
Validated by: Zander Polk
Validation date: TBD
Commit SHA: TBD
```

## Scope added since v0.2.2

- Consolidated viewer runtime behavior and removed replaced hotfix scripts.
- Added scientifically explicit uncertainty-proxy visualization and research-only labels.
- Added screenshot/export mode for PNG, JSON, and HTML research snapshots.
- Added research-validity guardrails for data source, geometry mode, display scale, and non-operational constraints.
- Added viewer export to the full pipeline.
- Added tests for split leakage, feature contracts, metric contracts, viewer export schema, viewer static contracts, and optional raw test-data inspection.
- Added interactive visual analytics framing to the paper.
- Added viewer export reliability configuration and browser smoke-test helper.
- Added reproducibility and viewer demo/checklist documentation.

## Validation checklist

- [ ] Latest `main` branch checked out.
- [ ] Dependencies installed from `requirements.txt`.
- [ ] `python -m pytest -q` completed.
- [ ] `python src/run_all.py` completed with full release settings.
- [ ] `viewer/data/conjunction_events.json` regenerated.
- [ ] LaTeX paper built.
- [ ] Viewer served locally.
- [ ] `runBeaconViewerSmokeTest()` completed in the browser console.
- [ ] PNG export checked and not blank.
- [ ] JSON export checked for `export_type`, `event_id`, `horizon`, `uncertainty_visualization`, and `snapshot`.
- [ ] Research HTML export checked locally.
- [ ] `README.md`, `REPRODUCIBILITY.md`, `CHANGELOG.md`, `paper/main.md`, and `paper/main.tex` reviewed for release consistency.
- [ ] `CITATION.cff` aligned with the current archived DOI status.

## Local commands

From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python src/run_all.py
```

Build the paper:

```powershell
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
cd ..
```

Serve the viewer:

```powershell
cd viewer
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

Then hard refresh and run in DevTools Console:

```javascript
runBeaconViewerSmokeTest()
```

## Test result

Recorded local output:

```text
TBD
```

Expected:

```text
all tests passed
```

## Full pipeline result

Recorded local output:

```text
TBD
```

Expected core output summary:

```text
data/processed/event_labels.csv
data/processed/horizon_snapshots.parquet
results/repeated_split_summary.csv
results/repeated_split_escalation_summary.csv
results/risk_ablation_summary.csv
viewer/data/conjunction_events.json
```

## Paper build result

Recorded local output:

```text
TBD
```

Expected:

```text
paper/main.pdf created successfully
```

## Viewer smoke-test result

Recorded browser console result:

```text
TBD
```

Expected:

```javascript
{ pass: true, failed: [], results: [...] }
```

## Export result

```text
PNG export: TBD
JSON export: TBD
Research HTML export: TBD
```

Expected:

```text
PNG is not blank.
JSON contains the research snapshot fields.
Research HTML opens locally and includes the research-only warning.
```

## Known caveats retained for release notes

- BEACON is a research prototype only.
- It is not an operational orbit propagator or operational decision system.
- Raw data is not redistributed.
- Results depend on public challenge data and have not been externally operationally validated.
- High-risk events are rare, so results must be interpreted with repeated-split uncertainty.
- Viewer geometry may use fallback/reference-orbit approximations when absolute positions are unavailable.
- Viewer uncertainty volumes are probability-space visual proxies, not physical covariance ellipsoids.
- Small separations may be display-scaled for visibility, while original distance is preserved in exported data.

## Release decision

```text
Decision: pending
Reason: local validation outputs are not yet recorded
```

Final release decisions are recorded as either:

```text
Decision: approve v0.3.0 release
Reason: tests, full pipeline, paper build, viewer smoke test, and exports passed
```

or:

```text
Decision: block v0.3.0 release
Reason: <specific blocker>
```
