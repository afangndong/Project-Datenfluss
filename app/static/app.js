/* Mini-KOS GUI – bewusst ohne Framework. Alle Daten werden per textContent gerendert (kein innerHTML → kein XSS). */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const fmtDate = d => (d ? new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) : "–");
const fmtDT = d => new Date(d).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}
const clear = el => { while (el.firstChild) el.firstChild.remove(); return el; };

function toast(msg, kind = "") {
  const t = h("div", { class: `toast ${kind}` }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), 4500);
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const key = sessionStorage.getItem("apiKey");
  if (key) headers["X-API-Key"] = key;
  const res = await fetch(path, { ...opts, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : (j.detail || []).map(e => e.msg).join("; ");
    } catch { /* kein JSON */ }
    if (res.status === 401) detail += " – API-Key über 🔑 oben rechts setzen.";
    throw new Error(detail);
  }
  return res.status === 204 ? null : { data: await res.json(), total: res.headers.get("X-Total-Count") };
}
const get = async p => (await api(p)).data;
const send = (method, p, body) => api(p, { method, body: body ? JSON.stringify(body) : undefined });
const guard = fn => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, "err"); } };

/* ---------- Navigation ---------- */
const loaders = { dashboard: loadDashboard, patienten: loadPatients, termine: loadAppointments, system: loadSystem };
let currentTab = "dashboard";
function showTab(name) {
  currentTab = name;
  history.replaceState(null, "", `#${name}`);
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach(s => (s.hidden = s.id !== `tab-${name}`));
  guard(loaders[name])();
}
$("#tabs").addEventListener("click", e => e.target.dataset.tab && showTab(e.target.dataset.tab));

/* ---------- Dashboard ---------- */
function bars(container, obj) {
  clear(container);
  const entries = Object.entries(obj);
  if (!entries.length) return container.append(h("p", { class: "empty" }, "Keine Daten."));
  const max = Math.max(...entries.map(([, v]) => v), 1);
  for (const [k, v] of entries.sort((a, b) => b[1] - a[1]))
    container.append(h("div", { class: "bar" }, h("span", {}, k),
      h("div", { class: "track" }, h("div", { class: "fill", style: `width:${(v / max) * 100}%` })), h("strong", {}, String(v))));
}
async function loadDashboard() {
  const [s, flags] = await Promise.all([get("/api/stats"), get("/api/flags")]);
  const cards = [["Patienten gesamt", s.patienten], ["Aktuell auf Station", s.aktuelle_aufenthalte],
    ["Termine heute", s.termine_heute], ["Offene Termine", s.termine_offen]];
  clear($("#statCards")).append(...cards.map(([l, n]) => h("div", { class: "card" }, h("div", { class: "n" }, String(n)), h("div", { class: "l" }, l))));
  $("#extraCards").hidden = !flags.neues_dashboard;
  $("#banner").hidden = !flags.wartungshinweis;
  bars($("#belegung"), s.belegung_je_station);
  bars($("#terminStatus"), s.termine_nach_status);
  const start = new Date(); start.setHours(0, 0, 0, 0);
  const all = await get(`/api/appointments?ab=${start.toISOString().slice(0, 19)}`);
  const today = all.filter(a => new Date(a.termin).toDateString() === new Date().toDateString());
  const box = clear($("#heute"));
  if (!today.length) box.append(h("p", { class: "empty" }, "Heute keine Termine."));
  today.forEach(a => box.append(h("div", { class: "item" }, h("span", {}, `${fmtDT(a.termin).slice(-5)} Uhr · ${a.patient_name} · ${a.art}`), tag(a.status))));
}
const tag = s => h("span", { class: `tag ${s}` }, s);

/* ---------- Patienten ---------- */
let selected = null, searchTimer;
$("#search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(guard(loadPatients), 250); });
async function loadPatients() {
  const q = encodeURIComponent($("#search").value.trim());
  const { data, total } = await api(`/api/patients?limit=100&q=${q}`);
  const body = clear($("#patTable tbody"));
  data.forEach(p => body.append(h("tr", { class: p.id === selected ? "sel" : "", onclick: guard(() => { selected = p.id; loadPatients(); loadDetail(p.id); }) },
    h("td", {}, p.fallnummer), h("td", {}, `${p.nachname}, ${p.vorname}`), h("td", {}, fmtDate(p.geburtsdatum)), h("td", {}, p.versicherung))));
  $("#patCount").textContent = `${data.length} von ${total} Patienten angezeigt`;
}
async function loadDetail(id) {
  const [p, stays, appts] = await Promise.all([get(`/api/patients/${id}`), get(`/api/stays?patient_id=${id}`), get(`/api/appointments?patient_id=${id}`)]);
  const d = clear($("#detail"));
  d.append(
    h("h2", {}, `${p.vorname} ${p.nachname}`),
    h("dl", { class: "kv" }, h("dt", {}, "Fallnummer"), h("dd", {}, p.fallnummer), h("dt", {}, "Geboren"), h("dd", {}, fmtDate(p.geburtsdatum)),
      h("dt", {}, "Geschlecht"), h("dd", {}, p.geschlecht), h("dt", {}, "Versicherung"), h("dd", {}, p.versicherung)),
    h("div", { class: "sub" }, h("button", { class: "small", onclick: () => openPatientForm(p) }, "Bearbeiten"), " ",
      h("button", { class: "small danger", onclick: guard(async () => { if (confirm("Patient inkl. Aufenthalte und Termine löschen?")) { await send("DELETE", `/api/patients/${id}`); selected = null; clear($("#detail")).append(h("p", { class: "muted" }, "Gelöscht.")); toast("Patient gelöscht", "ok"); loadPatients(); } }) }, "Löschen")),
    h("div", { class: "sub" }, h("h3", {}, "Aufenthalte", h("button", { class: "small", onclick: () => openStayForm(id) }, "+ Neu")),
      stays.length ? stays.map(s => h("div", { class: "item" }, h("span", {}, `${s.station}, Zi. ${s.zimmer} · ${fmtDate(s.aufnahme)} – ${s.entlassung ? fmtDate(s.entlassung) : "aktuell"}${s.diagnose ? " · " + s.diagnose : ""}`),
        s.entlassung ? null : h("button", { class: "small", onclick: guard(async () => { await send("POST", `/api/stays/${s.id}/entlassen`); toast("Patient entlassen", "ok"); loadDetail(id); }) }, "Entlassen"))) : h("p", { class: "empty" }, "Keine Aufenthalte.")),
    h("div", { class: "sub" }, h("h3", {}, "Termine", h("button", { class: "small", onclick: () => openApptForm(id) }, "+ Neu")),
      appts.length ? appts.map(a => h("div", { class: "item" }, h("span", {}, `${fmtDT(a.termin)} · ${a.art}`), tag(a.status))) : h("p", { class: "empty" }, "Keine Termine.")));
}

/* Dialoge */
function dialogResult(dlg, form, submit) {
  dlg.showModal();
  form.onsubmit = guard(async ev => {
    if (ev.submitter?.value !== "ok") return;
    await submit(Object.fromEntries(new FormData(form)));
  });
}
function openPatientForm(p = null) {
  const f = $("#formPatient"); f.reset();
  $("#dlgPatientTitle").textContent = p ? "Patient bearbeiten" : "Neuer Patient";
  if (p) for (const k of ["vorname", "nachname", "geburtsdatum", "geschlecht", "versicherung"]) f.elements[k].value = p[k];
  dialogResult($("#dlgPatient"), f, async data => {
    const r = p ? await send("PUT", `/api/patients/${p.id}`, data) : await send("POST", "/api/patients", data);
    toast(p ? "Gespeichert" : `Angelegt: ${r.data.fallnummer}`, "ok");
    selected = r.data.id; await loadPatients(); await loadDetail(selected);
  });
}
function openStayForm(pid) {
  const f = $("#formStay"); f.reset(); f.elements.aufnahme.value = new Date().toISOString().slice(0, 10);
  dialogResult($("#dlgStay"), f, async data => {
    data.patient_id = pid; data.diagnose ||= null;
    await send("POST", "/api/stays", data); toast("Aufenthalt angelegt", "ok"); loadDetail(pid);
  });
}
function openApptForm(pid) {
  const f = $("#formAppt"); f.reset();
  dialogResult($("#dlgAppt"), f, async data => {
    data.patient_id = pid; data.bemerkung ||= null;
    await send("POST", "/api/appointments", data); toast("Termin angelegt", "ok"); loadDetail(pid);
  });
}
$("#newPatient").addEventListener("click", () => openPatientForm());

/* ---------- Termine ---------- */
$("#statusFilter").addEventListener("change", guard(loadAppointments));
async function loadAppointments() {
  const st = $("#statusFilter").value;
  const list = await get(`/api/appointments${st ? `?status=${st}` : ""}`);
  const body = clear($("#apptTable tbody"));
  if (!list.length) body.append(h("tr", {}, h("td", { colspan: 5, class: "empty" }, "Keine Termine.")));
  list.forEach(a => body.append(h("tr", {}, h("td", {}, fmtDT(a.termin)), h("td", {}, a.patient_name), h("td", {}, a.art), h("td", {}, tag(a.status)),
    h("td", {}, ["erledigt", "abgesagt"].filter(s => s !== a.status).map(s => h("button", { class: "small", onclick: guard(async () => { await send("PATCH", `/api/appointments/${a.id}/status?status=${s}`); loadAppointments(); }) }, s)), " ",
      h("button", { class: "small danger", onclick: guard(async () => { if (confirm("Termin löschen?")) { await send("DELETE", `/api/appointments/${a.id}`); loadAppointments(); } }) }, "✕")))));
}

/* ---------- System ---------- */
async function loadSystem() {
  const [v, flags, links] = await Promise.all([get("/api/version"), get("/api/flags"), get("/api/links")]);
  const kv = (el, obj) => { clear(el); Object.entries(obj).forEach(([k, val]) => el.append(h("dt", {}, k), h("dd", {}, String(val)))); };
  kv($("#versionInfo"), { Anwendung: v.name, Version: v.version, "Git-SHA": v.git_sha, Umgebung: v.env, "Bedient von": v.instance });
  $("#simPanel").hidden = v.env === "prod";
  const probe = async p => { try { const r = await fetch(p); return r.ok ? "✔ ok" : `✖ HTTP ${r.status}`; } catch { return "✖ nicht erreichbar"; } };
  kv($("#healthInfo"), { "Liveness (/health)": await probe("/health"), "Readiness (/ready, DB)": await probe("/ready"), "Metriken (/metrics)": await probe("/metrics") });
  clear($("#flagList")).append(...Object.entries(flags).map(([k, on]) => h("div", { class: "flag" }, h("span", {}, k), h("span", { class: on ? "on" : "off" }, on ? "AN" : "AUS"))));
  clear($("#linkList")).append(...Object.entries(links).map(([k, u]) => h("li", {}, h("a", { href: u, target: "_blank", rel: "noopener" }, k), " ", h("span", { class: "muted" }, u))));
}
$("#simErr").addEventListener("click", guard(async () => { try { await send("GET", "/api/sim/error"); } catch (e) { toast(`Simulierter Fehler ausgelöst (${e.message})`, "ok"); } }));
$("#simSlow").addEventListener("click", guard(async () => { toast("Anfrage läuft (3 s) …"); await send("GET", "/api/sim/slow?sekunden=3"); toast("Langsame Antwort beendet", "ok"); }));

/* ---------- Kopfzeile ---------- */
$("#keyBtn").addEventListener("click", () => {
  const f = $("#formKey"); f.reset(); f.elements.key.value = sessionStorage.getItem("apiKey") || "";
  dialogResult($("#dlgKey"), f, async d => { d.key ? sessionStorage.setItem("apiKey", d.key) : sessionStorage.removeItem("apiKey"); toast("API-Key übernommen", "ok"); });
});
async function heartbeat() {
  try {
    const ok = (await fetch("/ready")).ok;
    $("#healthDot").className = `dot ${ok ? "ok" : "bad"}`; $("#healthDot").title = ok ? "System bereit" : "System nicht bereit";
  } catch { $("#healthDot").className = "dot bad"; }
}
(async () => {
  try { const v = await get("/api/version"); $("#envBadge").textContent = `${v.env} · v${v.version}`; } catch { /* egal */ }
  heartbeat(); setInterval(heartbeat, 10000);
  const wanted = location.hash.slice(1);  // Deep-Link, z. B. /#system
  showTab(loaders[wanted] ? wanted : "dashboard");
})();
