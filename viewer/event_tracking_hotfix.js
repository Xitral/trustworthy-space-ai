// Make event switching and playback respect the Track selected event toggle.
(function patchEventTrackingToggle() {
  let playButtonInterceptWired = false;

  if (typeof setEvent === "function") {
    setEvent = function patchedSetEvent(index) {
      stopAnimation();
      state.eventIndex = Number(index);
      state.horizonIndex = 0;
      state.displaySnapshot = currentSnapshot();
      populateHorizonSelect();
      state.hovered = null;
      updateHoverLabels();

      // Only move/focus the camera when tracking is actually enabled.
      // With tracking disabled, changing events updates the scene in place.
      renderScene(trackToggle.checked);
    };
  }

  function playbackTick(shouldTrackDuringPlayback) {
    const event = currentEvent();
    const next = (state.horizonIndex + 1) % event.snapshots.length;
    const beforeTrackState = trackToggle.checked;

    // transitionToHorizon/renderSnapshot now already respects trackToggle. The
    // important part is never allowing playback to mutate the checkbox.
    transitionToHorizon(next, { smooth: smoothToggle.checked });

    trackToggle.checked = shouldTrackDuringPlayback ? beforeTrackState : false;
    if (!shouldTrackDuringPlayback) {
      viewer.trackedEntity = undefined;
    }
  }

  function patchedTogglePlay() {
    if (state.playTimer) {
      clearInterval(state.playTimer);
      state.playTimer = null;
      playButton.textContent = "Play horizons";
      return;
    }

    // Preserve the user's tracking choice. Playback should animate horizons,
    // not silently re-enable camera tracking.
    const shouldTrackDuringPlayback = trackToggle.checked;
    playButton.textContent = "Pause";

    state.playTimer = setInterval(() => {
      playbackTick(shouldTrackDuringPlayback);
    }, smoothToggle.checked ? 1250 : 900);
  }

  if (typeof togglePlay === "function") {
    togglePlay = patchedTogglePlay;
  }

  function wirePlayButtonIntercept() {
    if (playButtonInterceptWired || !playButton) return;
    playButtonInterceptWired = true;

    // app.js attached its original click listener before this file loaded, and
    // that original listener forcibly checks trackToggle. Capture the click first
    // and stop it so only the patched playback behavior runs.
    playButton.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        patchedTogglePlay();
      },
      true,
    );
  }

  wirePlayButtonIntercept();

  function frame() {
    wirePlayButtonIntercept();
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  window.__BEACON_EVENT_TRACKING_TOGGLE_RESPECTED__ = true;
  window.__BEACON_PLAY_RESPECTS_TRACKING__ = true;
  window.__BEACON_PLAY_BUTTON_INTERCEPTED__ = true;
})();
