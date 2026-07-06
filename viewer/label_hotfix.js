// Remove Cesium label background boxes while keeping the cleaner text styling.
(function patchLabelBackgrounds() {
  function stripLabelBackgrounds() {
    const entities = [
      state.refs.targetObject,
      state.refs.secondaryObject,
      state.refs.closestApproach,
    ];

    for (const entity of entities) {
      if (!entity?.label) continue;
      entity.label.showBackground = false;
      entity.label.backgroundColor = Cesium.Color.TRANSPARENT;
      entity.label.backgroundPadding = new Cesium.Cartesian2(0, 0);
      entity.label.outlineColor = Cesium.Color.BLACK.withAlpha(0.88);
      entity.label.outlineWidth = 3;
      entity.label.style = Cesium.LabelStyle.FILL_AND_OUTLINE;
    }
  }

  function frame() {
    stripLabelBackgrounds();
    requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
  window.__BEACON_LABEL_BACKGROUNDS_REMOVED__ = true;
})();
