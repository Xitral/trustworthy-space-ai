from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_reproducibility_guide_documents_core_release_commands() -> None:
    text = read("REPRODUCIBILITY.md")

    assert "python -m pytest -q" in text
    assert "python src/run_all.py" in text
    assert "python src/export_orbit_viewer.py" in text
    assert "runBeaconViewerSmokeTest()" in text
    assert "pdflatex main.tex" in text
    assert "viewer/data/conjunction_events.json" in text
    assert "not physical covariance ellipsoids" in text


def test_release_validation_record_states_candidate_validation_status() -> None:
    text = read("docs/release_validation_v0.3.0.md")

    assert "Release candidate: v0.3.0-rc1" in text
    assert "Validation status: pending local validation" in text
    assert "Decision: pending" in text
    assert "python -m pytest -q" in text
    assert "runBeaconViewerSmokeTest()" in text
    assert "CITATION.cff` aligned with the current archived DOI status" in text


def test_release_notes_define_research_framing_and_unsupported_claims() -> None:
    text = read("docs/release_notes_v0.3.0.md")

    assert "Status: release candidate draft" in text
    assert "BEACON remains a research prototype" in text
    assert "Research framing" in text
    assert "Unsupported claims" in text
    assert "physical covariance ellipsoids" in text


def test_reviewer_summary_states_review_lens() -> None:
    text = read("docs/reviewer_summary_v0.3.0.md")

    assert "One-sentence summary" in text
    assert "What is new in this artifact" in text
    assert "Core results" in text
    assert "Viewer contribution" in text
    assert "Recommended reviewer lens" in text
    assert "not as an operational space-safety product" in text


def test_readme_marks_release_candidate_without_replacing_archived_doi() -> None:
    text = read("README.md")

    assert "v0.3.0-rc1" in text
    assert "Archived version: v0.2.2" in text
    assert "10.5281/zenodo.21209794" in text
    assert "does not yet have a final Zenodo version DOI" in text
