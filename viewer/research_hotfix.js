// Final viewer polish layer.
// Loaded after app.js/live_trails.js so it can correct interaction behavior without
// disturbing the research overlays.
(function patchResearchHotfixes() {
  const MAP_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Equirectangular_projection_SW.jpg/640px-Equirectangular_projection_SW.jpg";
  let scrubberTrackingWired = false;
  let panelScrollbarWired = false;
  let panelScrollbarDragging = false;
  let lastTrackedCenter = null;
  let lastTrackEventIndex = null;

  function injectHotfixCss() {
    if (document.getElementById("researchHotfixStyles")) return;
    const style = document.createElement("style");
    style.id = "researchHotfixStyles";
    style.textContent = `
      html,body{width:100%!important;max-width:100vw!important;overflow:hidden!important}
      #panel{scrollbar-width:none!important;-ms-overflow-style:none!important;padding-right:28px!important;clip-path:inset(0 round 18px)}
      #panel::-webkit-scrollbar{width:0!important;height:0!important;display:none!important}#panel::-webkit-scrollbar-button{display:none!important}
      #panel,#researchDock{overflow-x:hidden!important;contain:paint;max-width:calc(100vw - 36px)!important}
      #panel *,#researchDock *{max-width:100%;min-width:0}#panel select,#panel button,#researchDock button,#researchDock input{max-width:100%;min-width:0}
      #researchTimeline{left:clamp(420px,44vw,620px)!important;right:clamp(24px,26vw,390px)!important;width:auto!important;max-width:calc(100vw - 48px)!important;overflow:hidden!important;box-sizing:border-box!important}
      #researchTimeline input[type="range"]{display:block;width:calc(100% - 4px)!important;max-width:calc(100% - 4px)!important;min-width:0!important;margin-left:2px!important;margin-right:2px!important;box-sizing:border-box!important}
      #groundTrackWrap{position:relative;width:100%;height:150px;overflow:hidden;border-radius:10px;border:1px solid rgba(255,255,255,.10);background:#071a30;background-image:linear-gradient(rgba(5,12,25,.10),rgba(5,12,25,.30)),url("${MAP_IMAGE_URL}");background-size:100% 100%;background-position:center;background-repeat:no-repeat;box-shadow:inset 0 0 24px rgba(0,0,0,.28)}
      #groundTrackWrap canvas,#groundTrack{position:absolute;inset:0;width:100%!important;height:100%!important;border:0!important;border-radius:0!important;background:transparent!important}
      #beaconPanelScrollRail{position:fixed;width:8px;border-radius:999px;background:rgba(8,15,28,.36);box-shadow:inset 0 0 0 1px rgba(126,177,255,.12);z-index:140;pointer-events:none}
      #beaconPanelScrollThumb{position:absolute;left:1px;width:6px;border-radius:999px;background:linear-gradient(180deg,rgba(132,179,255,.95),rgba(87,165,255,.48));box-shadow:0 0 18px rgba(87,165,255,.24);pointer-events:auto;cursor:grab}#beaconPanelScrollThumb:active{cursor:grabbing;background:linear-gradient(180deg,rgba(172,204,255,1),rgba(87,165,255,.68))}
      @media(max-width:1050px){#researchTimeline{left:24px!important;right:24px!important}#researchDock{display:none!important}}`;
    document.head.appendChild(style);
  }

  function ensurePanelScrollbar() {
    const panel = document.getElementById("panel");
    if (!panel) return;

    let rail = document.getElementById("beaconPanelScrollRail");
    let thumb = document.getElementById("beaconPanelScrollThumb");
    if (!rail) {
      rail = document.createElement("div");
      rail.id = "beaconPanelScrollRail";
      thumb = document.createElement("div");
      thumb.id = "beaconPanelScrollThumb";
      rail.appendChild(thumb);
      document.body.appendChild(rail);
    }

    if (!panelScrollbarWired && thumb) {
      panelScrollbarWired = true;
      let startY = 0;
      let startScrollTop = 0;
      thumb.addEventListener("pointerdown", (event) => {
        panelScrollbarDragging = true;
        startY = event.clientY;
        startScrollTop = panel.scrollTop;
        thumb.setPointerCapture(event.pointerId);
        event.preventDefault();
      });
      thumb.addEventListener("pointermove", (event) => {
        if (!panelScrollbarDragging) return;
        const scrollMax = Math.max(1, panel.scrollHeight - panel.clientHeight);
        const railHeight = Math.max(1, rail.getBoundingClientRect().height);
        const thumbHeight = Math.max(44, railHeight * (panel.clientHeight / Math.max(panel.scrollHeight, 1)));
        const usable = Math.max(1, railHeight - thumbHeight);
        panel.scrollTop = startScrollTop + ((event.clientY - startY) / usable) * scrollMax;
        event.preventDefault();
      });
      thumb.addEventListener("pointerup", (event) => {
        panelScrollbarDragging = false;
        thumb.releasePointerCapture(event.pointerId);
      });
      thumb.addEventListener("pointercancel", () => {
        panelScrollbarDragging = false;
      });
    }
  }

  function updatePanelScrollbar() {
    const panel = document.getElementById("panel");
    const rail = document.getElementById("beaconPanelScrollRail");
    const thumb = document.getElementById("beaconPanelScrollThumb");
    if (!panel || !rail || !thumb) return;

    const scrollMax = panel.scrollHeight - panel.clientHeight;
    if (scrollMax <= 2) {
      rail.style.display = "none";
      return;
    }

    const rect = panel.getBoundingClientRect();
    const railInset = 14;
    const railHeight = Math.max(40, rect.height - railInset * 2);
    const thumbHeight = Math.max(46, railHeight * (panel.clientHeight / panel.scrollHeight));
    const y = (railHeight - thumbHeight) * (panel.scrollTop / scrollMax);

    rail.style.display = "block";
    rail.style.left = `${Math.round(rect.right - 14)}px`;
    rail.style.top = `${Math.round(rect.top + railInset)}px`;
    rail.style.height = `${Math.round(railHeight)}px`;
    thumb.style.height = `${Math.round(thumbHeight)}px`;
    thumb.style.transform = `translateY(${Math.round(y)}px)`;
  }

  function ensureMapWrapper() {
    const canvas = document.getElementById("groundTrack");
    if (!canvas || canvas.parentElement?.id === "groundTrackWrap") return;
    const wrapper = document.createElement("div");
    wrapper.id = "groundTrackWrap";
    canvas.parentNode.insertBefore(wrapper, canvas);
    wrapper.appendChild(canvas);
  }

  function project(point, width, height) {
    const r = Math.sqrt(point[0] ** 2 + point[1] ** 2 + point[2] ** 2) || 1;
    const lon = Math.atan2(point[1], point[0]);
    const lat = Math.asin(clamp(point[2] / r, -1, 1));
    return [width * (lon + Math.PI) / (2 * Math.PI), height * (0.5 - lat / Math.PI)];
  }

  function redrawMapOverlay() {
    const canvas = document.getElementById("groundTrack");
    const snapshot = state.displaySnapshot;
    const geometry = snapshot?.geometry;
    if (!canvas || !geometry) return;

    ensureMapWrapper();
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.strokeStyle = "rgba(205,230,255,.18)";
    ctx.lineWidth = 1;
    for (let lon = -120; lon <= 120; lon += 60) {
      const x = (lon + 180) / 360 * width;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let lat = -45; lat <= 45; lat += 45) {
      const y = (90 - lat) / 180 * height;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    function drawPath(points, color) {
      if (!Array.isArray(points) || points.length < 2) return;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      points.forEach((point, index) => {
        const p = project(point, width, height);
        if (index === 0) ctx.moveTo(p[0], p[1]);
        else ctx.lineTo(p[0], p[1]);
      });
      ctx.stroke();
    }

    drawPath(geometry.target_orbit_km, "rgba(87,165,255,.95)");
    drawPath(geometry.secondary_orbit_km, "rgba(255,184,77,.95)");

    for (const [point, color] of [[geometry.target_position_km, "#57a5ff"], [geometry.secondary_position_km, "#ffb84d"]]) {
      if (!Array.isArray(point)) continue;
      const p = project(point, width, height);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(p[0], p[1], 4.8, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "white";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    ctx.restore();
  }

  function resetTrackedCenter() {
    lastTrackedCenter = state.displaySnapshot ? eventCenter(state.displaySnapshot) : null;
    lastTrackEventIndex = state.eventIndex;
  }

  function translateTrackedCameraToSnapshot() {
    if (!trackToggle?.checked || !state.displaySnapshot) {
      lastTrackedCenter = null;
      return;
    }

    const center = eventCenter(state.displaySnapshot);
    if (!lastTrackedCenter || lastTrackEventIndex !== state.eventIndex) {
      lastTrackedCenter = center;
      lastTrackEventIndex = state.eventIndex;
      return;
    }

    const delta = Cesium.Cartesian3.subtract(center, lastTrackedCenter, new Cesium.Cartesian3());
    if (Cesium.Cartesian3.magnitude(delta) < 0.001) return;

    const camera = viewer.camera;
    const destination = Cesium.Cartesian3.add(camera.positionWC, delta, new Cesium.Cartesian3());
    const direction = Cesium.Cartesian3.clone(camera.directionWC);
    const up = Cesium.Cartesian3.clone(camera.upWC);

    viewer.trackedEntity = undefined;
    camera.setView({ destination, orientation: { direction, up } });
    lastTrackedCenter = center;
    viewer.scene.requestRender();
  }

  function styleLabels() {
    const labelEntities = [state.refs.targetObject, state.refs.secondaryObject, state.refs.closestApproach];
    for (const entity of labelEntities) {
      if (!entity?.label) continue;
      entity.label.font = "600 13px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
      entity.label.style = Cesium.LabelStyle.FILL_AND_OUTLINE;
      entity.label.outlineWidth = 3;
      entity.label.backgroundPadding = new Cesium.Cartesian2(8, 5);
      entity.label.pixelOffset = new Cesium.Cartesian2(0, -26);
      entity.label.scale = 1.0;
      entity.label.disableDepthTestDistance = Number.POSITIVE_INFINITY;
    }
  }

  function ensureUncertaintyHalo(name, color) {
    if (state.refs[name]) return state.refs[name];
    state.refs[name] = viewer.entities.add({
      name,
      position: Cesium.Cartesian3.ZERO,
      point: {
        pixelSize: 48,
        color: color.withAlpha(0.13),
        outlineColor: color.withAlpha(0.82),
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
    return state.refs[name];
  }

  function syncVisibleUncertainty(snapshot) {
    const geometry = snapshot?.geometry;
    if (!geometry) return;

    const uncertainty = Number(snapshot.predictive_std) || 0.04;
    const days = Math.max(0, Number(snapshot.time_to_tca_days) || 0);
    const haloSize = clamp(42 + uncertainty * 260 + days * 7, 42, 118);
    const radiusKm = clamp(90 + uncertainty * 1800 + days * 35, 120, 3400);

    const targetHalo = ensureUncertaintyHalo("researchTargetUncertaintyHalo", TARGET_COLOR);
    const secondaryHalo = ensureUncertaintyHalo("researchSecondaryUncertaintyHalo", SECONDARY_COLOR);
    targetHalo.position = new Cesium.ConstantPositionProperty(kmToCartesian(geometry.target_position_km));
    secondaryHalo.position = new Cesium.ConstantPositionProperty(kmToCartesian(geometry.secondary_position_km));
    targetHalo.point.pixelSize = new Cesium.ConstantProperty(haloSize);
    secondaryHalo.point.pixelSize = new Cesium.ConstantProperty(haloSize * 0.94);
    targetHalo.point.color = new Cesium.ConstantProperty(TARGET_COLOR.withAlpha(0.16));
    secondaryHalo.point.color = new Cesium.ConstantProperty(SECONDARY_COLOR.withAlpha(0.16));
    targetHalo.show = true;
    secondaryHalo.show = true;

    if (state.refs.researchTargetUncertainty?.ellipsoid) {
      state.refs.researchTargetUncertainty.show = true;
      state.refs.researchTargetUncertainty.position = new Cesium.ConstantPositionProperty(kmToCartesian(geometry.target_position_km));
      state.refs.researchTargetUncertainty.ellipsoid.radii = new Cesium.Cartesian3(radiusKm * 1000, radiusKm * 760, radiusKm * 520);
      state.refs.researchTargetUncertainty.ellipsoid.material = TARGET_COLOR.withAlpha(0.24);
      state.refs.researchTargetUncertainty.ellipsoid.outline = true;
      state.refs.researchTargetUncertainty.ellipsoid.outlineColor = TARGET_COLOR.withAlpha(0.78);
    }

    if (state.refs.researchSecondaryUncertainty?.ellipsoid) {
      state.refs.researchSecondaryUncertainty.show = true;
      state.refs.researchSecondaryUncertainty.position = new Cesium.ConstantPositionProperty(kmToCartesian(geometry.secondary_position_km));
      state.refs.researchSecondaryUncertainty.ellipsoid.radii = new Cesium.Cartesian3(radiusKm * 900, radiusKm * 680, radiusKm * 560);
      state.refs.researchSecondaryUncertainty.ellipsoid.material = SECONDARY_COLOR.withAlpha(0.24);
      state.refs.researchSecondaryUncertainty.ellipsoid.outline = true;
      state.refs.researchSecondaryUncertainty.ellipsoid.outlineColor = SECONDARY_COLOR.withAlpha(0.78);
    }
  }

  function wireScrubberTracking() {
    if (scrubberTrackingWired) return;
    const scrubber = document.getElementById("researchScrubber");
    if (!scrubber) return;
    scrubberTrackingWired = true;

    scrubber.addEventListener("pointerdown", () => {
      window.__BEACON_RESEARCH_SCRUBBING__ = true;
      resetTrackedCenter();
    });
    scrubber.addEventListener("input", () => {
      window.__BEACON_RESEARCH_SCRUBBING__ = true;
      translateTrackedCameraToSnapshot();
    });
    scrubber.addEventListener("change", () => {
      translateTrackedCameraToSnapshot();
    });
    scrubber.addEventListener("pointerup", () => {
      translateTrackedCameraToSnapshot();
      window.__BEACON_RESEARCH_SCRUBBING__ = false;
    });
    scrubber.addEventListener("pointercancel", () => {
      window.__BEACON_RESEARCH_SCRUBBING__ = false;
    });
  }

  if (typeof renderSnapshot === "function") {
    const previousRenderSnapshot = renderSnapshot;
    renderSnapshot = function hotfixedRenderSnapshot(snapshot, track = false) {
      const beforeCenter = state.displaySnapshot ? eventCenter(state.displaySnapshot) : null;
      previousRenderSnapshot(snapshot, false);
      redrawMapOverlay();
      styleLabels();
      syncVisibleUncertainty(snapshot);

      if (track && trackToggle.checked) {
        if (!lastTrackedCenter && beforeCenter) lastTrackedCenter = beforeCenter;
        translateTrackedCameraToSnapshot();
      }
    };
  }

  if (typeof transitionToHorizon === "function") {
    const previousTransitionToHorizon = transitionToHorizon;
    transitionToHorizon = function hotfixedTransitionToHorizon(index, options = {}) {
      const targetIndex = Number(index);
      resetTrackedCenter();
      if (targetIndex === 0) {
        previousTransitionToHorizon(targetIndex, { ...options, smooth: false });
        return;
      }
      previousTransitionToHorizon(targetIndex, options);
    };
  }

  function frame() {
    injectHotfixCss();
    ensurePanelScrollbar();
    updatePanelScrollbar();
    ensureMapWrapper();
    wireScrubberTracking();
    redrawMapOverlay();
    styleLabels();
    if (state.displaySnapshot) syncVisibleUncertainty(state.displaySnapshot);
    if (window.__BEACON_RESEARCH_SCRUBBING__) translateTrackedCameraToSnapshot();
    requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
  window.__BEACON_RESEARCH_HOTFIXES__ = true;
})();
