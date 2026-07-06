// Scrubber interaction fixes that run after the existing BEACON viewer patches.
(function patchScrubInteractionConflicts() {
  let wired = false;

  function pausePlayHorizons() {
    if (state.playTimer) {
      clearInterval(state.playTimer);
      state.playTimer = null;
      if (playButton) playButton.textContent = "Play horizons";
    }
  }

  function resetCameraPivotPreservingView() {
    if (!viewer?.camera) return;
    const camera = viewer.camera;
    const destination = Cesium.Cartesian3.clone(camera.positionWC);
    const direction = Cesium.Cartesian3.clone(camera.directionWC);
    const up = Cesium.Cartesian3.clone(camera.upWC);

    viewer.trackedEntity = undefined;
    camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    camera.setView({
      destination,
      orientation: { direction, up },
    });
    viewer.scene.requestRender();
  }

  function handleScrubStart() {
    pausePlayHorizons();
    resetCameraPivotPreservingView();
    window.__BEACON_RESEARCH_SCRUBBING__ = true;
  }

  function handleScrubMove() {
    pausePlayHorizons();
    requestAnimationFrame(resetCameraPivotPreservingView);
  }

  function handleScrubEnd() {
    pausePlayHorizons();
    requestAnimationFrame(() => {
      resetCameraPivotPreservingView();
      window.__BEACON_RESEARCH_SCRUBBING__ = false;
    });
  }

  function wireScrubber() {
    if (wired) return;
    const scrubber = document.getElementById("researchScrubber");
    if (!scrubber) return;
    wired = true;

    scrubber.addEventListener("pointerdown", handleScrubStart, true);
    scrubber.addEventListener("input", handleScrubMove, true);
    scrubber.addEventListener("change", handleScrubMove, true);
    scrubber.addEventListener("pointerup", handleScrubEnd, true);
    scrubber.addEventListener("pointercancel", handleScrubEnd, true);
  }

  function frame() {
    wireScrubber();
    requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
  window.__BEACON_SCRUB_PAUSES_PLAY__ = true;
  window.__BEACON_CAMERA_PIVOT_RESET_ON_SCRUB__ = true;
})();
