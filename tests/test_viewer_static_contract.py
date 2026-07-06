from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWER_DIR = REPO_ROOT / "viewer"


def test_viewer_loads_named_runtime_modules() -> None:
    html = (VIEWER_DIR / "index.html").read_text(encoding="utf-8")

    assert '<script src="app.js"></script>' in html
    assert '<script src="live_trails.js"></script>' in html
    assert '<script src="research_runtime.js"></script>' in html
    assert '<script src="research_consistency.js"></script>' in html


def test_research_runtime_has_one_canonical_export_area() -> None:
    runtime = (VIEWER_DIR / "research_runtime.js").read_text(encoding="utf-8")

    assert runtime.count("Screenshot / Export Mode") == 1
    assert "beaconPngButton" in runtime
    assert "beaconJsonButton" in runtime
    assert "beaconBriefButton" in runtime
    assert "Research-only classification. Not an operational maneuver recommendation." in runtime


def test_research_consistency_labels_guardrails() -> None:
    consistency = (VIEWER_DIR / "research_consistency.js").read_text(encoding="utf-8")

    assert "removeLegacyBriefCard" in consistency
    assert "Research Validity Guardrails" in consistency
    assert "not orbital covariance ellipsoids" in consistency
    assert "Not operational" in consistency


def test_removed_patch_scripts_are_not_loaded_or_present() -> None:
    html = (VIEWER_DIR / "index.html").read_text(encoding="utf-8")
    removed_scripts = [
        "research_hotfix.js",
        "label_hotfix.js",
        "event_tracking_hotfix.js",
        "scrub_interaction_hotfix.js",
        "camera_pivot_hotfix.js",
    ]

    for script in removed_scripts:
        assert script not in html
        assert not (VIEWER_DIR / script).exists()
