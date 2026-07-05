// Live trail alignment patch for the Cesium viewer.
//
// app.js owns the viewer state and scene entities. This companion script replaces
// the trail renderer with one that projects the live moving object position onto
// the current interpolated orbit path every frame. It also hooks renderSnapshot
// directly so the trails are corrected immediately after the dots move.

(function patchLiveOrbitTrails() {
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

  function trailAlphaAtMidpoint(midpoint, progress, length) {
    const behindDistance = wrapIndex(progress - midpoint, length);
    const raw = 1 - behindDistance / length;
    const eased = Math.pow(clamp(raw, 0, 1), 1.8);
    return eased < 0.025 ? 0 : clamp(eased, 0, 0.96);
  }

  function buildLiveTrailSegments(path, progress, currentPosition) {
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
        // The visible trail head is the actual moving dot, not the nearest path node.
        if (frac > 1e-6) {
          segments.push({
            start: p0,
            end: livePoint,
            alpha: trailAlphaAtMidpoint(i + frac * 0.5, wrappedProgress, length),
          });
        }
      } else {
        const alpha = trailAlphaAtMidpoint(i + 0.5, wrappedProgress, length);
        if (alpha > 0) {
          segments.push({ start: p0, end: p1, alpha });
        }
      }
    }

    return segments;
  }

  function clearTrailSegments(refKey) {
    const existing = state.refs[refKey] || [];
    for (const entity of existing) {
      viewer.entities.remove(entity);
    }
    state.refs[refKey] = [];
  }

  function addTrailSegment(refKey, segment, color) {
    const entity = viewer.entities.add({
      name: `${refKey} live segment`,
      polyline: {
        positions: pathToCartesianPair(segment.start, segment.end),
        width: 2.7,
        material: new Cesium.ColorMaterialProperty(color.withAlpha(segment.alpha)),
        clampToGround: false,
        arcType: Cesium.ArcType.NONE,
      },
    });
    state.refs[refKey].push(entity);
  }

  function updateLiveTrailSegments(path, progress, currentPosition, refKey, color) {
    const length = effectivePathLength(path);
    if (length < 2) return;

    const displaySegments = buildLiveTrailSegments(path, progress, currentPosition);

    // Rebuild instead of mutating ConstantProperty values. This is heavier, but it
    // guarantees Cesium redraws the trail continuously while the dots interpolate.
    clearTrailSegments(refKey);
    for (const segment of displaySegments) {
      addTrailSegment(refKey, segment, color);
    }
  }

  function syncLiveTrails(snapshot) {
    if (!snapshot || !snapshot.geometry) return;
    const geometry = snapshot.geometry;

    updateLiveTrailSegments(
      geometry.target_orbit_km,
      geometry._target_path_progress ?? closestPathIndex(geometry.target_orbit_km, geometry.target_position_km),
      geometry.target_position_km,
      "targetTrailSegments",
      TARGET_COLOR,
    );
    updateLiveTrailSegments(
      geometry.secondary_orbit_km,
      geometry._secondary_path_progress ?? closestPathIndex(geometry.secondary_orbit_km, geometry.secondary_position_km),
      geometry.secondary_position_km,
      "secondaryTrailSegments",
      SECONDARY_COLOR,
    );

    viewer.scene.requestRender();
  }

  updateTrailSegments = updateLiveTrailSegments;

  // Belt-and-suspenders: make sure every animation frame corrects the trail after
  // app.js moves the dots. This avoids the old static path staying visible during
  // prediction-horizon interpolation on some Cesium/browser combinations.
  const originalRenderSnapshot = renderSnapshot;
  renderSnapshot = function patchedRenderSnapshot(snapshot, track = false) {
    originalRenderSnapshot(snapshot, track);
    syncLiveTrails(snapshot);
  };

  viewer.scene.preRender.addEventListener(() => {
    syncLiveTrails(state.displaySnapshot);
  });

  window.__BEACON_LIVE_TRAILS_PATCHED__ = true;
})();
