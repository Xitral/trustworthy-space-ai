const DATA_URL = "data/conjunction_events.json";

const EARTH_RADIUS_M = 6_371_000;
const INTERPOLATION_MS = 950;
const TARGET_COLOR = Cesium.Color.fromCssColorString("#57a5ff");
const SECONDARY_COLOR = Cesium.Color.fromCssColorString("#ffb84d");
const SEPARATION_COLOR = Cesium.Color.fromCssColorString("#ff5b6e");
const CA_COLOR = Cesium.Color.fromCssColorString("#ffffff");
const EARTH_COLOR = Cesium.Color.fromCssColorString("#163f7a");
const ATMOSPHERE_COLOR = Cesium.Color.fromCssColorString("#6eb6ff").withAlpha(0.10);

const SAMPLE_DATA = {
  metadata: {
    viewer: "BEACON CesiumJS conjunction triage viewer",
    horizon_order: ["early", "3d", "2d", "1d"],
    geometry_modes: ["sample_reference_orbit"],
    coordinate_note: "Sample data shown. Run python src/export_orbit_viewer.py to export real BEACON viewer data.",
    display_scale_note: "Small separations can be scaled for visibility.",
  },
  events: [
    {
      event_id: "sample",
      display_name: "Sample event",
      high_risk: 1,
      final_risk_log10: -4.8,
      snapshots: [
        makeSampleSnapshot("early", 4.6, -6.2, 0.18, 0.11, 0),
        makeSampleSnapshot("3d", 3.1, -5.7, 0.31, 0.09, 25),
        makeSampleSnapshot("2d", 2.0, -5.2, 0.52, 0.08, 50),
        makeSampleSnapshot("1d", 1.0, -4.8, 0.73, 0.06, 75),
      ],
    },
  ],
};

function makeSampleSnapshot(horizon, timeToTca, risk, modelProbability, predictiveStd, phaseShift) {
  const radius = 7071;
  const targetOrbit = [];
  const secondaryOrbit = [];

  for (let i = 0; i < 144; i += 1) {
    const theta = (i / 143) * Math.PI * 2;
    const x = radius * Math.cos(theta);
    const y = radius * Math.sin(theta);
    const z = 900 * Math.sin(theta + 0.7);
    targetOrbit.push([x, y, z]);
    secondaryOrbit.push([x + 55 + phaseShift, y - 80, z + 120]);
  }

  const p = targetOrbit[30 + Math.floor(phaseShift / 5)];
  const q = secondaryOrbit[30 + Math.floor(phaseShift / 5)];

  return {
    horizon,
    time_to_tca_days: timeToTca,
    current_risk_log10: risk,
    current_risk_probability: Math.pow(10, risk),
    final_risk_log10: -4.8,
    model_probability: modelProbability,
    predictive_std: predictiveStd,
    geometry: {
      mode: "sample_reference_orbit",
      target_position_km: p,
      secondary_position_km: q,
      closest_approach_km: [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2, (p[2] + q[2]) / 2],
      target_orbit_km: targetOrbit,
      secondary_orbit_km: secondaryOrbit,
      relative_distance_km: 1.4,
      display_relative_scale: 120,
      display_relative_distance_km: 168,
    },
  };
}

const viewer = new Cesium.Viewer("cesiumContainer", {
  animation: false,
  timeline: false,
  baseLayerPicker: false,
  geocoder: false,
  sceneModePicker: false,
  navigationHelpButton: false,
  infoBox: false,
  selectionIndicator: false,
  skyAtmosphere: false,
});

// The default Cesium globe can appear black or fail without an imagery token/source.
// Hide it and draw a local reference Earth so the viewer is reliable offline.
viewer.scene.globe.show = false;
viewer.scene.moon.show = false;
viewer.scene.screenSpaceCameraController.minimumZoomDistance = 450_000;
viewer.scene.screenSpaceCameraController.maximumZoomDistance = 90_000_000;

const state = {
  data: null,
  eventIndex: 0,
  horizonIndex: 0,
  playTimer: null,
  animationFrame: null,
  displaySnapshot: null,
  refs: {},
};

const eventSelect = document.getElementById("eventSelect");
const horizonSelect = document.getElementById("horizonSelect");
const metricsEl = document.getElementById("metrics");
const metadataEl = document.getElementById("metadata");
const playButton = document.getElementById("playButton");
const homeButton = document.getElementById("homeButton");
const trackToggle = document.getElementById("trackToggle");
const smoothToggle = document.getElementById("smoothToggle");

function kmToCartesian(point) {
  return new Cesium.Cartesian3(point[0] * 1000, point[1] * 1000, point[2] * 1000);
}

function pathToCartesian(points) {
  return points.map(kmToCartesian);
}

function formatNumber(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const number = Number(value);
  if (Math.abs(number) < 0.001 && number !== 0) return number.toExponential(2);
  return number.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function riskColor(snapshot) {
  const risk = snapshot.current_risk_log10;

  if (risk !== null && risk !== undefined) {
    if (risk >= -5) return Cesium.Color.RED;
    if (risk >= -6) return Cesium.Color.ORANGE;
  }

  if (snapshot.model_probability !== null && snapshot.model_probability > 0.5) {
    return Cesium.Color.ORANGE;
  }

  return TARGET_COLOR;
}

function currentEvent() {
  return state.data.events[state.eventIndex];
}

function currentSnapshot() {
  return currentEvent().snapshots[state.horizonIndex];
}

function easeInOut(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function lerp(a, b, t) {
  if (a === null || a === undefined || b === null || b === undefined) return t < 1 ? a : b;
  const x = Number(a);
  const y = Number(b);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return t < 1 ? a : b;
  return x + (y - x) * t;
}

function lerpPoint(a, b, t) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return t < 1 ? a : b;
  return a.map((value, index) => lerp(value, b[index], t));
}

function lerpPath(a, b, t) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return t < 1 ? a : b;
  return a.map((point, index) => lerpPoint(point, b[index], t));
}

function interpolatedSnapshot(from, to, t) {
  const geometryA = from.geometry;
  const geometryB = to.geometry;

  return {
    ...to,
    time_to_tca_days: lerp(from.time_to_tca_days, to.time_to_tca_days, t),
    current_risk_log10: lerp(from.current_risk_log10, to.current_risk_log10, t),
    current_risk_probability: lerp(from.current_risk_probability, to.current_risk_probability, t),
    final_risk_log10: lerp(from.final_risk_log10, to.final_risk_log10, t),
    model_probability: lerp(from.model_probability, to.model_probability, t),
    predictive_std: lerp(from.predictive_std, to.predictive_std, t),
    geometry: {
      ...geometryB,
      target_position_km: lerpPoint(geometryA.target_position_km, geometryB.target_position_km, t),
      secondary_position_km: lerpPoint(geometryA.secondary_position_km, geometryB.secondary_position_km, t),
      closest_approach_km: lerpPoint(geometryA.closest_approach_km, geometryB.closest_approach_km, t),
      target_orbit_km: lerpPath(geometryA.target_orbit_km, geometryB.target_orbit_km, t),
      secondary_orbit_km: lerpPath(geometryA.secondary_orbit_km, geometryB.secondary_orbit_km, t),
      relative_distance_km: lerp(geometryA.relative_distance_km, geometryB.relative_distance_km, t),
      display_relative_scale: lerp(geometryA.display_relative_scale, geometryB.display_relative_scale, t),
      display_relative_distance_km: lerp(geometryA.display_relative_distance_km, geometryB.display_relative_distance_km, t),
    },
  };
}

function stopAnimation() {
  if (state.animationFrame) {
    cancelAnimationFrame(state.animationFrame);
    state.animationFrame = null;
  }
}

function ensureSceneEntities() {
  if (state.refs.targetOrbit) return;

  state.refs.earth = viewer.entities.add({
    name: "Earth reference sphere",
    position: Cesium.Cartesian3.ZERO,
    ellipsoid: {
      radii: new Cesium.Cartesian3(EARTH_RADIUS_M, EARTH_RADIUS_M, EARTH_RADIUS_M),
      material: EARTH_COLOR,
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString("#6eb6ff").withAlpha(0.35),
    },
  });

  state.refs.atmosphere = viewer.entities.add({
    name: "Atmosphere reference shell",
    position: Cesium.Cartesian3.ZERO,
    ellipsoid: {
      radii: new Cesium.Cartesian3(EARTH_RADIUS_M * 1.025, EARTH_RADIUS_M * 1.025, EARTH_RADIUS_M * 1.025),
      material: ATMOSPHERE_COLOR,
    },
  });

  state.refs.targetOrbit = viewer.entities.add({
    name: "Target orbit",
    polyline: {
      positions: [Cesium.Cartesian3.ZERO, Cesium.Cartesian3.ZERO],
      width: 2.5,
      material: TARGET_COLOR.withAlpha(0.82),
      clampToGround: false,
    },
  });

  state.refs.secondaryOrbit = viewer.entities.add({
    name: "Secondary orbit",
    polyline: {
      positions: [Cesium.Cartesian3.ZERO, Cesium.Cartesian3.ZERO],
      width: 2.5,
      material: SECONDARY_COLOR.withAlpha(0.88),
      clampToGround: false,
    },
  });

  state.refs.separation = viewer.entities.add({
    name: "Displayed separation",
    polyline: {
      positions: [Cesium.Cartesian3.ZERO, Cesium.Cartesian3.ZERO],
      width: 3,
      material: SEPARATION_COLOR,
    },
  });

  state.refs.targetObject = viewer.entities.add({
    name: "Target object",
    position: Cesium.Cartesian3.ZERO,
    point: { pixelSize: 11, color: TARGET_COLOR, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
    label: {
      text: "Target",
      font: "14px sans-serif",
      pixelOffset: new Cesium.Cartesian2(0, -22),
      fillColor: Cesium.Color.WHITE,
      showBackground: true,
      backgroundColor: Cesium.Color.BLACK.withAlpha(0.45),
    },
  });

  state.refs.secondaryObject = viewer.entities.add({
    name: "Secondary object",
    position: Cesium.Cartesian3.ZERO,
    point: { pixelSize: 10, color: SECONDARY_COLOR, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
    label: {
      text: "Secondary",
      font: "14px sans-serif",
      pixelOffset: new Cesium.Cartesian2(0, -22),
      fillColor: Cesium.Color.WHITE,
      showBackground: true,
      backgroundColor: Cesium.Color.BLACK.withAlpha(0.45),
    },
  });

  state.refs.closestApproach = viewer.entities.add({
    name: "Closest approach marker",
    position: Cesium.Cartesian3.ZERO,
    point: { pixelSize: 8, color: CA_COLOR, outlineColor: SEPARATION_COLOR, outlineWidth: 2 },
  });
}

function populateControls() {
  eventSelect.innerHTML = "";

  state.data.events.forEach((event, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${event.display_name || `Event ${event.event_id}`} ${event.high_risk ? "• high risk" : ""}`;
    eventSelect.appendChild(option);
  });

  eventSelect.value = String(state.eventIndex);
  populateHorizonSelect();
}

function populateHorizonSelect() {
  const event = currentEvent();
  horizonSelect.innerHTML = "";

  event.snapshots.forEach((snapshot, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = snapshot.horizon;
    horizonSelect.appendChild(option);
  });

  state.horizonIndex = Math.min(state.horizonIndex, event.snapshots.length - 1);
  horizonSelect.value = String(state.horizonIndex);
}

function renderMetrics(event, snapshot) {
  const geometry = snapshot.geometry;
  metricsEl.innerHTML = `
    <div class="metric"><span class="label">Current risk</span><span class="value">${formatNumber(snapshot.current_risk_log10)}</span></div>
    <div class="metric"><span class="label">Risk probability</span><span class="value">${formatNumber(snapshot.current_risk_probability, 6)}</span></div>
    <div class="metric"><span class="label">Model score</span><span class="value">${formatPercent(snapshot.model_probability)}</span></div>
    <div class="metric"><span class="label">Uncertainty</span><span class="value">${formatPercent(snapshot.predictive_std)}</span></div>
    <div class="metric"><span class="label">Time to TCA</span><span class="value">${formatNumber(snapshot.time_to_tca_days, 2)} d</span></div>
    <div class="metric"><span class="label">High-risk label</span><span class="value">${event.high_risk ? "yes" : "no"}</span></div>
    <div class="metric"><span class="label">Relative distance</span><span class="value">${formatNumber(geometry.relative_distance_km, 3)} km</span></div>
    <div class="metric"><span class="label">Display scale</span><span class="value">${formatNumber(geometry.display_relative_scale, 1)}×</span></div>
    <div class="metric wide"><span class="label">Geometry source</span><span class="value">${geometry.mode.replaceAll("_", " ")}</span></div>
  `;

  const notes = [state.data.metadata.coordinate_note, state.data.metadata.display_scale_note].filter(Boolean).join(" ");
  metadataEl.innerHTML = `<h2>Notes</h2><p>${notes}</p>`;
}

function updateEntityGeometry(snapshot) {
  ensureSceneEntities();

  const geometry = snapshot.geometry;
  const target = kmToCartesian(geometry.target_position_km);
  const secondary = kmToCartesian(geometry.secondary_position_km);
  const closest = kmToCartesian(geometry.closest_approach_km);

  viewer.entities.suspendEvents();

  state.refs.targetOrbit.polyline.positions = new Cesium.ConstantProperty(pathToCartesian(geometry.target_orbit_km));
  state.refs.secondaryOrbit.polyline.positions = new Cesium.ConstantProperty(pathToCartesian(geometry.secondary_orbit_km));
  state.refs.separation.polyline.positions = new Cesium.ConstantProperty([target, secondary]);

  state.refs.targetObject.position = new Cesium.ConstantPositionProperty(target);
  state.refs.targetObject.point.color = new Cesium.ConstantProperty(riskColor(snapshot));

  state.refs.secondaryObject.position = new Cesium.ConstantPositionProperty(secondary);
  state.refs.closestApproach.position = new Cesium.ConstantPositionProperty(closest);

  viewer.entities.resumeEvents();
  viewer.scene.requestRender();
}

function renderSnapshot(snapshot, track = false) {
  state.displaySnapshot = snapshot;
  updateEntityGeometry(snapshot);
  renderMetrics(currentEvent(), snapshot);

  if (track && trackToggle.checked) {
    centerCameraOnSnapshot(snapshot, false);
  }
}

function renderScene(fly = false) {
  stopAnimation();
  const snapshot = currentSnapshot();
  renderSnapshot(snapshot, false);

  if (fly || trackToggle.checked) {
    centerCameraOnSnapshot(snapshot, fly);
  }
}

function cameraRangeForSnapshot(snapshot) {
  const geometry = snapshot.geometry;
  const closest = kmToCartesian(geometry.closest_approach_km);
  const target = kmToCartesian(geometry.target_position_km);
  const secondary = kmToCartesian(geometry.secondary_position_km);
  const separation = Cesium.Cartesian3.distance(target, secondary);
  const orbitalRadius = Cesium.Cartesian3.magnitude(closest);
  return Math.max(2_800_000, Math.min(18_000_000, orbitalRadius * 0.30 + separation * 5));
}

function centerCameraOnSnapshot(snapshot, animated = true) {
  const closest = kmToCartesian(snapshot.geometry.closest_approach_km);
  const range = cameraRangeForSnapshot(snapshot);
  const offset = new Cesium.HeadingPitchRange(0.0, -0.42, range);

  if (animated) {
    viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(closest, 250_000), {
      duration: 0.65,
      offset,
    });
  } else {
    viewer.camera.lookAt(closest, offset);
  }
}

function focusEvent() {
  trackToggle.checked = true;
  centerCameraOnSnapshot(state.displaySnapshot || currentSnapshot(), true);
}

function transitionToHorizon(index, options = {}) {
  const targetIndex = Number(index);
  const event = currentEvent();
  const from = state.displaySnapshot || currentSnapshot();
  const to = event.snapshots[targetIndex];
  const smooth = smoothToggle.checked && options.smooth !== false;

  stopAnimation();
  state.horizonIndex = targetIndex;
  horizonSelect.value = String(targetIndex);

  if (!smooth) {
    renderSnapshot(to, true);
    return;
  }

  const startTime = performance.now();

  function frame(now) {
    const raw = Math.min(1, (now - startTime) / INTERPOLATION_MS);
    const eased = easeInOut(raw);
    const snapshot = interpolatedSnapshot(from, to, eased);
    renderSnapshot(snapshot, true);

    if (raw < 1) {
      state.animationFrame = requestAnimationFrame(frame);
    } else {
      state.animationFrame = null;
      renderSnapshot(to, true);
    }
  }

  state.animationFrame = requestAnimationFrame(frame);
}

function setEvent(index) {
  stopAnimation();
  state.eventIndex = Number(index);
  state.horizonIndex = 0;
  state.displaySnapshot = currentSnapshot();
  populateHorizonSelect();
  renderScene(true);
}

function setHorizon(index) {
  transitionToHorizon(index, { smooth: smoothToggle.checked });
}

function togglePlay() {
  if (state.playTimer) {
    clearInterval(state.playTimer);
    state.playTimer = null;
    playButton.textContent = "Play horizons";
    return;
  }

  trackToggle.checked = true;
  playButton.textContent = "Pause";

  state.playTimer = setInterval(() => {
    const event = currentEvent();
    const next = (state.horizonIndex + 1) % event.snapshots.length;
    transitionToHorizon(next, { smooth: smoothToggle.checked });
  }, smoothToggle.checked ? 1250 : 900);
}

async function loadData() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn("Using sample data because exported viewer data was not found.", error);
    return SAMPLE_DATA;
  }
}

loadData().then((data) => {
  state.data = data;
  if (!state.data.events || state.data.events.length === 0) {
    throw new Error("Viewer dataset contains no events.");
  }

  ensureSceneEntities();
  populateControls();
  state.displaySnapshot = currentSnapshot();
  renderScene(true);
});

eventSelect.addEventListener("change", (event) => setEvent(event.target.value));
horizonSelect.addEventListener("change", (event) => setHorizon(event.target.value));
playButton.addEventListener("click", togglePlay);
homeButton.addEventListener("click", focusEvent);
trackToggle.addEventListener("change", () => {
  if (trackToggle.checked) {
    centerCameraOnSnapshot(state.displaySnapshot || currentSnapshot(), true);
  } else {
    viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  }
});
smoothToggle.addEventListener("change", () => stopAnimation());
