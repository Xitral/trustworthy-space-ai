(function patchResearchViewer() {
  const HEAD = 0.96;
  const TAIL = 0.018;
  const FUTURE = 0.025;
  const LABEL_EASE = 0.075;
  const originalRenderSnapshot = renderSnapshot;
  const originalRenderMetrics = renderMetrics;
  const originalApplyLabelFade = applyLabelFade;
  const trails = { targetTrailSegments: null, secondaryTrailSegments: null };
  const labelState = { target: 1, current: 1 };
  const ui = { ready: false, scrubActive: false, scrubValue: null, lastEventIndex: null };

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

  function heatForSnapshot(snapshot) {
    const risk = Number(snapshot?.current_risk_log10);
    const uncertainty = Number(snapshot?.predictive_std) || 0;
    const model = Number(snapshot?.model_probability) || 0;
    const riskHeat = Number.isFinite(risk) ? clamp((risk + 7.5) / 4.5, 0, 1) : 0;
    return clamp(riskHeat * 0.68 + uncertainty * 1.6 + model * 0.18, 0, 1);
  }

  function blendColor(base, heat, amount) {
    const warm = heat > 0.65 ? Cesium.Color.fromCssColorString("#ff5b6e") : Cesium.Color.fromCssColorString("#ffd166");
    return Cesium.Color.lerp(base, warm, clamp(amount, 0, 1), new Cesium.Color());
  }

  function directionFor(refKey) {
    const progressKey = refKey === "secondaryTrailSegments" ? "_secondary_path_progress" : "_target_path_progress";
    const event = currentEvent?.();
    const snapshots = event?.snapshots || [];
    for (let i = 1; i < snapshots.length; i += 1) {
      const a = Number(snapshots[i - 1]?.geometry?.[progressKey]);
      const b = Number(snapshots[i]?.geometry?.[progressKey]);
      if (Number.isFinite(a) && Number.isFinite(b) && Math.abs(b - a) > 0.001) return Math.sign(b - a);
    }
    return 1;
  }

  function trailAlpha(mid, progress, n, direction) {
    const behind = direction >= 0 ? wrapIndex(progress - mid, n) : wrapIndex(mid - progress, n);
    const raw = 1 - behind / n;
    const eased = Math.pow(clamp(raw, 0, 1), 1.55);
    return eased < 0.015 ? TAIL : clamp(eased * HEAD, TAIL, HEAD);
  }

  function segmentList(path, progress, point, heat, direction) {
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
        if (direction >= 0) {
          const alpha = frac > 1e-6 ? trailAlpha(i + frac * 0.5, wrapped, n, direction) : 0;
          out.push({ a, b: frac > 1e-6 ? dot : a, alpha, heat: heat * alpha });
          out.push({ a: dot, b, alpha: frac < 1 - 1e-6 ? FUTURE : 0, heat: heat * 0.15 });
        } else {
          const alpha = frac < 1 - 1e-6 ? trailAlpha(i + frac + (1 - frac) * 0.5, wrapped, n, direction) : 0;
          out.push({ a: dot, b, alpha, heat: heat * alpha });
          out.push({ a, b: frac > 1e-6 ? dot : a, alpha: frac > 1e-6 ? FUTURE : 0, heat: heat * 0.15 });
        }
      } else {
        const alpha = trailAlpha(i + 0.5, wrapped, n, direction);
        out.push({ a, b, alpha, heat: heat * alpha });
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
        const data = { positions: [Cesium.Cartesian3.ZERO, Cesium.Cartesian3.ZERO], color: color.withAlpha(0) };
        state.refs[refKey].push(viewer.entities.add({
          name: `${refKey} research gradient segment`,
          polyline: {
            positions: new Cesium.CallbackProperty(() => data.positions, false),
            width: 2.8,
            material: new Cesium.ColorMaterialProperty(new Cesium.CallbackProperty(() => data.color, false)),
            clampToGround: false,
            arcType: Cesium.ArcType.NONE,
          },
        }));
        trails[refKey].push(data);
      }
    }
    return trails[refKey];
  }

  function syncTrail(path, progress, point, refKey, color, heat = 0) {
    const parts = segmentList(path, progress, point, heat, directionFor(refKey));
    const data = ensureTrail(refKey, color, parts.length);
    for (let i = 0; i < parts.length; i += 1) {
      const c = blendColor(color, heat, parts[i].heat).withAlpha(parts[i].alpha);
      data[i].positions = pathToCartesianPair(parts[i].a, parts[i].b);
      data[i].color = c;
      state.refs[refKey][i].show = parts[i].alpha > 0.01;
    }
  }

  function ensureResearchEntities() {
    if (state.refs.researchTargetUncertainty) return;
    state.refs.researchTargetUncertainty = viewer.entities.add({ position: Cesium.Cartesian3.ZERO, ellipsoid: { radii: new Cesium.Cartesian3(1, 1, 1), material: TARGET_COLOR.withAlpha(0.15), outline: true, outlineColor: TARGET_COLOR.withAlpha(0.36) } });
    state.refs.researchSecondaryUncertainty = viewer.entities.add({ position: Cesium.Cartesian3.ZERO, ellipsoid: { radii: new Cesium.Cartesian3(1, 1, 1), material: SECONDARY_COLOR.withAlpha(0.15), outline: true, outlineColor: SECONDARY_COLOR.withAlpha(0.36) } });
    state.refs.researchTcaVolume = viewer.entities.add({ position: Cesium.Cartesian3.ZERO, ellipsoid: { radii: new Cesium.Cartesian3(1, 1, 1), material: SEPARATION_COLOR.withAlpha(0.12), outline: true, outlineColor: SEPARATION_COLOR.withAlpha(0.42) } });
  }

  function syncResearchEntities(snapshot) {
    const g = snapshot?.geometry;
    if (!g) return;
    ensureResearchEntities();
    const u = Number(snapshot.predictive_std) || 0.04;
    const days = Math.max(0, Number(snapshot.time_to_tca_days) || 0);
    const rel = Math.max(1, Number(g.display_relative_distance_km || g.relative_distance_km) || 1);
    const radiusKm = clamp(55 + u * 1100 + days * 18 + rel * 0.08, 45, 2400);
    const mid = lerpPoint(g.target_position_km, g.secondary_position_km, 0.5);
    const corridorKm = clamp(rel * 0.8 + radiusKm * 0.7, 90, 4200);
    state.refs.researchTargetUncertainty.position = new Cesium.ConstantPositionProperty(kmToCartesian(g.target_position_km));
    state.refs.researchTargetUncertainty.ellipsoid.radii = new Cesium.Cartesian3(radiusKm * 1000, radiusKm * 720, radiusKm * 480);
    state.refs.researchSecondaryUncertainty.position = new Cesium.ConstantPositionProperty(kmToCartesian(g.secondary_position_km));
    state.refs.researchSecondaryUncertainty.ellipsoid.radii = new Cesium.Cartesian3(radiusKm * 850, radiusKm * 660, radiusKm * 560);
    state.refs.researchTcaVolume.position = new Cesium.ConstantPositionProperty(kmToCartesian(mid));
    state.refs.researchTcaVolume.ellipsoid.radii = new Cesium.Cartesian3(corridorKm * 1000, corridorKm * 1000, corridorKm * 1000);
  }

  function syncSeparation(snapshot) {
    const g = snapshot?.geometry;
    if (!g || !state.refs.separation) return;
    const positions = [kmToCartesian(g.target_position_km), kmToCartesian(g.secondary_position_km)];
    state.refs.separation.show = true;
    state.refs.separation.polyline.positions = new Cesium.ConstantProperty(positions);
    state.refs.separation.polyline.width = 2.4;
    state.refs.separation.polyline.material = new Cesium.ColorMaterialProperty(SEPARATION_COLOR.withAlpha(0.46));
    state.refs.separation.polyline.depthFailMaterial = new Cesium.ColorMaterialProperty(SEPARATION_COLOR.withAlpha(0.22));
  }

  function syncAll(snapshot) {
    const g = snapshot?.geometry;
    if (!g) return;
    const heat = heatForSnapshot(snapshot);
    syncTrail(g.target_orbit_km, g._target_path_progress ?? closestPathIndex(g.target_orbit_km, g.target_position_km), g.target_position_km, "targetTrailSegments", TARGET_COLOR, heat);
    syncTrail(g.secondary_orbit_km, g._secondary_path_progress ?? closestPathIndex(g.secondary_orbit_km, g.secondary_position_km), g.secondary_position_km, "secondaryTrailSegments", SECONDARY_COLOR, heat);
    syncSeparation(snapshot);
    syncResearchEntities(snapshot);
  }

  updateTrailSegments = syncTrail;

  function injectResearchCss() {
    if (document.getElementById("researchFeatureStyles")) return;
    const style = document.createElement("style");
    style.id = "researchFeatureStyles";
    style.textContent = `
      #panel,#researchDock{scrollbar-width:thin;scrollbar-color:rgba(120,166,255,.50) rgba(8,15,28,.30)}
      #panel::-webkit-scrollbar,#researchDock::-webkit-scrollbar{width:10px}#panel::-webkit-scrollbar-track,#researchDock::-webkit-scrollbar-track{background:rgba(8,15,28,.32);border-radius:999px;margin:14px 0}#panel::-webkit-scrollbar-thumb,#researchDock::-webkit-scrollbar-thumb{background:linear-gradient(180deg,rgba(120,166,255,.72),rgba(87,165,255,.32));border:2px solid rgba(8,15,28,.72);border-radius:999px}#panel::-webkit-scrollbar-thumb:hover,#researchDock::-webkit-scrollbar-thumb:hover{background:linear-gradient(180deg,rgba(120,166,255,.94),rgba(87,165,255,.52))}
      .metrics .metric{min-height:86px;display:flex;flex-direction:column;align-items:flex-start}.metrics .metric .value{margin-top:auto;line-height:1.15}.metrics .metric.wide{min-height:70px}
      #researchDock{position:fixed;right:18px;top:72px;width:350px;max-height:calc(100vh - 96px);overflow:auto;z-index:60;color:#eef6ff;font-family:Inter,system-ui,sans-serif;pointer-events:auto;padding-right:4px}
      #researchDock .card{background:rgba(8,15,28,.82);border:1px solid rgba(126,177,255,.24);box-shadow:0 18px 50px rgba(0,0,0,.30);backdrop-filter:blur(14px);border-radius:16px;padding:12px 14px;margin-bottom:10px}
      #researchDock h3{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#9ec6ff;margin:0 0 8px}
      #researchDock p,#researchDock li{font-size:12px;line-height:1.35;color:#cfe1ff;margin:4px 0}.research-muted{color:#7f93b7!important}.research-value{font-weight:700;color:#fff}.research-row{display:flex;justify-content:space-between;gap:8px;margin:5px 0}.research-small{font-size:11px;color:#9fb4d7}.research-event{display:block;width:100%;text-align:left;background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.08);color:#eaf3ff;border-radius:10px;padding:7px;margin:5px 0;cursor:pointer}.research-event:hover{background:rgba(87,165,255,.16)}
      #researchTimeline{position:fixed;left:620px;right:390px;bottom:22px;z-index:61;background:rgba(8,15,28,.82);border:1px solid rgba(126,177,255,.24);border-radius:16px;padding:12px 16px;color:#eef6ff;backdrop-filter:blur(14px);font-family:Inter,system-ui,sans-serif}#researchTimeline input{width:100%}#groundTrack{width:100%;height:148px;border-radius:10px;background:rgba(0,0,0,.22);border:1px solid rgba(255,255,255,.08)}.research-slider{width:100%}.research-brief{width:100%;border:0;border-radius:10px;padding:8px;background:#57a5ff;color:#07101f;font-weight:800;cursor:pointer}.research-feature-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}.research-feature{font-size:11px;padding:6px;border-radius:9px;background:rgba(87,165,255,.10);border:1px solid rgba(87,165,255,.16)}
      @media(max-width:1300px){#researchDock{width:310px;right:12px;top:72px}#researchTimeline{left:590px;right:335px}}
      @media(max-width:1050px){#researchDock{display:none}#researchTimeline{left:24px;right:24px}}`;
    document.head.appendChild(style);
  }

  function ensureResearchUi() {
    if (ui.ready) return;
    injectResearchCss();
    const dock = document.createElement("div");
    dock.id = "researchDock";
    dock.innerHTML = `
      <div class="card"><h3>Research Features Active</h3><div class="research-feature-grid"><span class="research-feature">Uncertainty volumes</span><span class="research-feature">TCA volume</span><span class="research-feature">Heat gradient trail</span><span class="research-feature">Ground track</span><span class="research-feature">Triage queue</span><span class="research-feature">Threshold sandbox</span></div></div>
      <div class="card"><h3>Research Triage Queue</h3><div id="researchEventList"></div></div>
      <div class="card"><h3>Model-Grounded Triage</h3><div id="triageSummary"></div><p class="research-muted">Research-only classification for explainable conjunction-risk triage. Not an operational maneuver recommendation.</p></div>
      <div class="card"><h3>What Changed?</h3><div id="changePanel"></div></div>
      <div class="card"><h3>Threshold Sensitivity</h3><label class="research-small">Risk log10 cutoff <span id="riskCutLabel"></span></label><input id="riskCut" class="research-slider" type="range" min="-8" max="-3" step="0.1" value="-5.5"><label class="research-small">Uncertainty cutoff <span id="uncCutLabel"></span></label><input id="uncCut" class="research-slider" type="range" min="0" max="0.3" step="0.01" value="0.10"><label class="research-small">Confidence cutoff <span id="confCutLabel"></span></label><input id="confCut" class="research-slider" type="range" min="0" max="1" step="0.05" value="0.50"><div id="sensitivityOut"></div></div>
      <div class="card"><h3>Ground-Track Mini Map</h3><canvas id="groundTrack" width="316" height="148"></canvas></div>
      <div class="card"><h3>Exportable Research Brief</h3><button id="briefButton" class="research-brief">Export Research Brief</button></div>`;
    document.body.appendChild(dock);
    const timeline = document.createElement("div");
    timeline.id = "researchTimeline";
    timeline.innerHTML = `<div class="research-row"><span class="research-value">Research Timeline Scrubber</span><span id="timelineLabel" class="research-small"></span></div><input id="researchScrubber" type="range" min="0" max="3" step="0.001" value="0"><div id="timelineTicks" class="research-small"></div>`;
    document.body.appendChild(timeline);
    const scrub = document.getElementById("researchScrubber");
    scrub.addEventListener("input", handleScrub);
    scrub.addEventListener("pointerdown", () => { ui.scrubActive = true; });
    scrub.addEventListener("pointerup", () => { ui.scrubActive = false; ui.scrubValue = Number(scrub.value); });
    scrub.addEventListener("change", () => { ui.scrubValue = Number(scrub.value); });
    document.getElementById("briefButton").addEventListener("click", exportBrief);
    for (const id of ["riskCut", "uncCut", "confCut"]) document.getElementById(id).addEventListener("input", updateResearchUi);
    ui.ready = true;
  }

  function interpAt(value) {
    const event = currentEvent();
    const snaps = event.snapshots;
    if (!snaps.length) return null;
    const low = Math.floor(clamp(value, 0, snaps.length - 1));
    const high = Math.min(snaps.length - 1, low + 1);
    const t = value - low;
    if (low === high || t <= 0) return snaps[low];
    return interpolatedSnapshot(snaps[low], snaps[high], easeInOut(t));
  }

  function handleScrub(e) {
    ui.scrubActive = true;
    ui.scrubValue = Number(e.target.value);
    const snapshot = interpAt(ui.scrubValue);
    if (snapshot) renderSnapshot(snapshot, false);
  }

  function riskLabel(snapshot) {
    const risk = Number(snapshot?.current_risk_log10);
    return Number.isFinite(risk) ? Math.abs(risk).toFixed(2) : "—";
  }

  function classify(snapshot) {
    const risk = Number(snapshot?.current_risk_log10);
    const unc = Number(snapshot?.predictive_std) || 0;
    const conf = Number(snapshot?.model_probability) || 0;
    const riskCut = Number(document.getElementById("riskCut")?.value ?? -5.5);
    const uncCut = Number(document.getElementById("uncCut")?.value ?? 0.10);
    const confCut = Number(document.getElementById("confCut")?.value ?? 0.50);
    const elevatedRisk = Number.isFinite(risk) && risk >= riskCut;
    const highUnc = unc >= uncCut;
    const highConf = conf >= confCut;
    if (elevatedRisk && highUnc) return "High-Risk / High-Uncertainty Case";
    if (elevatedRisk && highConf) return "Model-Consistent Elevated-Risk Case";
    if (highUnc) return "Uncertainty-Dominated Case";
    if (elevatedRisk) return "Elevated-Risk Case";
    return "Nominal Research Case";
  }

  function updateEventList() {
    const el = document.getElementById("researchEventList");
    if (!el || !state.data?.events) return;
    el.innerHTML = "";
    state.data.events.map((event, index) => ({ event, index, score: Math.max(...event.snapshots.map(s => Number(s.current_risk_log10) || -99)) })).sort((a, b) => b.score - a.score).slice(0, 8).forEach(({ event, index, score }) => {
      const button = document.createElement("button");
      button.className = "research-event";
      button.innerHTML = `<b>${event.display_name || event.event_id}</b><br><span class="research-small">max log10 risk ${Number.isFinite(score) ? score.toFixed(2) : "—"}</span>`;
      button.addEventListener("click", () => { ui.scrubValue = null; setEvent(index); });
      el.appendChild(button);
    });
  }

  function updateChangePanel(snapshot) {
    const el = document.getElementById("changePanel");
    if (!el) return;
    const event = currentEvent();
    const idx = Math.max(0, Math.round(ui.scrubValue ?? state.horizonIndex ?? 0));
    const prev = event.snapshots[Math.max(0, idx - 1)] || snapshot;
    const dr = (Number(snapshot.current_risk_log10) || 0) - (Number(prev.current_risk_log10) || 0);
    const du = (Number(snapshot.predictive_std) || 0) - (Number(prev.predictive_std) || 0);
    const dd = (Number(snapshot.geometry?.relative_distance_km) || 0) - (Number(prev.geometry?.relative_distance_km) || 0);
    el.innerHTML = `<div class="research-row"><span>Risk log10 shift</span><span class="research-value">${dr >= 0 ? "+" : ""}${dr.toFixed(2)}</span></div><div class="research-row"><span>Uncertainty shift</span><span class="research-value">${du >= 0 ? "+" : ""}${(du * 100).toFixed(1)}%</span></div><div class="research-row"><span>Distance shift</span><span class="research-value">${dd >= 0 ? "+" : ""}${dd.toFixed(2)} km</span></div>`;
  }

  function updateTriage(snapshot) {
    const out = document.getElementById("triageSummary");
    const sensitivity = document.getElementById("sensitivityOut");
    if (!out || !sensitivity) return;
    const stateName = classify(snapshot);
    const heat = heatForSnapshot(snapshot);
    out.innerHTML = `<div class="research-row"><span>Research classification</span><span class="research-value">${stateName}</span></div><div class="research-row"><span>Risk magnitude</span><span class="research-value">${riskLabel(snapshot)}</span></div><div class="research-row"><span>Visual heat index</span><span class="research-value">${(heat * 100).toFixed(0)}%</span></div><ul><li>Classification is threshold-driven and explainable.</li><li>Uncertainty volumes encode predictive spread.</li><li>Color heat shows model-evidence concentration near the live conjunction geometry.</li></ul>`;
    document.getElementById("riskCutLabel").textContent = document.getElementById("riskCut").value;
    document.getElementById("uncCutLabel").textContent = document.getElementById("uncCut").value;
    document.getElementById("confCutLabel").textContent = document.getElementById("confCut").value;
    sensitivity.innerHTML = `<p class="research-small">Current threshold result: <b>${stateName}</b></p>`;
  }

  function drawEarthMap(ctx, w, h) {
    const ocean = ctx.createLinearGradient(0, 0, 0, h);
    ocean.addColorStop(0, "#102a52");
    ocean.addColorStop(0.55, "#0b3f7b");
    ocean.addColorStop(1, "#071b35");
    ctx.fillStyle = ocean;
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(190,220,255,.16)";
    ctx.lineWidth = 1;
    for (let i = 1; i < 6; i += 1) { ctx.beginPath(); ctx.moveTo((w / 6) * i, 0); ctx.lineTo((w / 6) * i, h); ctx.stroke(); }
    for (let i = 1; i < 4; i += 1) { ctx.beginPath(); ctx.moveTo(0, (h / 4) * i); ctx.lineTo(w, (h / 4) * i); ctx.stroke(); }
    const land = "rgba(93,150,112,.80)";
    const edge = "rgba(200,235,210,.35)";
    function poly(points) { ctx.beginPath(); points.forEach(([x, y], i) => { const px = x * w, py = y * h; if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py); }); ctx.closePath(); ctx.fillStyle = land; ctx.fill(); ctx.strokeStyle = edge; ctx.stroke(); }
    poly([[.12,.32],[.20,.22],[.30,.28],[.28,.43],[.20,.52],[.13,.45]]);
    poly([[.25,.55],[.33,.57],[.36,.73],[.30,.88],[.24,.75]]);
    poly([[.45,.31],[.55,.24],[.64,.29],[.62,.40],[.51,.41],[.44,.36]]);
    poly([[.52,.43],[.62,.45],[.66,.60],[.60,.80],[.51,.66]]);
    poly([[.62,.30],[.78,.24],[.90,.33],[.86,.48],[.73,.50],[.63,.42]]);
    poly([[.77,.62],[.88,.65],[.90,.76],[.80,.79]]);
    ctx.fillStyle = "rgba(255,255,255,.18)";
    ctx.beginPath(); ctx.ellipse(w * .53, h * .18, w * .08, h * .025, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(w * .15, h * .83, w * .16, h * .025, 0, 0, Math.PI * 2); ctx.fill();
  }

  function drawGroundTrack(snapshot) {
    const canvas = document.getElementById("groundTrack");
    if (!canvas || !snapshot?.geometry) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    drawEarthMap(ctx, w, h);
    function project(p) { const r = Math.sqrt(p[0] ** 2 + p[1] ** 2 + p[2] ** 2) || 1; const lon = Math.atan2(p[1], p[0]); const lat = Math.asin(clamp(p[2] / r, -1, 1)); return [w * (lon + Math.PI) / (2 * Math.PI), h * (0.5 - lat / Math.PI)]; }
    function path(points, color) { ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath(); points.forEach((p, i) => { const q = project(p); if (i === 0) ctx.moveTo(q[0], q[1]); else ctx.lineTo(q[0], q[1]); }); ctx.stroke(); }
    path(snapshot.geometry.target_orbit_km || [], "rgba(87,165,255,.88)");
    path(snapshot.geometry.secondary_orbit_km || [], "rgba(255,184,77,.88)");
    for (const [p, color] of [[snapshot.geometry.target_position_km, "#57a5ff"], [snapshot.geometry.secondary_position_km, "#ffb84d"]]) { const q = project(p); ctx.fillStyle = color; ctx.beginPath(); ctx.arc(q[0], q[1], 4.5, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = "white"; ctx.lineWidth = 1.3; ctx.stroke(); }
  }

  function updateTimeline(snapshot) {
    const slider = document.getElementById("researchScrubber");
    const label = document.getElementById("timelineLabel");
    const ticks = document.getElementById("timelineTicks");
    if (!slider || !state.data) return;
    if (ui.lastEventIndex !== state.eventIndex) { ui.scrubValue = null; ui.lastEventIndex = state.eventIndex; }
    const snaps = currentEvent().snapshots;
    slider.max = String(Math.max(0, snaps.length - 1));
    const value = ui.scrubValue !== null ? ui.scrubValue : (state.horizonIndex || 0);
    slider.value = String(clamp(value, 0, Math.max(0, snaps.length - 1)));
    if (label) label.textContent = ui.scrubValue !== null ? "interpolated" : (snapshot?.horizon || "interpolated");
    if (ticks) ticks.textContent = snaps.map((s, i) => `${i}: ${s.horizon}`).join("   ");
  }

  function updateResearchUi() {
    if (!state.data || !state.displaySnapshot) return;
    ensureResearchUi();
    updateEventList();
    updateTimeline(state.displaySnapshot);
    updateTriage(state.displaySnapshot);
    updateChangePanel(state.displaySnapshot);
    drawGroundTrack(state.displaySnapshot);
  }

  function exportBrief() {
    const s = state.displaySnapshot || currentSnapshot();
    const e = currentEvent();
    const html = `<!doctype html><title>BEACON Research Brief</title><h1>BEACON Research Brief</h1><p><b>Event:</b> ${e.display_name || e.event_id}</p><p><b>Horizon:</b> ${s.horizon}</p><p><b>Research classification:</b> ${classify(s)}</p><p><b>Risk magnitude:</b> ${riskLabel(s)}</p><p><b>Model probability:</b> ${formatPercent(s.model_probability)}</p><p><b>Predictive uncertainty:</b> ${formatPercent(s.predictive_std)}</p><p><b>Relative distance:</b> ${formatNumber(s.geometry.relative_distance_km, 3)} km</p><p>This brief is generated for explainable AI research and visualization review only. It is not an operational maneuver recommendation.</p>`;
    const blob = new Blob([html], { type: "text/html" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `beacon-research-brief-${e.event_id || "event"}.html`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

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

  function paintLabel(entity, alpha, bgScale) {
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
    updateResearchUi();
    applyLabelFade();
  };

  function frame() {
    if (state.displaySnapshot) {
      syncAll(state.displaySnapshot);
      labelState.target = labelAlphaForCamera();
      labelState.current += (labelState.target - labelState.current) * LABEL_EASE;
      paintLabel(state.refs.targetObject, labelState.current, 0.45);
      paintLabel(state.refs.secondaryObject, labelState.current, 0.45);
      paintLabel(state.refs.closestApproach, state.hovered === "center" ? labelState.current : 0, 0.55);
      updateResearchUi();
      viewer.scene.requestRender();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  window.__BEACON_LIVE_TRAILS_PATCHED__ = true;
  window.__BEACON_RESEARCH_FEATURES__ = true;
})();
