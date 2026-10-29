// PulseNet operations dashboard. Plain JavaScript, no build step: it polls the PulseNet API (api.py) and
// draws four pages (operations, topology, traffic, controller) plus the agent panel.

const POLL_MS = 3000;
const DISTRICTS = ["KHALIDIYAH", "UYUN", "SULTANAH", "AZIZIYAH", "QUBA"];
const RING = ["FIBER-KHALIDIYAH-UYUN", "FIBER-UYUN-SULTANAH", "FIBER-SULTANAH-AZIZIYAH", "FIBER-AZIZIYAH-QUBA",
  "FIBER-QUBA-KHALIDIYAH"];
const INTENT_LIMIT = 70; // INT-2: no backbone link above 70 % at the evening peak

const S = {
  key: load("pulsenet.key") || "dev-key-1",
  assets: [], byId: {}, alarms: [], intents: [], logs: [], tickets: [], audit: [], jobs: [], meta: null,
  online: false, firstLoad: true, seenAlarms: new Set(), seenLogs: 0,
  route: "operations", focus: [], selected: null, segment: "FIBER-KHALIDIYAH-UYUN",
  replay: null, chat: { job: null, busy: false },
};

// ---------------------------------------------------------------- helpers
function load(k) { try { return localStorage.getItem(k); } catch { return null; } }
function save(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } }
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hhmm = (ts) => (ts || "").slice(11, 16);
const pct = (v) => (v == null ? "–" : `${Math.round(v)} %`);
const districtName = (d) => (S.meta?.districts?.[d]) || d;

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts, headers: { "X-API-Key": S.key, "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not json */ }
    const err = new Error(detail); err.status = res.status; throw err;
  }
  return res.json();
}

function profileAt(hour) {
  const p = S.meta?.traffic_profile || {};
  const hours = Object.keys(p).map(Number).sort((a, b) => a - b);
  const below = hours.filter((h) => h <= hour).pop() ?? hours[0];
  return p[String(below).padStart(2, "0")] ?? 1;
}
const peakFactor = () => profileAt(21) / profileAt(9.5);
const utilColor = (u, down) => (down ? "var(--bad)" : u > INTENT_LIMIT ? "var(--bad)" : u > 50 ? "var(--warn)" : "var(--ok)");

function alarmsFor(id) { return visibleAlarms().filter((a) => a.asset_id === id); }

// ---------------------------------------------------------------- replay of this morning
// Plays the morning's log from 06:00 to 09:30 in 45 seconds, raising each alarm when its first warning appears.
const REPLAY_FROM = 6 * 60, REPLAY_TO = 9 * 60 + 30, REPLAY_S = 45;
function replayMinute() {
  if (!S.replay) return null;
  const done = (Date.now() - S.replay.start) / 1000 / REPLAY_S;
  if (done >= 1) { S.replay = null; toast("good", "Replay finished", "Back to live telemetry."); return null; }
  return REPLAY_FROM + done * (REPLAY_TO - REPLAY_FROM);
}
const minuteOf = (ts) => Number(ts.slice(11, 13)) * 60 + Number(ts.slice(14, 16));
function firstSeen(id) {
  const rows = S.logs.filter((l) => l.asset_id === id);
  const bad = rows.find((l) => l.level !== "INFO") || rows.find((l) => minuteOf(l.ts) > REPLAY_FROM + 60);
  return bad ? minuteOf(bad.ts) : REPLAY_TO;
}
function visibleAlarms() {
  const m = replayMinute();
  return m == null ? S.alarms : S.alarms.filter((a) => firstSeen(a.asset_id) <= m);
}
function visibleLogs() {
  const m = replayMinute();
  return m == null ? S.logs : S.logs.filter((l) => minuteOf(l.ts) <= m);
}

// ---------------------------------------------------------------- polling
async function poll() {
  try {
    const [assets, overview, intents, logs, tickets, audit, jobs] = await Promise.all([
      api("/v1/assets"), api("/v1/alarms"), api("/v1/intents"), api("/v1/logs"), api("/v1/tickets"),
      api("/v1/audit"), api("/v1/jobs"),
    ]);
    if (!S.meta) {
      S.meta = await api("/v1/meta");
      $("#agentModel").textContent = `model: ${S.meta.model} · tools over MCP`;
    }
    Object.assign(S, { assets, alarms: overview.alarms, intents, logs, tickets, audit, jobs, online: true });
    S.byId = Object.fromEntries(assets.map((a) => [a.asset_id, a]));
    if (!S.replay) notifyAlarmChanges();
  } catch (e) {
    S.online = false;
    if (e.status === 401) askKey("The API key was refused. Enter a key from PULSENET_API_KEYS.");
  }
  render();
}

function alarmKey(a) { return `${a.asset_id}|${a.alarm.replace(/[\d.]+/g, "#")}`; }
function notifyAlarmChanges() {
  const now = new Set(S.alarms.map(alarmKey));
  if (!S.firstLoad) {
    for (const a of S.alarms) {
      if (!S.seenAlarms.has(alarmKey(a))) {
        toast(a.severity, `New ${a.severity} alarm · ${a.asset_id}`, a.alarm, alarmActions(a));
      }
    }
    for (const k of S.seenAlarms) {
      if (!now.has(k)) toast("good", `Cleared · ${k.split("|")[0]}`, "The alarm is no longer active.");
    }
  }
  S.seenAlarms = now; S.firstLoad = false;
}

function alarmActions(a) {
  return [
    { label: "Locate", go: `#/topology?focus=${a.asset_id}` },
    { label: "Ask PulseNet", ask: `Explain the ${a.severity} alarm on ${a.asset_id} ("${a.alarm}"). What is the root cause and what should I do?` },
  ];
}

// ---------------------------------------------------------------- routing
function parseRoute() {
  const [path, query] = (location.hash.replace(/^#\/?/, "") || "operations").split("?");
  S.route = ["operations", "topology", "traffic", "controller"].includes(path) ? path : "operations";
  const params = new URLSearchParams(query || "");
  S.focus = (params.get("focus") || "").split(",").filter(Boolean);
  if (S.focus.length) {
    S.selected = S.focus[0];
    if (S.route === "traffic" && RING.concat("BACKUP-WAVE-1").includes(S.focus[0])) S.segment = S.focus[0];
  }
  document.querySelectorAll("#tabs a").forEach((a) => a.classList.toggle("active", a.dataset.page === S.route));
  render(true);
}

function go(hash) { if (location.hash === hash) parseRoute(); else location.hash = hash; }

// ---------------------------------------------------------------- render
function render(scrollToFocus = false) {
  renderStrip();
  const page = $("#page");
  if (!S.assets.length) {
    page.innerHTML = `<div class="banner bad">${S.online ? "Loading…" : "Cannot reach the PulseNet API. Start it with <code>uv run pulsenet/api.py</code>."}</div>`;
    return;
  }
  const html = { operations: pageOperations, topology: pageTopology, traffic: pageTraffic, controller: pageController }[S.route]();
  page.innerHTML = (S.online ? "" : `<div class="banner bad">Connection to the API lost, showing the last known state.</div>`) + html;
  if (scrollToFocus) {
    const row = page.querySelector("tr.focus");
    if (row) row.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

function renderStrip() {
  const al = visibleAlarms();
  const crit = al.filter((a) => a.severity === "critical").length;
  const met = S.intents.filter((i) => i.met).length;
  const pending = S.jobs.find((j) => j.pending_approval);
  const working = S.jobs.find((j) => !j.done);
  const agentState = pending ? `<span class="pill warn">change awaiting approval</span>`
    : working ? `<span class="pill info">agent working</span>` : `<span class="pill ok">agent idle</span>`;
  $("#statusStrip").innerHTML = `<span class="pill ${crit ? "critical" : "ok"}">${al.length} alarms · ${crit} critical</span>
    <span class="pill ${met === S.intents.length ? "met" : "major"}">${met}/${S.intents.length || 5} intents met</span>${agentState}`;
  $(".live-dot").classList.toggle("off", !S.online);
  $("#liveLabel").textContent = S.replay ? "REPLAY" : S.online ? "LIVE" : "OFFLINE";
}

function idLink(id) { return `<a class="id" data-select="${esc(id)}">${esc(id)}</a>`; }
function statusPill(s) { return `<span class="pill ${esc(s)}">${esc(s)}</span>`; }

// ---------------------------------------------------------------- page: operations
function pageOperations() {
  const al = visibleAlarms();
  const sites = S.assets.filter((a) => a.kind === "cell_site");
  const down = sites.filter((a) => a.status === "down").length;
  const avail = sites.reduce((s, a) => s + (a.metrics.availability_pct ?? 100), 0) / (sites.length || 1);
  const met = S.intents.filter((i) => i.met).length;
  const ringPeak = Math.max(...RING.map((id) => (S.byId[id]?.metrics.utilisation_pct || 0) * peakFactor()));
  const open = S.tickets.filter((t) => t.status === "open").length;
  const crit = al.filter((a) => a.severity === "critical").length;

  const kpis = [
    ["Active alarms", al.length, `${crit} critical · ${al.filter((a) => a.severity === "major").length} major`, crit ? "bad" : al.length ? "warn" : "ok"],
    ["Intents met", `${met}/${S.intents.length}`, "operator goals INT-1 … INT-5", met === S.intents.length ? "ok" : "bad"],
    ["5G availability", `${avail.toFixed(1)} %`, "target ≥ 99.5 % per district", avail >= 99.5 ? "ok" : "warn"],
    ["Cell sites down", `${down}/${sites.length}`, "out of service now", down ? "bad" : "ok"],
    ["Ring at 21:00 peak", pct(ringPeak), `forecast · limit ${INTENT_LIMIT} %`, ringPeak > INTENT_LIMIT ? "bad" : "ok"],
    ["Open tickets", open, "field teams dispatched", open ? "warn" : ""],
  ].map(([l, v, h, c]) => `<div class="card kpi ${c}"><div class="label">${l}</div><div class="value">${v}</div><div class="hint">${h}</div></div>`).join("");

  const alarmRows = al.length ? al.map((a) => `<tr class="${S.focus.includes(a.asset_id) ? "focus" : ""}">
      <td>${statusPill(a.severity)}</td><td>${idLink(a.asset_id)}</td><td class="muted">${esc(districtName(a.district))}</td>
      <td>${esc(a.alarm)}</td>
      <td><div class="row-actions">
        <button class="btn small" data-go="#/topology?focus=${esc(a.asset_id)}">Locate</button>
        <button class="btn small primary" data-ask="${esc(alarmActions(a)[1].ask)}">Ask agent</button></div></td></tr>`).join("")
    : `<tr><td colspan="5" class="empty">No active alarms.</td></tr>`;

  const intents = S.intents.map((i) => `<div class="intent"><div class="iid">${i.id}</div>
      <div class="itext">${esc(i.text)}${i.violated_by.length ? `<div class="by">${i.violated_by.map(idLink).join("")}</div>` : ""}</div>
      <div>${i.met ? `<span class="pill met">met</span>` : `<span class="pill critical">violated</span>`}</div></div>`).join("");

  const districts = DISTRICTS.map((d) => {
    const list = S.assets.filter((a) => a.district === d && !["ring_fiber", "backup_link"].includes(a.kind));
    const bad = list.filter((a) => a.status !== "ok").length;
    const dal = al.filter((a) => a.district === d).length;
    return `<div class="card district" data-go="#/topology?focus=AGG-${d}" style="cursor:pointer">
      <div class="name">${esc(districtName(d))} ${dal ? `<span class="pill ${al.some((a) => a.district === d && a.severity === "critical") ? "critical" : "major"}">${dal} alarms</span>` : `<span class="pill ok">normal</span>`}</div>
      <div class="bars">${list.map((a) => `<span class="${a.status}" title="${esc(a.asset_id)} · ${a.status}"></span>`).join("")}</div>
      <div class="small muted">${list.length} assets · ${bad} not OK</div></div>`;
  }).join("");

  const logs = visibleLogs().slice().reverse();
  const fresh = S.seenLogs ? logs.length - S.seenLogs : 0;
  const events = logs.map((l, i) => `<div class="event ${l.level} ${i < fresh ? "new" : ""}">
      <span class="t">${hhmm(l.ts)}</span><span>${S.byId[l.asset_id] ? idLink(l.asset_id) : `<span class="mono small muted">${esc(l.asset_id)}</span>`}</span>
      <span>${esc(l.message.length > 150 ? l.message.slice(0, 150) + "…" : l.message)}</span></div>`).join("");
  S.seenLogs = logs.length;

  return `<h1 class="page-title">Operations overview</h1>
    <p class="page-sub">Monday 2 November 2026 · Madinah metropolitan network · 40 assets in 5 districts on a 100G fiber ring</p>
    <div class="grid g-kpi">${kpis}</div>
    <div class="grid g-2" style="margin-top:14px">
      <div class="card"><div class="card-h"><h2>Active alarms</h2><span class="small muted">sorted by severity · symptoms, not causes</span></div>
        <div class="card-b flush"><table><thead><tr><th>Severity</th><th>Asset</th><th>District</th><th>Alarm</th><th></th></tr></thead>
        <tbody>${alarmRows}</tbody></table></div></div>
      <div class="card"><div class="card-h"><h2>Operator intents</h2><span class="small muted">closed-loop goals</span></div>
        <div class="card-b flush">${intents}</div></div>
    </div>
    <div class="grid g-5" style="margin-top:14px">${districts}</div>
    <div class="card" style="margin-top:14px"><div class="card-h"><h2>Event stream</h2>
        <button class="btn small" data-replay>${S.replay ? "Stop replay" : "▶ Replay this morning"}</button></div>
      <div class="card-b flush events">${events || `<div class="empty">No events yet.</div>`}</div></div>`;
}

// ---------------------------------------------------------------- page: topology
const W = 980, H = 800, CX = 490, CY = 395, R = 215;
const ANGLE = { KHALIDIYAH: -126, UYUN: -54, SULTANAH: 18, AZIZIYAH: 90, QUBA: 162 };
const rad = (d) => (d * Math.PI) / 180;

function layout() {
  const pos = {};
  for (const d of DISTRICTS) {
    const a = rad(ANGLE[d]);
    pos[`AGG-${d}`] = [CX + R * Math.cos(a), CY + R * Math.sin(a)];
    const kids = S.assets.filter((x) => x.district === d && !["aggregation_router", "ring_fiber", "backup_link",
      "spur_fiber", "core_router", "internet_gateway"].includes(x.kind));
    kids.forEach((k, i) => {
      const spread = kids.length > 1 ? -66 + (132 * i) / (kids.length - 1) : 0;
      const b = rad(ANGLE[d] + spread);
      const dist = 118 + (i % 2) * 26;
      pos[k.asset_id] = [pos[`AGG-${d}`][0] + dist * Math.cos(b), pos[`AGG-${d}`][1] + dist * Math.sin(b)];
    });
  }
  const at = (d, f) => [CX + R * f * Math.cos(rad(ANGLE[d])), CY + R * f * Math.sin(rad(ANGLE[d]))];
  pos["CORE-R1"] = at("KHALIDIYAH", 0.5);
  pos["CORE-R2"] = at("QUBA", 0.5);
  pos["IGW-1"] = [CX, CY - 20];
  return pos;
}

const GLYPH = { cell_site: "5G", iot_gateway: "IoT", edge_dc: "DC", critical_service: "★", aggregation_router: "AGG",
  core_router: "CR", internet_gateway: "GW" };
const SIZE = { cell_site: 11, iot_gateway: 10, edge_dc: 13, critical_service: 12, aggregation_router: 17, core_router: 15, internet_gateway: 17 };
// re-rendering restarts CSS animations; a negative delay keeps each pulse in phase
const phase = (ms) => `style="animation-delay:-${(Date.now() % ms) / 1000}s"`;
const STROKE = { ok: "var(--ok)", degraded: "var(--warn)", down: "var(--bad)", quarantined: "var(--quar)" };
const FILL = { ok: "#eef4ec", degraded: "#f8edd6", down: "#f6e0db", quarantined: "#ece7f2" };

function edgeSvg(id, d, color, width, dash, label, labelAt) {
  const focus = S.focus.includes(id) || S.selected === id;
  return `<g data-select="${id}">
    ${focus ? `<path d="${d}" class="halo" style="stroke-width:${width + 8};animation-delay:-${(Date.now() % 1600) / 1000}s"/>` : ""}
    <path d="${d}" class="edge" stroke="${color}" stroke-width="${width}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>
    <path d="${d}" class="edge-hit"/>
    ${label ? `<text class="edge-label" x="${labelAt[0]}" y="${labelAt[1]}" text-anchor="middle">${esc(label)}</text>` : ""}</g>`;
}

function pageTopology() {
  const pos = layout();
  const al = visibleAlarms();
  const alarmed = new Set(al.filter((a) => a.severity !== "minor").map((a) => a.asset_id));
  let svg = "";

  // district zones and labels
  for (const d of DISTRICTS) {
    const [x, y] = pos[`AGG-${d}`];
    const a = rad(ANGLE[d]);
    svg += `<circle class="district-zone" cx="${x + 62 * Math.cos(a)}" cy="${y + 62 * Math.sin(a)}" r="128"/>`;
  }

  // core links
  for (const [a, b] of [["IGW-1", "CORE-R1"], ["IGW-1", "CORE-R2"], ["CORE-R1", "AGG-KHALIDIYAH"], ["CORE-R2", "AGG-QUBA"]]) {
    svg += `<line x1="${pos[a][0]}" y1="${pos[a][1]}" x2="${pos[b][0]}" y2="${pos[b][1]}" stroke="#9c968a" stroke-width="3"/>`;
  }

  // ring segments as arcs
  RING.forEach((id, i) => {
    const f = S.byId[id];
    if (!f) return;
    const from = DISTRICTS[i], to = DISTRICTS[(i + 1) % 5];
    const [x1, y1] = pos[`AGG-${from}`], [x2, y2] = pos[`AGG-${to}`];
    const mid = rad((ANGLE[from] + (ANGLE[to] < ANGLE[from] ? ANGLE[to] + 360 : ANGLE[to])) / 2);
    const down = f.status === "down", u = f.metrics.utilisation_pct;
    const lr = down ? R - 26 : R + 20;  // a cut label goes inside the ring, away from the district's nodes
    const lab = [CX + lr * Math.cos(mid), CY + lr * Math.sin(mid) + 4];
    const label = down ? `✕ CUT · duct ${f.metrics.duct}` : `${Math.round(u)} %`;
    svg += edgeSvg(id, `M${x1},${y1} A${R},${R} 0 0 1 ${x2},${y2}`, utilColor(u, down), 6, down ? "9 7" : "", label, lab);
  });

  // backup wavelength (chord through the city)
  const wave = S.byId["BACKUP-WAVE-1"];
  if (wave) {
    const [x1, y1] = pos["AGG-AZIZIYAH"], [x2, y2] = pos["AGG-KHALIDIYAH"];
    const on = wave.config.state === "enabled";
    const cx = CX + 175, cy = CY + 30;
    svg += edgeSvg("BACKUP-WAVE-1", `M${x1},${y1} Q${cx},${cy} ${x2},${y2}`, on ? "var(--accent)" : "#b9b3a6", on ? 5 : 3,
      on ? "" : "4 6", on ? `BACKUP-WAVE-1 · ${Math.round(wave.metrics.utilisation_pct)} %` : "BACKUP-WAVE-1 · disabled",
      [(x1 + x2) / 4 + cx / 2, (y1 + y2) / 4 + cy / 2 + 16]);
  }

  // access links (district router to its sites, gateways, data centers, services)
  for (const a of S.assets) {
    if (!pos[a.asset_id] || !a.uplink || a.kind === "aggregation_router" || a.kind.endsWith("router") || a.kind === "internet_gateway") continue;
    const up = a.uplink.startsWith("SPUR-") ? `AGG-${a.district}` : a.uplink;
    if (!pos[up]) continue;
    const spur = a.uplink.startsWith("SPUR-") ? S.byId[a.uplink] : null;
    const [x1, y1] = pos[up], [x2, y2] = pos[a.asset_id];
    if (spur) {
      svg += edgeSvg(spur.asset_id, `M${x1},${y1} L${x2},${y2}`, spur.status === "down" ? "var(--bad)" : "#a9a395", 3,
        spur.status === "down" ? "6 5" : "", spur.status === "down" ? "✕ spur" : "", [(x1 + x2) / 2 + 14, (y1 + y2) / 2]);
    } else {
      const c = a.status === "quarantined" ? "var(--quar)" : a.status === "down" ? "var(--bad)" : "#b3ad9f";
      svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${c}" stroke-width="1.6" ${a.status === "quarantined" ? 'stroke-dasharray="3 4"' : ""}/>`;
    }
  }

  // nodes
  for (const a of S.assets) {
    const p = pos[a.asset_id];
    if (!p) continue;
    const r = SIZE[a.kind] || 10;
    const focus = S.focus.includes(a.asset_id) || S.selected === a.asset_id;
    const shape = a.kind === "edge_dc" || a.kind === "critical_service"
      ? `<rect class="body" x="${p[0] - r}" y="${p[1] - r}" width="${2 * r}" height="${2 * r}" rx="4" fill="${FILL[a.status]}" stroke="${STROKE[a.status]}"/>`
      : `<circle class="body" cx="${p[0]}" cy="${p[1]}" r="${r}" fill="${FILL[a.status]}" stroke="${STROKE[a.status]}"/>`;
    const label = a.kind === "aggregation_router" ? "" : a.asset_id.replace(`-${a.district}`, "");
    svg += `<g class="node" data-select="${a.asset_id}">
      ${alarmed.has(a.asset_id) ? `<circle class="alarm-ring" cx="${p[0]}" cy="${p[1]}" r="${r + 3}" ${phase(1800)}/>` : ""}
      ${focus ? `<circle class="halo" cx="${p[0]}" cy="${p[1]}" r="${r + 7}" ${phase(1600)}/>` : ""}
      ${shape}
      <text class="glyph" x="${p[0]}" y="${p[1] + 3.5}" text-anchor="middle">${GLYPH[a.kind] || ""}</text>
      <text x="${p[0]}" y="${p[1] + r + 13}" text-anchor="middle">${esc(label)}</text></g>`;
  }

  for (const d of DISTRICTS) {
    const [x, y] = pos[`AGG-${d}`];
    svg += `<text class="zone-label" x="${x}" y="${y + 33}" text-anchor="middle">${esc(districtName(d))}</text>`;
  }

  const legend = `<div class="legend">
    <span><i style="border-color:var(--ok)"></i>ring &lt; 50 %</span><span><i style="border-color:var(--warn)"></i>50–70 %</span>
    <span><i style="border-color:var(--bad)"></i>&gt; 70 % or cut</span><span><i style="border-color:var(--accent)"></i>backup active</span>
    <span><b style="border-color:var(--ok)"></b>ok</span><span><b style="border-color:var(--warn)"></b>degraded</span>
    <span><b style="border-color:var(--bad)"></b>down</span><span><b style="border-color:var(--quar)"></b>quarantined</span>
    <span>5G cell site · IoT gateway · DC edge data center · ★ critical service · CR core router</span></div>`;

  return `<h1 class="page-title">Network topology</h1>
    <p class="page-sub">Backbone ring, district routers and everything behind them. Click any node or link for its live readings.</p>
    <div class="topo-wrap">
      <div class="card"><div class="card-h"><h2>Madinah metro ring · live</h2>
        <span class="small muted">${S.focus.length ? `highlighted: ${S.focus.map(esc).join(", ")} · <a href="#/topology">clear</a>` : "pulsing red = active alarm"}</span></div>
        <svg class="topo" viewBox="0 0 ${W} ${H}">${svg}</svg>${legend}</div>
      <div class="card"><div class="card-h"><h2>Asset details</h2></div><div class="card-b detail">${detailPanel(S.selected)}</div></div>
    </div>`;
}

function flatten(obj, prefix = "") {
  return Object.entries(obj || {}).flatMap(([k, v]) =>
    v && typeof v === "object" && !Array.isArray(v) ? flatten(v, `${prefix}${k}.`) : [[`${prefix}${k}`, Array.isArray(v) ? v.join(", ") || "none" : v]]);
}

function pathOf(id) {
  const hops = [];
  let a = S.byId[id];
  while (a && hops.length < 8) { hops.push(a); a = S.byId[a.uplink]; }
  return hops;
}

function detailPanel(id) {
  const a = S.byId[id];
  if (!a) return `<div class="empty">Select a node or a link on the map.</div>`;
  const kv = flatten(a.metrics).map(([k, v]) => `<div>${esc(k.replace(/_/g, " "))}</div><div>${esc(v)}</div>`).join("");
  const cfg = flatten(a.config).map(([k, v]) => `<div>${esc(k.replace(/_/g, " "))}</div><div>${esc(v)}</div>`).join("");
  const al = alarmsFor(a.asset_id).map((x) => `<div style="margin-top:4px">${statusPill(x.severity)} ${esc(x.alarm)}</div>`).join("");
  const path = pathOf(a.asset_id).map((h) => `<span class="hop ${h.status}" data-select="${h.asset_id}" style="cursor:pointer">${esc(h.asset_id)}</span>`).join("→");
  const dependents = S.assets.filter((x) => pathOf(x.asset_id).slice(1).some((h) => h.asset_id === a.asset_id));
  const trafficable = ["ring_fiber", "backup_link", "cell_site", "edge_dc", "iot_gateway"].includes(a.kind);
  return `<h3 class="mono">${esc(a.asset_id)}</h3>
    <div class="muted small">${esc(a.name)}</div>
    <div style="margin-top:8px; display:flex; gap:6px; flex-wrap:wrap">${statusPill(a.status)} <span class="pill info">${esc(a.kind.replace(/_/g, " "))}</span>
      <span class="pill info">${esc(districtName(a.district))}</span>${a.critical ? `<span class="pill lock">critical · locked</span>` : ""}</div>
    ${al ? `<div class="section-label">Alarms</div>${al}` : ""}
    <div class="section-label">Live readings</div><div class="kv">${kv || "<div>none</div><div></div>"}</div>
    ${cfg ? `<div class="section-label">Configuration</div><div class="kv">${cfg}</div>` : ""}
    ${a.uplink ? `<div class="section-label">Path to the internet</div><div class="path">${path}</div>` : ""}
    ${dependents.length ? `<div class="section-label">Depends on it</div><div class="small">${dependents.length} assets: ${dependents.slice(0, 8).map((d) => idLink(d.asset_id)).join(" ")}${dependents.length > 8 ? " …" : ""}</div>` : ""}
    <div style="display:flex; gap:6px; margin-top:16px; flex-wrap:wrap">
      <button class="btn primary small" data-ask="Check ${esc(a.asset_id)}: is anything wrong with it, why, and what should I do?">Ask PulseNet</button>
      ${trafficable ? `<button class="btn small" data-go="#/traffic?focus=${esc(a.asset_id)}">Traffic view</button>` : ""}
    </div>`;
}

// ---------------------------------------------------------------- page: traffic
function meter(now, peak, color) {
  return `<div class="meter"><div class="fill" style="width:${Math.min(100, now)}%;background:${color}"></div>
    ${peak != null ? `<div class="peak" style="width:${Math.min(100, peak)}%"></div>` : ""}<div class="limit" style="left:${INTENT_LIMIT}%"></div></div>`;
}

function dayChart(id) {
  const a = S.byId[id];
  if (!a) return "";
  const u = a.metrics.utilisation_pct || 0, base = profileAt(9.5);
  const w = 640, h = 230, l = 40, t = 14, ch = 180, cw = w - l - 14;
  const yMax = Math.max(130, Math.ceil((u / base) * 1.05 / 10) * 10);
  const X = (hr) => l + (hr / 24) * cw, Y = (v) => t + ch - (v / yMax) * ch;
  let d = "";
  for (let hr = 0; hr <= 24; hr += 0.25) d += `${hr ? "L" : "M"}${X(hr).toFixed(1)},${Y((u * profileAt(Math.min(hr, 23.99))) / base).toFixed(1)} `;
  let grid = "";
  for (let v = 0; v <= yMax; v += yMax > 150 ? 50 : 25) grid += `<line x1="${l}" x2="${w - 14}" y1="${Y(v)}" y2="${Y(v)}" stroke="#e6e1d6"/><text x="${l - 6}" y="${Y(v) + 4}" text-anchor="end">${v}%</text>`;
  for (let hr = 0; hr <= 24; hr += 3) grid += `<text x="${X(hr)}" y="${h - 14}" text-anchor="middle">${String(hr).padStart(2, "0")}:00</text>`;
  const peak = (u * profileAt(21)) / base;
  return `<svg class="chart" viewBox="0 0 ${w} ${h}">${grid}
    <rect x="${l}" y="${Y(yMax)}" width="${cw}" height="${Y(INTENT_LIMIT) - Y(yMax)}" fill="#f4dcd7" opacity=".45"/>
    <line x1="${l}" x2="${w - 14}" y1="${Y(INTENT_LIMIT)}" y2="${Y(INTENT_LIMIT)}" stroke="var(--bad)" stroke-dasharray="5 4"/>
    <text x="${w - 16}" y="${Y(INTENT_LIMIT) - 5}" text-anchor="end" style="fill:var(--bad)">intent limit ${INTENT_LIMIT} %</text>
    <path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2.4"/>
    <line x1="${X(9.5)}" x2="${X(9.5)}" y1="${t}" y2="${t + ch}" stroke="var(--ink)" stroke-dasharray="2 3"/>
    <text x="${X(9.5) + 4}" y="${t + 10}" style="fill:var(--ink)">now 09:30 · ${Math.round(u)} %</text>
    <circle cx="${X(21)}" cy="${Y(peak)}" r="4.5" fill="${peak > INTENT_LIMIT ? "var(--bad)" : "var(--ok)"}"/>
    <text x="${X(21)}" y="${Y(peak) - 9}" text-anchor="middle" style="fill:${peak > INTENT_LIMIT ? "var(--bad)" : "var(--ok)"};font-weight:600">21:00 · ${Math.round(peak)} %</text>
  </svg>`;
}

function pageTraffic() {
  const pf = peakFactor();
  const links = RING.concat("BACKUP-WAVE-1").map((id) => S.byId[id]).filter(Boolean);
  const linkRows = links.map((f) => {
    const down = f.status === "down", u = f.metrics.utilisation_pct || 0, peak = down ? 0 : u * pf;
    const off = f.kind === "backup_link" && f.config.state !== "enabled";
    return `<tr class="${S.focus.includes(f.asset_id) ? "focus" : ""}" data-seg="${f.asset_id}" style="cursor:pointer">
      <td>${idLink(f.asset_id)}<div class="small muted">${esc(f.metrics.duct || "")} · ${f.metrics.capacity_gbps}G</div></td>
      <td style="width:38%">${down ? `<span class="pill down">cut since ${hhmm(f.metrics.down_since)}</span>` : off ? `<span class="pill info">disabled</span>` : meter(u, peak, utilColor(u))}</td>
      <td class="mono">${down || off ? "–" : pct(u)}</td><td class="mono">${down || off ? "–" : pct(peak)}</td>
      <td>${down ? statusPill("down") : off ? `<span class="pill info">standby</span>` : peak > INTENT_LIMIT ? `<span class="pill critical">breaks INT-2</span>` : `<span class="pill ok">ok</span>`}</td></tr>`;
  }).join("");

  const sites = S.assets.filter((a) => a.kind === "cell_site");
  const siteRows = sites.map((s) => {
    const m = s.metrics, prb = m.prb_dl_pct || 0;
    const sectors = Object.entries(m.sectors || {}).map(([k, v]) => `<span class="${v === 0 && s.status !== "down" ? "zero" : ""}" title="sector ${k}">S${k} ${v}</span>`).join("");
    const power = m.power === "battery" ? `<span class="pill warn">battery ${m.battery_pct}% · ${m.battery_minutes_left} min</span>` : `<span class="small muted">mains</span>`;
    return `<tr class="${S.focus.includes(s.asset_id) ? "focus" : ""}"><td>${idLink(s.asset_id)}</td><td>${statusPill(s.status)}</td>
      <td style="width:22%">${meter(prb, null, prb > 90 ? "var(--bad)" : prb > 75 ? "var(--warn)" : "var(--ok)")}</td>
      <td class="mono">${pct(prb)}</td><td class="mono">${m.users}</td><td><div class="sectors">${sectors}</div></td><td>${power}</td>
      <td class="small">${esc(s.config.second_carrier)}</td></tr>`;
  }).join("");

  const dcs = S.assets.filter((a) => a.kind === "edge_dc").map((d) => {
    const m = d.metrics, trend = m.inlet_temp_trend_c_per_10min;
    const toShut = trend > 0 ? Math.round(((m.shutdown_c - m.inlet_temp_c) / trend) * 10) : null;
    return `<tr class="${S.focus.includes(d.asset_id) ? "focus" : ""}"><td>${idLink(d.asset_id)}</td><td>${statusPill(d.status)}</td>
      <td class="mono">${m.inlet_temp_c} °C</td><td class="mono">${trend > 0 ? "+" : ""}${trend} °C / 10 min</td>
      <td>${toShut != null ? `<span class="pill critical">shutdown in ~${toShut} min</span>` : `<span class="pill ok">stable</span>`}</td>
      <td class="mono">${m.vms} VMs${m.free_capacity_vms ? ` · ${m.free_capacity_vms} free` : ""}</td></tr>`;
  }).join("");

  const iots = S.assets.filter((a) => a.kind === "iot_gateway").map((g) => {
    const m = g.metrics, hot = m.uplink_mbps > m.normal_uplink_mbps * 3;
    return `<tr class="${S.focus.includes(g.asset_id) ? "focus" : ""}"><td>${idLink(g.asset_id)}</td><td>${statusPill(g.status)}</td>
      <td class="mono">${m.uplink_mbps} Mbps</td><td class="mono muted">${m.normal_uplink_mbps} Mbps</td>
      <td>${m.external_connections?.length ? `<span class="pill critical">${esc(m.external_connections.join(", "))}</span>` : `<span class="small muted">none</span>`}</td>
      <td>${hot ? `<span class="pill critical">${Math.round(m.uplink_mbps / m.normal_uplink_mbps)}× normal</span>` : `<span class="pill ok">normal</span>`}</td></tr>`;
  }).join("");

  const pick = RING.concat("BACKUP-WAVE-1").map((id) => `<button class="${S.segment === id ? "on" : ""}" data-seg="${id}">${id.replace("FIBER-", "")}</button>`).join("");

  return `<h1 class="page-title">Traffic &amp; capacity</h1>
    <p class="page-sub">Live load and the evening-peak forecast from the 30-day hourly traffic profile (21:00 is ${pf.toFixed(2)}× the traffic now).</p>
    <div class="grid g-2e">
      <div class="card"><div class="card-h"><h2>Backbone ring</h2><span class="small muted">bar = now · dashed = 21:00 peak · line = ${INTENT_LIMIT} % limit</span></div>
        <div class="card-b flush"><table><thead><tr><th>Link</th><th>Load</th><th>Now</th><th>21:00</th><th></th></tr></thead><tbody>${linkRows}</tbody></table></div></div>
      <div class="card"><div class="card-h"><h2>Today, projected</h2><div class="seg-pick">${pick}</div></div>
        <div class="card-b">${dayChart(S.segment)}</div></div>
    </div>
    <div class="card" style="margin-top:14px"><div class="card-h"><h2>5G cell sites · radio load</h2><span class="small muted">PRB = share of radio resources in use · a sector with 0 users and no alarm is a sleeping cell</span></div>
      <div class="card-b flush"><table><thead><tr><th>Site</th><th>Status</th><th>PRB downlink</th><th></th><th>Users</th><th>Sectors</th><th>Power</th><th>2nd carrier</th></tr></thead><tbody>${siteRows}</tbody></table></div></div>
    <div class="grid g-2e" style="margin-top:14px">
      <div class="card"><div class="card-h"><h2>Edge data centers · cooling</h2><span class="small muted">recommended ≤ 27 °C · shutdown 35 °C</span></div>
        <div class="card-b flush"><table><thead><tr><th>Site</th><th>Status</th><th>Inlet</th><th>Trend</th><th></th><th>Load</th></tr></thead><tbody>${dcs}</tbody></table></div></div>
      <div class="card"><div class="card-h"><h2>City IoT gateways · uplink</h2></div>
        <div class="card-b flush"><table><thead><tr><th>Gateway</th><th>Status</th><th>Uplink</th><th>Normal</th><th>External sessions</th><th></th></tr></thead><tbody>${iots}</tbody></table></div></div>
    </div>`;
}

// ---------------------------------------------------------------- page: controller
const STAGES = [
  ["Monitor", "collect alarms & intents"], ["Analyse", "trace, forecast, search"], ["Decide", "engineer approves"],
  ["Execute", "apply the change"], ["Verify", "re-check the intents"],
];
const STAGE_OF = { get_overview: 0, check_intents: 0, list_assets: 0, list_tickets: 0, get_asset: 1, trace_path: 1,
  impact_of: 1, search_logs: 1, forecast: 1, search_knowledge: 1, update_config: 3, restart_asset: 3, open_ticket: 3 };

function loopStage(job) {
  if (!job) return { reached: -1, active: -1 };
  let reached = -1, executed = false;
  for (const s of job.steps) {
    if (s.kind === "call") {
      const st = STAGE_OF[s.tool] ?? 1;
      if (executed && st === 0) reached = 4;
      else if (st === 3) { reached = Math.max(reached, 3); if (s.tool !== "open_ticket") executed = true; }
      else reached = Math.max(reached, st);
    }
    if (s.kind === "approval") reached = Math.max(reached, 2);
  }
  if (job.pending_approval) reached = 2;
  return { reached, active: job.done ? -1 : reached };
}

function pendingCard(job) {
  const p = job.pending_approval;
  return `<div class="pending"><b>Change waiting for approval</b> <span class="small muted">· job ${esc(job.id)} · "${esc(job.message.slice(0, 80))}"</span>
    <div class="call">${esc(p.tool)}(${esc(JSON.stringify(p.args))})</div>
    <div style="display:flex;gap:8px"><button class="btn approve" data-approve="${job.id}">Approve</button>
      <button class="btn reject" data-reject="${job.id}">Reject</button></div></div>`;
}

function pageController() {
  const job = S.jobs[0];
  const { reached, active } = loopStage(job);
  const loop = STAGES.map(([n, w], i) => `<div class="stage ${i === active ? "active" : i <= reached ? "done" : ""}">
      <div class="dot" ${phase(1600)}>${i + 1}</div><div class="name">${n}</div><div class="what">${w}</div></div>`).join("");
  const pending = S.jobs.filter((j) => j.pending_approval);

  const configurable = S.assets.filter((a) => Object.keys(a.config).length);
  const configRows = configurable.map((a) => `<tr class="${S.focus.includes(a.asset_id) ? "focus" : ""}"><td>${idLink(a.asset_id)}</td>
      <td class="small muted">${esc(a.kind.replace(/_/g, " "))}</td><td>${statusPill(a.status)}</td>
      <td>${Object.entries(a.config).map(([k, v]) => `<span class="pill cfg ${["enabled", "quarantine"].includes(v) || (k === "migrate_to" && v !== "none") ? "ok" : "info"}" style="margin:0 4px 3px 0">${esc(k)}=${esc(v)}</span>`).join("")}</td></tr>`).join("");
  const locked = S.assets.filter((a) => a.critical).map((a) => `<span class="pill lock" style="margin:0 4px 4px 0">🔒 ${esc(a.asset_id)}</span>`).join("");

  const audit = S.audit.slice().reverse().map((r) => {
    let d = r.detail; try { d = JSON.parse(r.detail); } catch { /* text */ }
    const what = d.changed ? `${d.changed.join(", ")}: ${d.setting}=${d.value}` : d.ticket_id ? `${d.ticket_id} for ${d.asset_id} → ${d.team}` : d.asset_id ? `${d.asset_id}: ${d.now || "restarted"}` : JSON.stringify(d);
    return `<tr><td class="mono small">${hhmm(r.ts)}</td><td><span class="pill info">${esc(r.action)}</span></td><td>${esc(what)}</td>
      <td class="small muted">${esc((d.effects || []).join("; "))}</td></tr>`;
  }).join("");
  const tickets = S.tickets.map((t) => `<tr><td class="mono">${esc(t.ticket_id)}</td><td>${idLink(t.asset_id)}</td><td>${esc(t.team)}</td>
      <td>${statusPill(t.priority === "urgent" ? "critical" : t.priority === "high" ? "major" : "minor").replace(/>[a-z]+</, `>${esc(t.priority)}<`)}</td>
      <td class="small">${esc(t.summary)}</td></tr>`).join("");
  const jobs = S.jobs.map((j) => `<tr><td class="mono small">${esc(j.id)}</td><td>${esc(j.message.slice(0, 90))}</td>
      <td class="mono">${j.steps.filter((s) => s.kind === "call").length}</td>
      <td>${j.pending_approval ? `<span class="pill warn">awaiting approval</span>` : j.done ? `<span class="pill ok">done</span>` : `<span class="pill info">running</span>`}</td></tr>`).join("");
  const m = S.meta || {};

  return `<h1 class="page-title">Network controller</h1>
    <p class="page-sub">The closed loop (ETSI ZSM): what PulseNet is doing, what it wants to change, and what the network is configured to now.</p>
    <div class="card"><div class="card-h"><h2>Closed loop · ${job ? `job ${esc(job.id)}` : "idle"}</h2>
      <span class="small muted">${job ? esc(job.message.slice(0, 90)) : "ask the agent something to start the loop"}</span></div><div class="loop">${loop}</div></div>
    <div class="grid g-2" style="margin-top:14px">
      <div class="card"><div class="card-h"><h2>Approval queue</h2><span class="small muted">update_config and restart_asset always stop here</span></div>
        <div class="card-b">${pending.length ? pending.map(pendingCard).join("") : `<div class="empty">No change is waiting. PulseNet cannot change anything without you.</div>`}</div></div>
      <div class="card"><div class="card-h"><h2>Policy &amp; guards</h2><span class="pill lock">enforced in code</span></div>
        <div class="card-b policy">
          <div>Autonomy level</div><div><b>L3</b> · system executes, human decides (ITU-T Y.3173)</div>
          <div>Needs approval</div><div class="mono small">update_config · restart_asset</div>
          <div>Never changed</div><div class="mono small">${(m.critical_prefixes || []).map((p) => p + "*").join("  ")}</div>
          <div>Budgets</div><div>${m.max_steps ?? 14} tool rounds · $${m.max_cost ?? 0.05} per request</div>
          <div>Device text</div><div>wrapped in &lt;device_text&gt; tags, treated as data</div>
          <div>Model</div><div class="mono small">${esc(m.model || "")}</div>
        </div></div>
    </div>
    <div class="grid g-2" style="margin-top:14px">
      <div class="card"><div class="card-h"><h2>Device configuration</h2><span class="small muted">settings PulseNet may change</span></div>
        <div class="card-b flush"><table><thead><tr><th>Asset</th><th>Kind</th><th>Status</th><th>Settings</th></tr></thead><tbody>${configRows}</tbody></table></div></div>
      <div class="card"><div class="card-h"><h2>Locked assets</h2><span class="small muted">deny list</span></div><div class="card-b">${locked}</div>
        <div class="card-h" style="border-top:1px solid var(--line-2)"><h2>Agent jobs</h2>
          <button class="btn small" data-reset>Reset network to 09:30</button></div>
        <div class="card-b flush"><table><tbody>${jobs || `<tr><td class="empty">No requests yet.</td></tr>`}</tbody></table></div></div>
    </div>
    <div class="card" style="margin-top:14px"><div class="card-h"><h2>Change log (audit)</h2></div>
      <div class="card-b flush"><table><thead><tr><th>Time</th><th>Action</th><th>What</th><th>Effect</th></tr></thead>
      <tbody>${audit || `<tr><td colspan="4" class="empty">No changes yet.</td></tr>`}</tbody></table></div></div>
    <div class="card" style="margin-top:14px"><div class="card-h"><h2>Tickets</h2></div>
      <div class="card-b flush"><table><thead><tr><th>Ticket</th><th>Asset</th><th>Team</th><th>Priority</th><th>Summary</th></tr></thead>
      <tbody>${tickets || `<tr><td colspan="5" class="empty">No tickets yet.</td></tr>`}</tbody></table></div></div>`;
}

// ---------------------------------------------------------------- agent panel
function mentionedIds(text) {
  const ids = Object.keys(S.byId).sort((a, b) => b.length - a.length);
  const found = new Set();
  for (const id of ids) if (new RegExp(`\\b${id}\\b`).test(text)) found.add(id);
  if (/\bD-114\b/.test(text)) { found.add("FIBER-AZIZIYAH-QUBA"); found.add("SPUR-AZIZIYAH-02"); }
  return [...found];
}

function markdown(text) {
  const lines = esc(text).split(/\r?\n/);
  let html = "", list = null, table = [];
  const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const flushList = () => { if (list) { html += `</${list}>`; list = null; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\s*\|?[\s:|-]+\|?\s*$/.test(r));
    html += `<table class="small">${rows.map((r, i) => `<tr>${r.replace(/^\s*\||\|\s*$/g, "").split("|").map((c) => i ? `<td>${inline(c.trim())}</td>` : `<th>${inline(c.trim())}</th>`).join("")}</tr>`).join("")}</table>`;
    table = [];
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^\s*\|/.test(line)) { flushList(); table.push(line); continue; }
    flushTable();
    let m;
    if ((m = line.match(/^\s*[-*•]\s+(.*)/))) { if (list !== "ul") { flushList(); html += "<ul>"; list = "ul"; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== "ol") { flushList(); html += "<ol>"; list = "ol"; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = line.match(/^#+\s+(.*)/))) { flushList(); html += `<p><b>${inline(m[1])}</b></p>`; }
    else if (line.trim()) { flushList(); html += `<p>${inline(line)}</p>`; }
    else flushList();
  }
  flushList(); flushTable();
  return chipify(html);
}

function chipify(html) {
  const ids = Object.keys(S.byId).sort((a, b) => b.length - a.length);
  if (!ids.length) return html;
  const re = new RegExp(`\\b(${ids.map((i) => i.replace(/-/g, "\\-")).join("|")}|D-114)\\b`, "g");
  return html.split(/(<[^>]+>)/).map((part) => part.startsWith("<") ? part
    : part.replace(re, (id) => `<span class="chip" data-go="#/topology?focus=${id === "D-114" ? "FIBER-AZIZIYAH-QUBA,SPUR-AZIZIYAH-02" : id}" title="show on the map">${id}</span>`)).join("");
}

function addMsg(cls, html) {
  const div = document.createElement("div");
  div.className = `msg ${cls}`;
  div.innerHTML = html;
  $("#agentLog").appendChild(div);
  $("#agentLog").scrollTop = 1e9;
  return div;
}

const WHERE = /\b(where|locate|location|show me|take me|on the map|exactly|which (link|segment|site|cable|duct))\b/i;
const TRAFFIC = /\b(traffic|peak|utili[sz]ation|capacity|congest\w*|load|prb|forecast)\b/i;

async function sendToAgent(message) {
  message = message.trim();
  if (!message || S.chat.busy) return;
  showAgent(true);
  addMsg("user", esc(message));
  const bot = addMsg("bot", `<details class="steps" open><summary><span class="spinner"></span> <span class="sum">Thinking…</span></summary><ol></ol></details><div class="ans"></div>`);
  setBusy(true);
  let job;
  try {
    job = (await api("/v1/chat", { method: "POST", body: JSON.stringify({ message }) })).job_id;
  } catch (e) {
    bot.innerHTML = `<b>Could not reach PulseNet:</b> ${esc(e.message)}`;
    setBusy(false); return;
  }
  S.chat.job = job;
  const tick = async () => {
    let st;
    try { st = await api(`/v1/jobs/${job}`); } catch { setTimeout(tick, 1500); return; }
    renderSteps(bot, st);
    if (!st.done) { setTimeout(tick, 900); return; }
    const answer = st.answer || "(no answer)";
    const ids = mentionedIds(answer);
    const changed = st.steps.some((s) => s.kind === "approval" && s.text.endsWith("approved"));
    bot.querySelector(".ans").innerHTML = markdown(answer) + goButtons(ids, answer);
    bot.querySelector("details").open = false;
    bot.querySelector(".spinner")?.remove();
    setBusy(false);
    poll();
    if (ids.length && WHERE.test(message)) {
      const onTraffic = TRAFFIC.test(message) && ids.some((i) => i.startsWith("FIBER-") || i.startsWith("SITE-"));
      setTimeout(() => go(`#/${onTraffic ? "traffic" : "topology"}?focus=${ids.join(",")}`), 600);
    } else if (changed) toast("good", "Change applied", "The network map and the controller page now show the new state.");
    $("#agentLog").scrollTop = 1e9;
  };
  tick();
}

function renderSteps(bot, st) {
  const calls = st.steps.filter((s) => s.kind === "call").length;
  const list = st.steps.filter((s) => ["call", "guard", "approval", "error"].includes(s.kind)).map((s) =>
    `<li class="${s.kind}">${esc(s.kind === "call" ? s.text.slice(0, 160) : `${s.kind}: ${s.text.slice(0, 160)}`)}</li>`).join("");
  bot.querySelector("ol").innerHTML = list;
  bot.querySelector(".sum").textContent = st.done ? `${calls} tool calls` : st.pending_approval ? "Waiting for your approval…" : `Working · ${calls} tool calls`;
  const ans = bot.querySelector(".ans");
  if (st.pending_approval && !ans.querySelector(".pending")) {
    ans.innerHTML = pendingCard(st);
    $("#agentLog").scrollTop = 1e9;
  } else if (!st.pending_approval && ans.querySelector(".pending")) ans.innerHTML = "";
}

function goButtons(ids, answer) {
  if (!ids.length) return "";
  const traffic = ids.filter((i) => /^(FIBER|SITE|EDGE-DC|IOT-GW|BACKUP)/.test(i));
  return `<div class="go"><button class="btn small" data-go="#/topology?focus=${ids.join(",")}">Show on topology (${ids.length})</button>
    ${traffic.length && TRAFFIC.test(answer) ? `<button class="btn small" data-go="#/traffic?focus=${traffic.join(",")}">Traffic view</button>` : ""}
    <button class="btn small" data-go="#/controller">Controller</button></div>`;
}

function setBusy(b) {
  S.chat.busy = b;
  $("#agentSend").disabled = b;
  $("#agentSend").textContent = b ? "…" : "Send";
}

function showAgent(on) { $("#agent").classList.toggle("hidden", !on); }

async function answerApproval(jobId, approve) {
  try {
    await api(`/v1/jobs/${jobId}/approval`, { method: "POST", body: JSON.stringify({ approve }) });
    toast(approve ? "good" : "major", approve ? "Change approved" : "Change rejected", approve ? "PulseNet is applying it now." : "PulseNet was told you said no.");
  } catch (e) { toast("major", "Approval failed", e.message); }
  document.querySelectorAll(`[data-approve="${jobId}"],[data-reject="${jobId}"]`).forEach((b) => (b.disabled = true));
  poll();
}

// ---------------------------------------------------------------- toasts and key
function toast(kind, title, body, actions = []) {
  const box = document.createElement("div");
  box.className = `toast ${kind === "critical" ? "" : kind}`;
  box.innerHTML = `<div class="t-h"><span>${esc(title)}</span><button class="icon-btn" style="font-size:16px">×</button></div>
    <div class="small">${esc(body)}</div>
    ${actions.length ? `<div class="t-a">${actions.map((a) => a.go ? `<button class="btn small" data-go="${esc(a.go)}">${esc(a.label)}</button>`
      : `<button class="btn small primary" data-ask="${esc(a.ask)}">${esc(a.label)}</button>`).join("")}</div>` : ""}`;
  box.querySelector(".icon-btn").onclick = () => box.remove();
  $("#toasts").appendChild(box);
  while ($("#toasts").children.length > 4) $("#toasts").firstChild.remove();
  setTimeout(() => box.remove(), actions.length ? 14000 : 6000);
}

function askKey(note = "") {
  $("#drawer").innerHTML = `<div class="modal"><b>PulseNet API key</b>
    <div class="small muted" style="margin-top:4px">${esc(note || "The key the API expects in X-API-Key (PULSENET_API_KEYS, default dev-key-1).")}</div>
    <input id="keyInput" value="${esc(S.key)}" autocomplete="off">
    <div style="display:flex;gap:8px;justify-content:flex-end"><button class="btn" id="keyCancel">Cancel</button><button class="btn primary" id="keySave">Save</button></div></div>`;
  $("#drawer").classList.add("open");
  $("#keyCancel").onclick = () => $("#drawer").classList.remove("open");
  $("#keySave").onclick = () => { S.key = $("#keyInput").value.trim(); save("pulsenet.key", S.key); $("#drawer").classList.remove("open"); poll(); };
}

// ---------------------------------------------------------------- events
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-go],[data-ask],[data-select],[data-seg],[data-approve],[data-reject],[data-replay],[data-reset]");
  if (!t) return;
  if (t.dataset.go) { e.preventDefault(); go(t.dataset.go); }
  else if (t.dataset.ask) sendToAgent(t.dataset.ask);
  else if (t.dataset.approve) answerApproval(t.dataset.approve, true);
  else if (t.dataset.reject) answerApproval(t.dataset.reject, false);
  else if (t.dataset.seg) { S.segment = t.dataset.seg; render(); }
  else if (t.dataset.select) {
    S.selected = t.dataset.select;
    if (S.route !== "topology") go(`#/topology?focus=${t.dataset.select}`); else { S.focus = [t.dataset.select]; render(); }
  } else if (t.hasAttribute("data-replay")) {
    S.replay = S.replay ? null : { start: Date.now() };
    S.seenLogs = 0;
    if (S.replay) toast("major", "Replaying 06:00 → 09:30", "Watch the alarms arrive as they did this morning.");
    render();
  } else if (t.hasAttribute("data-reset")) {
    if (!confirm("Reset the network to Monday 09:30? Changes, tickets and the agent's memory are cleared.")) return;
    api("/v1/reset", { method: "POST" }).then(() => { toast("good", "Network reset", "Back to Monday 09:30."); S.firstLoad = true; poll(); })
      .catch((err) => toast("major", "Reset failed", err.message));
  }
});

$("#agentForm").addEventListener("submit", (e) => { e.preventDefault(); const t = $("#agentText"); sendToAgent(t.value); t.value = ""; });
$("#agentText").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#agentForm").requestSubmit(); } });
$("#suggest").addEventListener("click", (e) => { if (e.target.tagName === "BUTTON") sendToAgent(e.target.textContent); });
$("#agentToggle").onclick = () => showAgent($("#agent").classList.contains("hidden"));
$("#agentClose").onclick = () => showAgent(false);
$("#keyBtn").onclick = () => askKey();
window.addEventListener("hashchange", parseRoute);

// replay alarms appear one by one; tell the engineer about each as it arrives
let replayShown = new Set();
setInterval(() => {
  const m = replayMinute();
  const clock = m == null ? "09:30" : `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(Math.floor(m % 60)).padStart(2, "0")}`;
  $("#shiftClock").textContent = `Mon 2 Nov 2026 · ${clock} · ${new Date().toLocaleTimeString("en-GB")}`;
  if (m == null) { replayShown = new Set(); return; }
  for (const a of visibleAlarms()) {
    const k = alarmKey(a);
    if (!replayShown.has(k)) { replayShown.add(k); if (a.severity !== "minor") toast(a.severity, `${a.severity} · ${a.asset_id}`, a.alarm, alarmActions(a)); }
  }
  render();
}, 1000);

parseRoute();
poll();
setInterval(poll, POLL_MS);
