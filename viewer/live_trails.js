(function patchBeaconViewer() {
  const HEAD = 0.96;
  const TAIL = 0.018;
  const FUTURE = 0.025;
  const LABEL_EASE = 0.16;
  const originalRenderSnapshot = renderSnapshot;
  const originalRenderMetrics = renderMetrics;
  const originalApplyLabelFade = applyLabelFade;
  const trails = { targetTrailSegments: null, secondaryTrailSegments: null };
  const labelState = { target: 1, current: 1 };

  function d2(a, b) {
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;
  }

  function closestProgress(path, point, fallback) {
    const n = effectivePathLength(path);
    if (n < 2 || !Array.isArray(point)) return isFiniteNumber(fallback) ? Number(fallback) : 0;
    let best = 0;
    let bestD = Number.POSITIVE_INFINITY;
    for (let i = 0; i < n; i += 1) {
      const a = path[i];
      const b = path[(i + 1) % n];
      const ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      const ap = [point[0] - a[0], point[1] - a[1], point[2] - a[2]];
      const denom = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2;
      const t = denom > 0 ? clamp((ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / denom, 0, 1) : 0;
      const p = [a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t];
      const dist = d2(p, point);
      if (dist < bestD) {
        bestD = dist;
        best = i + t;
      }
    }
    return best;
  }

  function trailAlpha(mid, progress, n) {
    const behind = wrapIndex(progress - mid, n);
    const raw = 1 - behind / n;
    const eased = Math.pow(clamp(raw, 0, 1), 1.55);
    return eased < 0.015 ? TAIL : clamp(eased * HEAD, TAIL, HEAD);
  }

  function segmentList(path, progress, point) {
    const n = effectivePathLength(path);
    if (n < 2) return [];
    const live = closestProgress(path, point, progress);
    const wrapped = wrapIndex(live, n);
    const active = Math.floor(wrapped);
    const frac = wrapped - active;
    const dot = point || samplePath(path, wrapped);
    const out = [];
    for (let i = 0; i < n; i += 1) {
      const a = path[i];
      const b = path[(i + 1) % n];
      if (i === active) {
        out.push({ a, b: frac > 1e-6 ? dot : a, alpha: frac > 1e-6 ? trailAlpha(i + frac * 0.5, wrapped, n) : 0 });
        out.push({ a: dot, b, alpha: frac < 1 - 1e-6 ? FUTURE : 0 });
      } else {
        out.push({ a, b, alpha: trailAlpha(i + 0.5, wrapped, n) });
      }
    }
    return out;
  }

  function ensureTrail(refKey, color, count) {
    if (!trails[refKey] || trails[refKey].length !== count) {
      for (const e of state.refs[refKey] || []) viewer.entities.remove(e);
      state.refs[refKey] = [];
      trails[refKey] = [];
      for (let i = 0; i < count; i += 1) {
        const data = { positions: [Cesium.Cartesian3.ZERO, Cesium.Cartesian3.ZERO], alpha: 0 };
        state.refs[refKey].push(viewer.entities.add({
          name: `${refKey} live segment`,
          polyline: {
            positions: new Cesium.CallbackProperty(() => data.positions, false),
            width: 2.8,
            material: new Cesium.ColorMaterialProperty(new Cesium.CallbackProperty(() => color.withAlpha(data.alpha), false)),
            clampToGround: false,
            arcType: Cesium.ArcType.NONE,
          },
        }));
        trails[refKey].push(data);
      }
    }
    return trails[refKey];
  }

  function syncTrail(path, progress, point, refKey, color) {
    const parts = segmentList(path, progress, point);
    const data = ensureTrail(refKey, color, parts.length);
    for (let i = 0; i < parts.length; i += 1) {
      data[i].positions = pathToCartesianPair(parts[i].a, parts[i].b);
      data[i].alpha = parts[i].alpha;
      state.refs[refKey][i].show = parts[i].alpha > 0.01;
    }
  }

  function syncAll(snapshot) {
    const g = snapshot?.geometry;
    if (!g) return;
    syncTrail(g.target_orbit_km, g._target_path_progress ?? closestPathIndex(g.target_orbit_km, g.target_position_km), g.target_position_km, "targetTrailSegments", TARGET_COLOR);
    syncTrail(g.secondary_orbit_km, g._secondary_path_progress ?? closestPathIndex(g.secondary_orbit_km, g.secondary_position_km), g.secondary_position_km, "secondaryTrailSegments", SECONDARY_COLOR);
    if (state.refs.separation) {
      state.refs.separation.polyline.positions = new Cesium.CallbackProperty(() => [kmToCartesian(g.target_position_km), kmToCartesian(g.secondary_position_km)], false);
      state.refs.separation.polyline.material = new Cesium.ColorMaterialProperty(SEPARATION_COLOR);
    }
  }

  updateTrailSegments = syncTrail;

  function patchRisk(snapshot) {
    const risk = Math.abs(Number(snapshot?.current_risk_log10));
    for (const label of metricsEl.querySelectorAll(".metric .label")) {
      if (!["Risk log10", "Risk magnitude"].includes(label.textContent.trim())) continue;
      label.textContent = "Risk magnitude";
      const value = label.parentElement?.querySelector(".value");
      if (value) value.textContent = Number.isFinite(risk) ? risk.toFixed(2) : "—";
    }
  }

  renderMetrics = function patchedRenderMetrics(event, snapshot) {
    originalRenderMetrics(event, snapshot);
    patchRisk(snapshot);
  };

  function prop(color, alpha) {
    return new Cesium.ConstantProperty(color.withAlpha(alpha));
  }

  function label(entity, alpha, bgScale) {
    if (!entity?.label) return;
    const a = clamp(alpha, 0, 1);
    const show = a > 0.025;
    entity.label.show = show;
    entity.label.showBackground = show;
    entity.label.fillColor = prop(Cesium.Color.WHITE, a);
    entity.label.outlineColor = prop(Cesium.Color.BLACK, a);
    entity.label.backgroundColor = prop(Cesium.Color.BLACK, bgScale * a);
  }

  applyLabelFade = function patchedApplyLabelFade() {
    if (!state.refs.targetObject || !state.displaySnapshot) return;
    labelState.target = labelAlphaForCamera();
  };
  if (viewer.camera.changed?.removeEventListener) viewer.camera.changed.removeEventListener(originalApplyLabelFade);
  viewer.camera.changed.addEventListener(applyLabelFade);

  renderSnapshot = function patchedRenderSnapshot(snapshot) {
    originalRenderSnapshot(snapshot, false);
    syncAll(snapshot);
    patchRisk(snapshot);
    applyLabelFade();
  };

  function frame() {
    if (state.displaySnapshot) {
      syncAll(state.displaySnapshot);
      labelState.current += (labelState.target - labelState.current) * LABEL_EASE;
      label(state.refs.targetObject, labelState.current, 0.45);
      label(state.refs.secondaryObject, labelState.current, 0.45);
      label(state.refs.closestApproach, state.hovered === "center" ? labelState.current : 0, 0.55);
      viewer.scene.requestRender();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  window.__BEACON_LIVE_TRAILS_PATCHED__ = true;
})();
