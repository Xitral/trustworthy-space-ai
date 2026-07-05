// BEACON viewer UX/live-trail patch.
//
// This file patches app.js without changing its exported data model. It replaces
// the static-looking orbit trail updates with dynamic per-segment CallbackProperty
// trails. Each segment reads the latest interpolated snapshot every frame, so the
// orbit gradient moves with the dots and the visible trail head terminates at the
// live object position instead of snapping after the transition completes.

(function patchBeaconViewerUx() {
  const TRAIL_HEAD_ALPHA = 0.96;
  const TRAIL_TAIL_ALPHA = 0.018;
  const FUTURE_ALPHA = 0.025;
  const LABEL_FADE_EASE = 0.16;

  const originalRenderSnapshot = renderSnapshot;
  const originalRenderMetrics = renderMetrics;
  const originalCenterCameraOnSnapshot = centerCameraOnSnapshot;
  const originalApplyLabelFade = applyLabelFade;

  const labelFadeState = {
    target: 1,
    current: 1,
  };

  const trailState = {
    targetTrailSegments: null,
    secondaryTrailSegments: null,
  };

  function squaredDistance(a, b) {
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;
  }

  function closestProgressOnPath(path, point, fallbackProgress) {
    const length = effectivePathLength(path);
    if (length < 2 || !Array.isArray(point)) {
      return isFiniteNumber(fallbackProgress) ? Number(fallbackProgress) : 0;
    }

    let bestProgress = 0;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (let i = 0; i < length; i += 1) {
      const a = path[i];
      const b = path[(i + 1) % length];
      const ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      const ap = [point[0] - a[0], point[1] - a[1], point[2] - a[2]];
      const denom = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2;
      const t = denom > 0 ? clamp((ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / denom, 0, 1) : 0;
      const projected = [a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t];
      const d = squaredDistance(projected, point);

      if (d < bestDistance) {
        bestDistance = d;
        bestProgress = i + t;
      }
    }

    return bestProgress;
  }

  function trailAlphaAtMidpoint(midpoint, liveProgress, length) {
    const behindDistance = wrapIndex(liveProgress - midpoint, length);
    const raw = 1 - behindDistance / length;
    const eased = Math.pow(clamp(raw, 0, 1), 1.55);
    return eased < 0.015 ? TRAIL_TAIL_ALPHA : clamp(eased * TRAIL_HEAD_ALPHA, TRAIL_TAIL_ALPHA, TRAIL_HEAD_ALPHA);
  }

  function ensureTrailData(refKey, color, count) {
    if (!trailState[refKey] || trailState[refKey].length !== count) {
      for (const entity of state.refs[refKey] || []) {
        viewer.entities.remove(entity);
      }
      state.refs[refKey] = [];
      trailState[refKey] = [];

      for (let i = 0; i < count; i += 1) {
        const segmentData = {
          positions: [Cesium.Cartesian3.ZERO, Cesium.Cartesian3.ZERO],
          alpha: 0,
        };
        const entity = viewer.entities.add({
          name: `${refKey} gradient segment`,
          polyline: {
            positions: new Cesium.CallbackProperty(() => segmentData.positions, false),
            width: 2.8,
            material: new Cesium.ColorMaterialProperty(
              new Cesium.CallbackProperty(() => color.withAlpha(segmentData.alpha), false),
            ),
            clampToGround: false,
            arcType: Cesium.ArcType.NONE,
          },
        });
        state.refs[refKey].push(entity);
        trailState[refKey].push(segmentData);
      }
    }

    return trailState[refKey];
  }

  function buildFullOrbitGradientSegments(path, progress, currentPosition) {
    const length = effectivePathLength(path);
    if (length < 2) return [];

    const liveProgress = closestProgressOnPath(path, currentPosition, progress);
    const wrappedProgress = wrapIndex(liveProgress, length);
    const activeIndex = Math.floor(wrappedProgress);
    const frac = wrappedProgress - activeIndex;
    const livePoint = currentPosition || samplePath(path, wrappedProgress);
    const segments = [];

    for (let i = 0; i < length; i += 1) {
      const p0 = path[i];
      const p1 = path[(i + 1) % length];

      if (i === activeIndex) {
        const behindEnd = frac > 1e-6 ? livePoint : p0;
        segments.push({
          start: p0,
          end: behindEnd,
          alpha: frac > 1e-6 ? trailAlphaAtMidpoint(i + frac * 0.5, wrappedProgress, length) : 0,
        });
        segments.push({
          start: livePoint,
          end: p1,
          alpha: frac < 1 - 1e-6 ? FUTURE_ALPHA : 0,
        });
      } else {
        const alpha = trailAlphaAtMidpoint(i + 0.5, wrappedProgress, length);
        segments.push({ start: p0, end: p1, alpha });
      }
    }

    return segments;
  }

  function syncLiveTrail(path, progress, currentPosition, refKey, color) {
    const length = effectivePathLength(path);
    if (length < 2) return;

    const displaySegments = buildFullOrbitGradientSegments(path, progress, currentPosition);
    const segmentData = ensureTrailData(refKey, color, displaySegments.length);

    for (let i = 0; i < displaySegments.length; i += 1) {
      const segment = displaySegments[i];
      segmentData[i].positions = pathToCartesianPair(segment.start, segment.end);
      segmentData[i].alpha = segment.alpha;
      state.refs[refKey][i].show = segment.alpha > 0.01;
    }
  }

  function syncLiveTrails(snapshot) {
    const geometry = snapshot?.geometry;
    if (!geometry) return;

    syncLiveTrail(
      geometry.target_orbit_km,
      geometry._target_path_progress ?? closestPathIndex(geometry.target_orbit_km, geometry.target_position_km),
      geometry.target_position_km,
      "targetTrailSegments",
      TARGET_COLOR,
    );
    syncLiveTrail(
      geometry.secondary_orbit_km,
      geometry._secondary_path_progress ?? closestPathIndex(geometry.secondary_orbit_km, geometry.secondary_position_km),
      geometry.secondary_position_km,
      "secondaryTrailSegments",
      SECONDARY_COLOR,
    );
  }

  updateTrailSegments = function patchedUpdateTrailSegments(path, progress, currentPosition, refKey, color) {
    syncLiveTrail(path, progress, currentPosition, refKey, color);
  };

  function ensureSeparationLine() {
    if (!state.refs.separation || state.refs.separationLivePatched) return;
    state.refs.separationLivePositions = [Cesium.Cartesian3.ZERO, Cesium.Cartesian3.ZERO];
    state.refs.separation.polyline.positions = new Cesium.CallbackProperty(
      () => state.refs.separationLivePositions,
      false,
    );
    state.refs.separation.polyline.material = new Cesium.ColorMaterialProperty(SEPARATION_COLOR);
    state.refs.separationLivePatched = true;
  }

  function syncSeparationLine(snapshot) {
    const geometry = snapshot?.geometry;
    if (!geometry || !state.refs.separation) return;
    ensureSeparationLine();
    state.refs.separationLivePositions = [
      kmToCartesian(geometry.target_position_km),
      kmToCartesian(geometry.secondary_position_km),
    ];
    state.refs.separation.show = true;
  }

  function positiveRiskMagnitude(snapshot) {
    const risk = Number(snapshot?.current_risk_log10);
    if (!Number.isFinite(risk)) return "—";
    return Math.abs(risk).toFixed(2);
  }

  function patchRiskMetric(snapshot) {
    const labels = metricsEl.querySelectorAll(".metric .label");
    for (const label of labels) {
      if (label.textContent.trim() !== "Risk log10" && label.textContent.trim() !== "Risk magnitude") continue;
      label.textContent = "Risk magnitude";
      const value = label.parentElement?.querySelector(".value");
      if (value) value.textContent = positiveRiskMagnitude(snapshot);
    }
  }

  renderMetrics = function patchedRenderMetrics(event, snapshot) {
    originalRenderMetrics(event, snapshot);
    patchRiskMetric(snapshot);
  };

  function cameraDistanceToCenter(snapshot) {
    if (!snapshot) return null;
    const center = eventCenter(snapshot);
    const distance = Cesium.Cartesian3.distance(viewer.camera.positionWC, center);
    return Number.isFinite(distance) ? distance : null;
  }

  let hasInitialCameraFocus = false;
  centerCameraOnSnapshot = function patchedCenterCameraOnSnapshot(snapshot) {
    if (!hasInitialCameraFocus) {
      hasInitialCameraFocus = true;
      originalCenterCameraOnSnapshot(snapshot);
      return;
    }

    const center = eventCenter(snapshot);
    const referenceSnapshot = state.displaySnapshot || snapshot;
    const range = clamp(
      cameraDistanceToCenter(referenceSnapshot) ?? cameraRangeForSnapshot(snapshot),
      viewer.scene.screenSpaceCameraController.minimumZoomDistance,
      viewer.scene.screenSpaceCameraController.maximumZoomDistance,
    );
    const direction = Cesium.Cartesian3.clone(viewer.camera.directionWC);
    const up = Cesium.Cartesian3.clone(viewer.camera.upWC);
    const offset = Cesium.Cartesian3.multiplyByScalar(direction, -range, new Cesium.Cartesian3());
    const destination = Cesium.Cartesian3.add(center, offset, new Cesium.Cartesian3());

    viewer.trackedEntity = undefined;
    viewer.camera.setView({
      destination,
      orientation: { direction, up },
    });
    applyLabelFade();
  };

  function setLabelVisual(entity, alpha, backgroundScale) {
    if (!entity?.label) return;
    const show = alpha > 0.025;
    const textAlpha = show ? alpha : 0;
    const bgAlpha = show ? backgroundScale * alpha : 0;
    entity.label.show = show;
    entity.label.showBackground = show && bgAlpha > 0.01;
    entity.label.fillColor = Cesium.Color.WHITE.withAlpha(textAlpha);
    entity.label.outlineColor = Cesium.Color.BLACK.withAlpha(textAlpha);
    entity.label.backgroundColor = Cesium.Color.BLACK.withAlpha(bgAlpha);
  }

  function paintLabels(alpha) {
    setLabelVisual(state.refs.targetObject, alpha, 0.45);
    setLabelVisual(state.refs.secondaryObject, alpha, 0.45);
    setLabelVisual(state.refs.closestApproach, state.hovered === "center" ? alpha : 0, 0.55);
  }

  applyLabelFade = function patchedApplyLabelFade() {
    if (!state.refs.targetObject || !state.displaySnapshot) return;
    labelFadeState.target = labelAlphaForCamera();
  };

  if (viewer.camera.changed?.removeEventListener) {
    viewer.camera.changed.removeEventListener(originalApplyLabelFade);
  }
  viewer.camera.changed.addEventListener(applyLabelFade);

  renderSnapshot = function patchedRenderSnapshot(snapshot, track = false) {
    // Do not let horizon changes recenter/zoom the camera every interpolation frame.
    originalRenderSnapshot(snapshot, false);
    syncLiveTrails(snapshot);
    syncSeparationLine(snapshot);
    patchRiskMetric(snapshot);
    applyLabelFade();
  };

  function liveFrame() {
    if (state.displaySnapshot) {
      syncLiveTrails(state.displaySnapshot);
      syncSeparationLine(state.displaySnapshot);
      labelFadeState.current += (labelFadeState.target - labelFadeState.current) * LABEL_FADE_EASE;
      paintLabels(clamp(labelFadeState.current, 0, 1));
      viewer.scene.requestRender();
    }
    requestAnimationFrame(liveFrame);
  }

  requestAnimationFrame(liveFrame);
  window.__BEACON_LIVE_TRAILS_PATCHED__ = true;
})();
