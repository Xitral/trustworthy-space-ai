// Make event switching respect the Track selected event toggle.
(function patchEventTrackingToggle() {
  if (typeof setEvent !== "function") return;

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

  window.__BEACON_EVENT_TRACKING_TOGGLE_RESPECTED__ = true;
})();
