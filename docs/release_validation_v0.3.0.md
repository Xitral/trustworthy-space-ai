# BEACON v0.3.0 Release Validation Record

This file is the release-candidate validation record for the v0.3.0 research artifact.

Do not publish a new GitHub release, Zenodo archive, or public announcement until the unchecked items are completed and the local outputs are pasted or summarized here.

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

## Required validation checklist

- [ ] Pull latest `main`.
- [ ] Install dependencies from `requirements.txt`.
- [ ] Run `python -m pytest -q`.
- [ ] Run `python src/run_all.py` with full release settings.
- [ ] Confirm `viewer/data/conjunction_events.json` is regenerated.
- [ ] Build the LaTeX paper.
- [ ] Serve the viewer locally.
- [ ] Run `runBeaconViewerSmokeTest()` in the browser console.
- [ ] Export PNG and confirm it is not blank.
- [ ] Export JSON and confirm it contains `export_type`, `event_id`, `horizon`, `uncertainty_visualization`, and `snapshot`.
- [ ] Export Research HTML and confirm it opens locally.
- [ ] Review `README.md`, `REPRODUCIBILITY.md`, `CHANGELOG.md`, `paper/main.md`, and `paper/main.tex` for release consistency.
- [ ] Confirm `CITATION.cff` still points to the current archived DOI until a new Zenodo DOI is minted.

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

Paste or summarize the local output here:

```text
TBD
```

Expected:

```text
all tests passed
```

## Full pipeline result

Paste or summarize the local output here:

```text
TBD
```

Expected core output summary should include:

```text
data/processed/event_labels.csv
data/processed/horizon_snapshots.parquet
results/repeated_split_summary.csv
results/repeated_split_escalation_summary.csv
results/risk_ablation_summary.csv
viewer/data/conjunction_events.json
```

## Paper build result

Paste or summarize the local output here:

```text
TBD
```

Expected:

```text
paper/main.pdf created successfully
```

## Viewer smoke-test result

Paste or summarize the browser console result here:

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

## Known caveats to keep in release notes

- BEACON is a research prototype only.
- It is not an operational orbit propagator, collision-avoidance system, or maneuver recommendation system.
- Raw data is not redistributed.
- Results depend on public challenge data and have not been externally operationally validated.
- High-risk events are rare, so results must be interpreted with repeated-split uncertainty.
- Viewer geometry may use fallback/reference-orbit approximations when absolute positions are unavailable.
- Viewer uncertainty volumes are probability-space visual proxies, not physical covariance ellipsoids.
- Small separations may be display-scaled for visibility, while original distance is preserved in exported data.

## Release decision

```text
Decision: pending
Reason: waiting on local validation outputs
```

When all validation is complete, update this section to either:

```text
Decision: approve v0.3.0 release
Reason: tests, full pipeline, paper build, viewer smoke test, and exports passed
```

or:

```text
Decision: block v0.3.0 release
Reason: <specific blocker>
```
