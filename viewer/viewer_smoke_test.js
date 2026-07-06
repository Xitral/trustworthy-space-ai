// Browser-console smoke test for the BEACON viewer.
// Usage from http://localhost:8000 after a hard refresh:
//   runBeaconViewerSmokeTest()
(function installBeaconViewerSmokeTest() {
  function exists(selector) {
    return Boolean(document.querySelector(selector));
  }

  function count(selector) {
    return document.querySelectorAll(selector).length;
  }

  function hasText(selector, text) {
    return Array.from(document.querySelectorAll(selector)).some((node) =>
      (node.textContent || "").includes(text),
    );
  }

  function finiteNumber(value) {
    return Number.isFinite(Number(value));
  }

  function currentSnapshotSafe() {
    try {
      return state?.displaySnapshot || currentSnapshot?.();
    } catch (error) {
      return null;
    }
  }

  function stateSafe() {
    try {
      return typeof state !== "undefined" ? state : null;
    } catch (error) {
      return null;
    }
  }

  function viewerSafe() {
    try {
      return typeof viewer !== "undefined" ? viewer : window.viewer;
    } catch (error) {
      return window.viewer || null;
    }
  }

  function check(name, pass, detail = "") {
    return { name, pass: Boolean(pass), detail };
  }

  window.runBeaconViewerSmokeTest = function runBeaconViewerSmokeTest() {
    const viewerInstance = viewerSafe();
    const stateObject = stateSafe();
    const snapshot = currentSnapshotSafe();
    const geometry = snapshot?.geometry || {};
    const data = stateObject?.data || {};
    const events = Array.isArray(data.events) ? data.events : [];
    const scripts = Array.from(document.scripts).map((script) => script.getAttribute("src") || "");

    const results = [
      check("Cesium loaded", Boolean(window.Cesium?.Viewer)),
      check("Viewer created", Boolean(viewerInstance)),
      check("Preserve drawing buffer configured", window.__BEACON_PRESERVE_DRAWING_BUFFER_CONFIGURED__ === true),
      check("Viewer export flag set", Boolean(viewerInstance?.__BEACON_PRESERVE_DRAWING_BUFFER__)),
      check("Research runtime loaded", window.__BEACON_RESEARCH_RUNTIME__ === true),
      check("Research consistency loaded", window.__BEACON_RESEARCH_CONSISTENCY__ === true),
      check("Event selector exists", exists("#eventSelect")),
      check("Horizon selector exists", exists("#horizonSelect")),
      check("Play button exists", exists("#playButton")),
      check("Focus button exists", exists("#homeButton")),
      check("Tracking toggle exists", exists("#trackToggle")),
      check("Metrics panel exists", exists("#metrics")),
      check("Research dock exists", exists("#researchDock")),
      check("Validity guardrails card exists", exists("#beaconValidityCard")),
      check("Uncertainty panel exists", exists("#beaconUncertaintyPanel")),
      check("One canonical export card", count("#beaconExportCard") === 1, `count=${count("#beaconExportCard")}`),
      check("PNG export button exists", exists("#beaconPngButton")),
      check("JSON export button exists", exists("#beaconJsonButton")),
      check("HTML export button exists", exists("#beaconBriefButton")),
      check("Figure mode button exists", exists("#beaconFigureModeButton")),
      check("No removed patch scripts loaded", !scripts.some((src) => src.includes("hotfix"))),
      check("Data payload has events", events.length > 0, `events=${events.length}`),
      check("Current snapshot exists", Boolean(snapshot)),
      check("Snapshot has horizon", Boolean(snapshot?.horizon), String(snapshot?.horizon || "")),
      check("Snapshot has risk", finiteNumber(snapshot?.current_risk_log10), String(snapshot?.current_risk_log10)),
      check("Snapshot has model probability", snapshot?.model_probability === null || finiteNumber(snapshot?.model_probability), String(snapshot?.model_probability)),
      check("Snapshot has predictive std", snapshot?.predictive_std === null || finiteNumber(snapshot?.predictive_std), String(snapshot?.predictive_std)),
      check("Geometry mode exposed", Boolean(geometry.mode), String(geometry.mode || "")),
      check("Target position vector", Array.isArray(geometry.target_position_km) && geometry.target_position_km.length === 3),
      check("Secondary position vector", Array.isArray(geometry.secondary_position_km) && geometry.secondary_position_km.length === 3),
      check("Target orbit path", Array.isArray(geometry.target_orbit_km) && geometry.target_orbit_km.length >= 8),
      check("Secondary orbit path", Array.isArray(geometry.secondary_orbit_km) && geometry.secondary_orbit_km.length >= 8),
      check("Original distance preserved", finiteNumber(geometry.relative_distance_km), String(geometry.relative_distance_km)),
      check("Display scale present", finiteNumber(geometry.display_relative_scale), String(geometry.display_relative_scale)),
      check("Research-only warning visible", hasText("body", "Not operational") || hasText("body", "Research-only")),
    ];

    const failed = results.filter((result) => !result.pass);
    console.table(results);

    if (failed.length) {
      console.warn("BEACON viewer smoke test failed", failed);
      return { pass: false, failed, results };
    }

    console.log("BEACON viewer smoke test passed.");
    return { pass: true, failed: [], results };
  };

  window.__BEACON_VIEWER_SMOKE_TEST_INSTALLED__ = true;
})();
