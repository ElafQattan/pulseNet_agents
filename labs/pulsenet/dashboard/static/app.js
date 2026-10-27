const DISTRICTS = {
  QUBA: "Quba", AZIZIYAH: "Al-Aziziyah", SULTANAH: "Sultanah", UYUN: "Al-Uyun", CENTER: "Control Center",
};
const SUGGESTIONS = [
  "Good morning, what broke during last night's rain? Where do I start?",
  "Water is rising in the Quba Road underpass. What's going on?",
  "Half the streetlights on Sultanah Road are off.",
  "The data platform is slow. Why?",
  "Turn the Al-Aziziyah traffic signal back to normal.",
];

let state = null;
let deviceFilter = { text: "", district: "", status: "" };
const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function time(ts) {
  return ts ? ts.slice(11, 16) : "—";
}

// ---------------------------------------------------------------- dashboard
async function loadState() {
  state = await (await fetch("/api/state")).json();
  const w = state.weather;
  $("weather").textContent = `🌧 ${w.rain_last_24h_mm} mm overnight · stopped ${time(w.rain_stopped)} · ${w.temperature_c}°C`;
  $("clock").textContent = state.time;
  renderKpis();
  renderDistricts();
  renderAlerts();
  renderFilters();
  renderDevices();
  renderTickets();
  renderLogs();
}

function renderKpis() {
  const d = state.devices;
  const online = d.filter((x) => x.status === "online").length;
  const urgent = state.alerts.filter((a) => a.severity === "urgent").length;
  const open = state.tickets.filter((t) => t.status === "open").length;
  const tiles = [
    ["Devices", d.length, ""],
    ["Online", online, "ok"],
    ["Not online", d.length - online, d.length - online ? "warn" : "ok"],
    ["Urgent alerts", urgent, urgent ? "bad" : "ok"],
    ["Open tickets", open, ""],
  ];
  $("kpis").innerHTML = tiles.map(([label, value, cls]) =>
    `<div class="kpi ${cls}"><div class="label">${label}</div><div class="value">${value}</div></div>`).join("");
}

function renderDistricts() {
  $("districts").innerHTML = Object.entries(DISTRICTS).map(([code, name]) => {
    const devices = state.devices.filter((x) => x.district === code);
    const online = devices.filter((x) => x.status === "online").length;
    const alerts = state.alerts.filter((a) => a.district === code);
    const worst = ["urgent", "high", "normal"].find((s) => alerts.some((a) => a.severity === s)) || "";
    const pct = devices.length ? Math.round((100 * online) / devices.length) : 100;
    return `<div class="district ${worst}" data-district="${code}">
      <div class="name">${name}</div>
      <div class="sub">${online} of ${devices.length} online</div>
      <div class="bar"><div style="width:${pct}%"></div></div>
      <div class="issues">${alerts.length ? `${alerts.length} alert${alerts.length > 1 ? "s" : ""}` : "No alerts"}</div>
    </div>`;
  }).join("");
  document.querySelectorAll(".district").forEach((el) => el.onclick = () => {
    deviceFilter.district = el.dataset.district;
    $("district-filter").value = el.dataset.district;
    renderDevices();
    $("devices").scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

function renderAlerts() {
  $("alert-count").textContent = `${state.alerts.length} active`;
  $("alerts").innerHTML = state.alerts.map((a) => `
    <div class="alert">
      <span class="pill ${a.severity}">${a.severity}</span>
      <div>
        <div class="what">${esc(a.name)} <span class="dev-id">${esc(a.device_id)}</span></div>
        <div class="detail">${esc(a.alert)}</div>
      </div>
      <button class="btn ask" data-q="Look into this alert: ${esc(a.name)} (${esc(a.device_id)}): ${esc(a.alert)}">Ask PulseNet</button>
    </div>`).join("") || `<div class="muted">No active alerts.</div>`;
  document.querySelectorAll(".alert .ask").forEach((b) => b.onclick = () => ask(b.dataset.q));
}

function renderFilters() {
  const d = $("district-filter"), s = $("status-filter");
  if (d.options.length === 1) {
    Object.entries(DISTRICTS).forEach(([code, name]) => d.add(new Option(name, code)));
    ["online", "offline", "degraded", "stopped", "tripped", "quarantined"].forEach((x) => s.add(new Option(x, x)));
  }
}

function renderDevices() {
  const f = deviceFilter;
  const rows = state.devices.filter((x) =>
    (!f.district || x.district === f.district) && (!f.status || x.status === f.status) &&
    (!f.text || `${x.name} ${x.device_id}`.toLowerCase().includes(f.text.toLowerCase())));
  $("devices").innerHTML = rows.map((x) => `
    <tr data-id="${x.device_id}">
      <td><div class="dev-name">${esc(x.name)}</div><div class="dev-id mono">${x.device_id}</div></td>
      <td>${x.kind}</td>
      <td>${DISTRICTS[x.district]}</td>
      <td><span class="status ${x.status}">${x.status}</span></td>
      <td class="mono">${time(x.last_seen)}</td>
      <td>${x.battery_pct == null ? "—" : x.battery_pct + " %"}</td>
    </tr>`).join("");
  document.querySelectorAll("#devices tr").forEach((tr) => tr.onclick = () => openDevice(tr.dataset.id));
}

function renderTickets() {
  $("tickets").innerHTML = state.tickets.map((t) => `
    <div class="ticket">
      <div class="top"><b class="mono">${t.ticket_id}</b><span class="pill ${t.priority === "urgent" ? "urgent" : t.priority === "high" ? "high" : "normal"}">${t.priority}</span>
        <span class="muted">${t.team} · ${t.device_id}</span></div>
      <div class="detail muted">${esc(t.summary)}</div>
    </div>`).join("") || `<div class="muted">No tickets yet. PulseNet opens them here.</div>`;
}

function renderLogs() {
  $("logs").innerHTML = state.logs.map((l) =>
    `<div class="lvl-${l.level}" title="${esc(l.message)}">${time(l.ts)} ${l.device_id} ${esc(l.message)}</div>`).join("");
}

async function openDevice(id) {
  const d = await (await fetch(`/api/devices/${id}`)).json();
  $("drawer-title").textContent = d.name;
  $("drawer-id").textContent = d.device_id;
  const kv = (obj) => `<div class="kv">${Object.entries(obj || {}).map(([k, v]) =>
    `<div class="k">${esc(k)}</div><div class="v mono">${esc(typeof v === "object" ? JSON.stringify(v) : v)}</div>`).join("")}</div>`;
  const main = { status: d.status, kind: d.kind, district: DISTRICTS[d.district], connectivity: d.connectivity,
    gateway: d.gateway_id || "—", cabinet: d.cabinet_id || "—", last_seen: d.last_seen,
    battery: d.battery_pct == null ? "—" : d.battery_pct + " %", firmware: d.firmware };
  $("drawer-body").innerHTML = kv(main) +
    `<h3>Readings</h3>${kv(d.metrics)}` +
    (d.signal ? `<h3>Signal</h3>${kv(d.signal)}` : "") +
    (Object.keys(d.config).length ? `<h3>Settings</h3>${kv(d.config)}` : "") +
    `<h3>Reported description</h3><div class="muted">${esc(d.description)}</div>`;
  $("drawer-ask").onclick = () => { closeDrawer(); ask(`What's going on with ${d.name} (${d.device_id})?`); };
  $("drawer").hidden = false;
}

function closeDrawer() { $("drawer").hidden = true; }

// ---------------------------------------------------------------- chat
function markdown(text) {
  // a small renderer: headings, bold, code, lists, tables, rules
  const lines = esc(text).split("\n");
  let html = "", list = null, table = [];
  const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const flushList = () => { if (list) { html += `</${list}>`; list = null; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\|?\s*:?-{2,}/.test(r));
    html += "<table>" + rows.map((r, i) => "<tr>" + r.replace(/^\||\|$/g, "").split("|")
      .map((c) => `<${i ? "td" : "th"}>${inline(c.trim())}</${i ? "td" : "th"}>`).join("") + "</tr>").join("") + "</table>";
    table = [];
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line.trim().startsWith("|")) { flushList(); table.push(line.trim()); continue; }
    flushTable();
    let m;
    if ((m = line.match(/^#{1,4}\s+(.*)/))) { flushList(); html += `<h4>${inline(m[1])}</h4>`; }
    else if (/^\s*(---|\*\*\*)\s*$/.test(line)) { flushList(); html += "<hr>"; }
    else if ((m = line.match(/^\s*[-*•]\s+(.*)/))) { if (list !== "ul") { flushList(); html += "<ul>"; list = "ul"; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== "ol") { flushList(); html += "<ol>"; list = "ol"; } html += `<li>${inline(m[1])}</li>`; }
    else if (!line.trim()) { flushList(); }
    else { flushList(); html += `<p>${inline(line)}</p>`; }
  }
  flushList(); flushTable();
  return html;
}

function addMessage(who, html) {
  const el = document.createElement("div");
  el.className = `msg ${who}`;
  el.innerHTML = `<div class="bubble">${html}</div>`;
  $("messages").appendChild(el);
  $("messages").scrollTop = $("messages").scrollHeight;
  return el;
}

function stepLine(e) {
  const labels = { call: "", result: "  ← ", error: "⚠ ", guard: "🛡 ", approval: "✔ technician " };
  if (e.kind === "user" || e.kind === "final") return "";
  if (e.kind === "model") return `<div class="step">💭 ${esc(e.text)}</div>`;
  return `<div class="step ${e.kind}" title="${esc(e.text)}">${labels[e.kind] ?? ""}${esc(e.text)}</div>`;
}

async function ask(message) {
  message = (message || "").trim();
  if (!message) return;
  addMessage("user", esc(message));
  $("input").value = "";
  $("send").disabled = true;
  $("chat-status").textContent = "Working…";

  const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }) });
  if (!res.ok) {
    addMessage("bot", esc((await res.json()).detail || "Busy, try again."));
    $("send").disabled = false;
    return;
  }
  const { job_id } = await res.json();
  const work = addMessage("bot", `<div class="steps"><div class="thinking">Checking the network</div></div>`);
  let approvalShown = false;

  while (true) {
    await new Promise((r) => setTimeout(r, 700));
    const job = await (await fetch(`/api/jobs/${job_id}`)).json();
    work.querySelector(".steps").innerHTML = job.events.map(stepLine).join("") +
      (job.done ? "" : `<div class="thinking">${job.pending ? "Waiting for your approval" : "Working"}</div>`);

    if (job.pending && !approvalShown) {
      approvalShown = true;
      showApproval(job_id, job.pending, () => { approvalShown = false; });
    }
    if (job.done) {
      addMessage("bot", markdown(job.final));
      break;
    }
    $("messages").scrollTop = $("messages").scrollHeight;
  }
  $("send").disabled = false;
  $("chat-status").textContent = "Ready";
  loadState();
}

function showApproval(jobId, pending, onAnswered) {
  const card = addMessage("bot", `
    <div class="approval-card">
      <div class="title">🛡️ Approval needed</div>
      <div>PulseNet wants to run <b class="mono">${esc(pending.tool)}</b> with:</div>
      <pre>${esc(JSON.stringify(pending.args, null, 2))}</pre>
      <div class="actions">
        <button class="btn ok">Approve</button>
        <button class="btn no">Reject</button>
      </div>
    </div>`);
  const answer = async (approve) => {
    await fetch(`/api/jobs/${jobId}/approval`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approve }) });
    card.querySelector(".actions").innerHTML = approve ? "<b style='color:#86efac'>✔ Approved</b>" : "<b style='color:#fca5a5'>✕ Rejected</b>";
    onAnswered();
  };
  card.querySelector(".btn.ok").onclick = () => answer(true);
  card.querySelector(".btn.no").onclick = () => answer(false);
}

// ---------------------------------------------------------------- wiring
$("composer").onsubmit = (e) => { e.preventDefault(); ask($("input").value); };
$("input").onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask($("input").value); } };
$("search").oninput = (e) => { deviceFilter.text = e.target.value; renderDevices(); };
$("district-filter").onchange = (e) => { deviceFilter.district = e.target.value; renderDevices(); };
$("status-filter").onchange = (e) => { deviceFilter.status = e.target.value; renderDevices(); };
$("drawer-close").onclick = closeDrawer;
$("drawer").onclick = (e) => { if (e.target.id === "drawer") closeDrawer(); };
$("reset").onclick = async () => {
  if (!confirm("Put the city back to its 09:00 state and clear the conversation?")) return;
  await fetch("/api/reset", { method: "POST" });
  $("messages").innerHTML = "";
  addMessage("bot", "The city is back to its 09:00 state. Where should we start?");
  loadState();
};
$("suggestions").innerHTML = SUGGESTIONS.map((s) => `<button class="btn">${esc(s)}</button>`).join("");
document.querySelectorAll("#suggestions button").forEach((b) => b.onclick = () => ask(b.textContent));

loadState();
