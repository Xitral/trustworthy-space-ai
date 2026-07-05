// Live trail alignment patch for the Cesium viewer.
//
// app.js owns the viewer state and scene entities. This small companion script
// replaces the trail renderer with one that projects the live moving object
// position onto the current interpolated orbit path every frame. That keeps the
// visible trail head locked to the dot during prediction-horizon interpolation.

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
        // Past/current segment: the visible trail must end exactly at the live dot.
        segments.push({
          start: p0,
          end: livePoint,
          alpha: frac <= 1e-6 ? 0 : trailAlphaAtMidpoint(i + frac * 0.5, wrappedProgress, length),
        });

        // Future side starts at the dot but is fully hidden so the trail never
        // visually extends beyond the object.
        segments.push({
          start: livePoint,
          end: p1,
          alpha: 0,
        });
      } else {
        segments.push({
          start: p0,
          end: p1,
          alpha: trailAlphaAtMidpoint(i + 0.5, wrappedProgress, length),
        });
      }
    }

    return segments;
  }

  function updateLiveTrailSegments(path, progress, currentPosition, refKey, color) {
    const length = effectivePathLength(path);
    if (length < 2) return;

    const displaySegments = buildLiveTrailSegments(path, progress, currentPosition);
    const segments = ensureTrailSegments(refKey, displaySegments.length, color);

    for (let i = 0; i < displaySegments.length; i += 1) {
      const segment = displaySegments[i];
      segments[i].polyline.positions = new Cesium.ConstantProperty(
        pathToCartesianPair(segment.start, segment.end),
      );
      segments[i].polyline.material = new Cesium.ColorMaterialProperty(
        color.withAlpha(segment.alpha),
      );
      segments[i].show = segment.alpha > 0;
    }
  }

  updateTrailSegments = updateLiveTrailSegments;
})();
