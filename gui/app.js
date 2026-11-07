// Lead Agent GUI. Plain JavaScript, no build step. All data comes from scripts/gui.py.
"use strict";

// ---------- helpers ----------
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => {
  u = String(u || "").trim();
  if (!u) return "";
  if (!/^https?:\/\//i.test(u)) u = "https://" + u;
  try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : ""; } catch { return ""; }
};
const link = (u, label) => { const s = safeUrl(u); return s ? `<a href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(label || shortUrl(u))}</a>` : esc(u); };
const shortUrl = (u) => String(u || "").replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "").slice(0, 60);
const splitList = (s) => String(s || "").split(";").map((x) => x.trim()).filter(Boolean);
const scoreCls = (n) => (n >= 70 ? "hi" : n >= 50 ? "mid" : "lo");
const scoreBadge = (r) => `<span class="score ${scoreCls(+r.fit_score)}">${esc(r.fit_score || 0)}</span>`;
const stageBadge = (s) => `<span class="stage ${esc(s)}">${esc(s.replace("_", " "))}</span>`;
const tagsHtml = (s) => splitList(s).map((t) => `<span class="tag">${esc(t)}</span>`).join("");
const addDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
const fmtNum = (n) => Number(n || 0).toLocaleString();

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-Lead-Agent": "1" }, body: JSON.stringify(body) };
  const res = await fetch("/api/" + path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

let toastTimer;
function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (err ? " err" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), err ? 6000 : 2600);
}
const fail = (e) => toast(e.message || String(e), true);

// ---------- state ----------
const S = {
  state: null,
  leads: [],
  byId: {},
  filters: loadPref("filters", { q: "", stage: "", min_score: "", tag: "", due: false, hideCandidates: true }),
  sort: loadPref("sort", { key: "fit_score", dir: -1 }),
  page: 0,
  selected: new Set(),
  boardCandidates: false,
  currentView: "",
};
function loadPref(k, d) { try { return Object.assign({}, d, JSON.parse(localStorage.getItem("la:" + k) || "{}")); } catch { return d; } }
function savePref(k, v) { try { localStorage.setItem("la:" + k, JSON.stringify(v)); } catch {} }

async function loadAll() {
  const [state, leads] = await Promise.all([api("state"), api("leads")]);
  S.state = state;
  S.leads = leads;
  S.byId = Object.fromEntries(leads.map((r) => [r.id, r]));
  renderChrome();
}

function renderChrome() {
  const st = S.state;
  $("#product-select").innerHTML = st.products.map((p) => `<option ${p === st.product ? "selected" : ""}>${esc(p)}</option>`).join("") + `<option value="__new">+ New product…</option>`;
  const newCount = S.leads.filter((r) => r.stage === "new").length;
  $("#badge-review").textContent = newCount || "";
  const t = st.today;
  const due = S.leads.filter((r) => r.next_action_date && r.next_action_date <= t && !["won", "lost", "rejected", "candidate"].includes(r.stage)).length;
  $("#badge-due").textContent = due || "";
  $("#badge-run").textContent = st.running ? `${st.running} running` : "";
}

$("#product-select").addEventListener("change", async (e) => {
  let name = e.target.value;
  if (name === "__new") {
    name = prompt("Name of the new product (for example: acme)");
    if (!name) { renderChrome(); return; }
  }
  try {
    await api("product", { name });
    S.selected.clear();
    S.currentView = "";
    await loadAll();
    route();
    toast(`Switched to ${S.state.product}`);
  } catch (err) { fail(err); }
});

// ---------- router ----------
const PAGES = {};
function route() {
  const page = (location.hash.replace(/^#\//, "").split("?")[0]) || "dashboard";
  $$("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  const fn = PAGES[page] || PAGES.dashboard;
  stopPolling();
  Promise.resolve(fn($("#main"))).catch(fail);
}
window.addEventListener("hashchange", route);

async function refresh() {
  await loadAll();
  route();
}

// ---------- filtering ----------
function matches(r, f) {
  if (f.stage) { if (!f.stage.split(",").includes(r.stage)) return false; }
  else if (f.hideCandidates && r.stage === "candidate") return false;
  if (f.min_score !== "" && f.min_score != null && +r.fit_score < +f.min_score) return false;
  if (f.tag && !splitList(r.tags).includes(f.tag)) return false;
  if (f.due && !(r.next_action_date && r.next_action_date <= S.state.today && !["won", "lost", "rejected"].includes(r.stage))) return false;
  if (f.q) {
    const hay = Object.values(r).join(" ").toLowerCase();
    if (!f.q.toLowerCase().split(/\s+/).filter(Boolean).every((w) => hay.includes(w))) return false;
  }
  return true;
}
const allTags = () => [...new Set(S.leads.flatMap((r) => splitList(r.tags)))].sort();

// ---------- dashboard ----------
PAGES.dashboard = async (el) => {
  const L = S.leads, t = S.state.today;
  const count = (s) => L.filter((r) => r.stage === s).length;
  const open = (r) => !["won", "lost", "rejected"].includes(r.stage);
  const overdue = L.filter((r) => open(r) && r.stage !== "candidate" && r.next_action_date && r.next_action_date < t);
  const today = L.filter((r) => open(r) && r.stage !== "candidate" && r.next_action_date === t);
  const approved = L.filter((r) => r.stage === "approved").sort((a, b) => b.fit_score - a.fit_score);
  const replied = L.filter((r) => ["replied", "meeting"].includes(r.stage));
  const topNew = L.filter((r) => r.stage === "new").sort((a, b) => b.fit_score - a.fit_score).slice(0, 5);
  const active = L.filter((r) => ["contacted", "replied", "meeting"].includes(r.stage)).length;

  const steps = [];
  if (!S.state.has_product_md) steps.push(`No product description yet. <a href="#/run">Run /setup-product</a> or write one under <a href="#/data">Product &amp; data</a>.`);
  else if (!S.state.has_icp) steps.push(`No ideal customer profile yet. <a href="#/run">Run /build-icp</a>.`);
  if (overdue.length) steps.push(`<b>${overdue.length}</b> follow-ups are overdue. <a href="#/followups">Open follow-ups</a>.`);
  if (replied.length) steps.push(`<b>${replied.length}</b> leads replied or have a meeting. Keep them moving.`);
  if (count("new")) steps.push(`<b>${count("new")}</b> researched leads are waiting for review. <a href="#/review">Review them</a>.`);
  if (approved.length) steps.push(`<b>${approved.length}</b> approved leads have not been contacted. <a href="#/outreach">Draft outreach</a>.`);
  if (count("candidate")) steps.push(`<b>${fmtNum(count("candidate"))}</b> unverified candidates. <a href="#/run?cmd=verify-candidates">Verify the next batch</a>.`);
  if (!L.length) steps.push(`No leads yet. <a href="#/run?cmd=find-leads">Find leads</a> or <a href="#/data">import a CSV</a>.`);

  el.innerHTML = `
    <h1>${esc(S.state.product_name)}</h1>
    <p class="sub">${fmtNum(L.length)} leads in <b>${esc(S.state.product)}</b> · today is ${esc(t)}</p>
    <div class="tiles">
      ${tile("Unverified candidates", count("candidate"), "#/leads?stage=candidate")}
      ${tile("To review", count("new"), "#/review")}
      ${tile("Approved", count("approved"), "#/leads?stage=approved")}
      ${tile("In conversation", active, "#/board")}
      ${tile("Won", count("won"), "#/leads?stage=won")}
      ${tile("Overdue", overdue.length, "#/followups")}
    </div>
    <div class="grid g2">
      <div class="card"><h2>What to do next</h2>${steps.length ? `<ul>${steps.map((s) => `<li>${s}</li>`).join("")}</ul>` : `<p class="muted">All caught up.</p>`}</div>
      <div class="card"><h2>Due today and overdue</h2>${todoList([...overdue, ...today].slice(0, 8), true) || `<p class="muted">Nothing due.</p>`}</div>
      <div class="card"><h2>Best approved leads, not contacted</h2>${leadMini(approved.slice(0, 6)) || `<p class="muted">None yet. Approve leads in the review queue.</p>`}</div>
      <div class="card"><h2>Top leads waiting for review</h2>${leadMini(topNew) || `<p class="muted">Review queue is empty.</p>`}</div>
    </div>`;
  bindLeadLinks(el);
  bindTodo(el);
};
function tile(label, v, href) { return `<div class="tile link" onclick="location.hash='${href}'"><div class="v">${fmtNum(v)}</div><div class="l">${esc(label)}</div></div>`; }
function leadMini(rows) {
  if (!rows.length) return "";
  return `<table class="simple">${rows.map((r) => `<tr><td>${scoreBadge(r)}</td><td><a href="#" data-lead="${esc(r.id)}">${esc(r.company)}</a><div class="small muted clip">${esc(r.fit_reason)}</div></td><td class="small muted">${esc(r.contact_name || "")}</td></tr>`).join("")}</table>`;
}
function bindLeadLinks(el) { $$("[data-lead]", el).forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); openLead(a.dataset.lead); })); }

// ---------- leads table ----------
const PAGE_SIZE = 100;
PAGES.leads = async (el) => {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  if (params.has("stage")) { S.filters.stage = params.get("stage"); history.replaceState(null, "", "#/leads"); }
  if (params.has("tag")) { S.filters.tag = params.get("tag"); history.replaceState(null, "", "#/leads"); }
  const views = await api("views");
  const f = S.filters;
  el.innerHTML = `
    <h1>Leads</h1>
    <p class="sub">Click a row to open it. Select rows to change many at once.</p>
    <div class="toolbar">
      <input type="search" id="f-q" placeholder="Search company, contact, reason, signals…" value="${esc(f.q)}">
      <select id="f-stage"><option value="">All stages</option>${S.state.stages.map((s) => `<option ${f.stage === s ? "selected" : ""}>${s}</option>`).join("")}<option value="approved,contacted,replied,meeting" ${f.stage === "approved,contacted,replied,meeting" ? "selected" : ""}>active pipeline</option></select>
      <label class="row small"><input type="checkbox" id="f-hidec" ${f.hideCandidates ? "checked" : ""}> hide candidates</label>
      <input type="number" id="f-min" placeholder="min score" style="width:100px" value="${esc(f.min_score)}">
      <select id="f-tag"><option value="">Any tag</option>${allTags().map((t) => `<option ${f.tag === t ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
      <label class="row small"><input type="checkbox" id="f-due" ${f.due ? "checked" : ""}> due now</label>
      <button class="ghost" id="f-clear">Clear</button>
      <span class="spacer"></span>
      <select id="views"><option value="">Saved views…</option>${views.map((v) => `<option ${v.name === S.currentView ? "selected" : ""}>${esc(v.name)}</option>`).join("")}</select>
      <button id="view-save">Save view</button><button class="ghost" id="view-del" title="Delete the selected saved view">Delete view</button>
      <button id="add-lead">+ Add lead</button>
    </div>
    <div id="bulk"></div>
    <div id="table"></div>`;
  const apply = () => { S.currentView = ""; const vs = $("#views"); if (vs) vs.value = ""; S.page = 0; savePref("filters", S.filters); drawTable(); };
  $("#f-q").addEventListener("input", (e) => { f.q = e.target.value; apply(); });
  $("#f-stage").addEventListener("change", (e) => { f.stage = e.target.value; apply(); });
  $("#f-hidec").addEventListener("change", (e) => { f.hideCandidates = e.target.checked; apply(); });
  $("#f-min").addEventListener("input", (e) => { f.min_score = e.target.value; apply(); });
  $("#f-tag").addEventListener("change", (e) => { f.tag = e.target.value; apply(); });
  $("#f-due").addEventListener("change", (e) => { f.due = e.target.checked; apply(); });
  $("#f-clear").addEventListener("click", () => { S.currentView = ""; S.filters = { q: "", stage: "", min_score: "", tag: "", due: false, hideCandidates: true }; savePref("filters", S.filters); PAGES.leads(el); });
  $("#views").addEventListener("change", (e) => {
    const v = views.find((x) => x.name === e.target.value);
    if (!v) { S.currentView = ""; return; }
    S.currentView = v.name;
    S.filters = Object.assign({ q: "", stage: "", min_score: "", tag: "", due: false, hideCandidates: true }, v.filters);
    savePref("filters", S.filters);
    PAGES.leads(el);
  });
  $("#view-del").addEventListener("click", async () => {
    const name = $("#views").value;
    if (!name) return toast("Pick a saved view to delete first", true);
    if (!confirm(`Delete the saved view "${name}"?`)) return;
    try { await api("views/delete", { name }); S.currentView = ""; toast("View deleted"); PAGES.leads(el); } catch (e) { fail(e); }
  });
  $("#view-save").addEventListener("click", async () => {
    const name = prompt("Name this view (for example: DACH approved 70+)");
    if (!name) return;
    try { await api("views", { name, filters: S.filters }); S.currentView = name; toast("View saved"); PAGES.leads(el); } catch (e) { fail(e); }
  });
  $("#add-lead").addEventListener("click", () => openNewLead());
  drawTable();
};

function filteredRows() {
  const rows = S.leads.filter((r) => matches(r, S.filters));
  const { key, dir } = S.sort;
  const num = key === "fit_score";
  rows.sort((a, b) => {
    const x = num ? +a[key] : String(a[key] || "").toLowerCase(), y = num ? +b[key] : String(b[key] || "").toLowerCase();
    if (!num && !x && y) return 1;
    if (!num && x && !y) return -1;
    return x < y ? -dir : x > y ? dir : 0;
  });
  return rows;
}

function drawTable() {
  const rows = filteredRows();
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  S.page = Math.min(S.page, pages - 1);
  const slice = rows.slice(S.page * PAGE_SIZE, (S.page + 1) * PAGE_SIZE);
  const t = S.state.today;
  const th = (k, label, cls = "") => `<th data-sort="${k}" class="${cls}">${label}${S.sort.key === k ? (S.sort.dir < 0 ? " ↓" : " ↑") : ""}</th>`;
  const allSel = slice.length && slice.every((r) => S.selected.has(r.id));
  $("#table").innerHTML = rows.length ? `
    <table class="leads">
      <thead><tr><th><input type="checkbox" id="sel-all" ${allSel ? "checked" : ""}></th>${th("fit_score", "Score", "num")}${th("company", "Company")}${th("contact_name", "Contact", "hide-sm")}${th("location", "Location", "hide-sm")}${th("stage", "Stage")}${th("next_action_date", "Next")}<th class="hide-sm">Tags</th></tr></thead>
      <tbody>${slice.map((r) => `
        <tr data-id="${esc(r.id)}" class="${S.selected.has(r.id) ? "sel" : ""}">
          <td><input type="checkbox" class="sel" ${S.selected.has(r.id) ? "checked" : ""}></td>
          <td class="num">${scoreBadge(r)}</td>
          <td><b>${esc(r.company)}</b><div class="small muted clip">${r.fit_reason.startsWith("unverified") ? `<span class="unverified">unverified</span> ` : ""}${esc(r.fit_reason.replace(/^unverified:\s*/, ""))}</div></td>
          <td class="hide-sm">${esc(r.contact_name)}<div class="small muted">${esc(r.contact_role)}</div>${r.contact_email ? `<div class="small">${esc(r.contact_email)}</div>` : ""}</td>
          <td class="hide-sm small">${esc(r.location)}</td>
          <td>${stageBadge(r.stage)}</td>
          <td class="small ${r.next_action_date && r.next_action_date < t && !["won","lost","rejected"].includes(r.stage) ? "overdue" : ""}">${esc(r.next_action_date)}<div class="muted clip" style="max-width:160px">${esc(r.next_action)}</div></td>
          <td class="hide-sm">${tagsHtml(r.tags)}</td>
        </tr>`).join("")}</tbody>
    </table>
    <div class="pager">${fmtNum(rows.length)} leads · page ${S.page + 1} of ${pages}
      <button class="sm" id="pg-prev" ${S.page ? "" : "disabled"}>‹ Prev</button><button class="sm" id="pg-next" ${S.page < pages - 1 ? "" : "disabled"}>Next ›</button>
      <a class="btn sm" href="${exportHref("csv", true)}">Export these (CSV)</a></div>`
    : `<div class="empty">No leads match these filters.</div>`;
  $$("th[data-sort]").forEach((h) => h.addEventListener("click", () => {
    const k = h.dataset.sort;
    S.sort = { key: k, dir: S.sort.key === k ? -S.sort.dir : k === "fit_score" ? -1 : 1 };
    savePref("sort", S.sort);
    drawTable();
  }));
  $("#sel-all")?.addEventListener("change", (e) => { slice.forEach((r) => (e.target.checked ? S.selected.add(r.id) : S.selected.delete(r.id))); drawTable(); });
  $$("#table tbody tr").forEach((tr) => tr.addEventListener("click", (e) => {
    const id = tr.dataset.id;
    if (e.target.classList.contains("sel")) { e.target.checked ? S.selected.add(id) : S.selected.delete(id); tr.classList.toggle("sel", e.target.checked); drawBulk(); return; }
    openLead(id);
  }));
  $("#pg-prev")?.addEventListener("click", () => { S.page--; drawTable(); window.scrollTo(0, 0); });
  $("#pg-next")?.addEventListener("click", () => { S.page++; drawTable(); window.scrollTo(0, 0); });
  drawBulk();
}

function exportHref(fmt, useFilters) {
  const p = new URLSearchParams({ format: fmt });
  if (useFilters) {
    const ids = filteredRows().map((r) => r.id);
    if (ids.length <= 400) p.set("ids", ids.join(","));
    else {
      const f = S.filters;
      const stage = f.stage || (f.hideCandidates ? S.state.stages.filter((x) => x !== "candidate").join(",") : "");
      if (f.q) p.set("q", f.q); if (stage) p.set("stage", stage); if (f.tag) p.set("tag", f.tag); if (f.min_score) p.set("min_score", f.min_score); if (f.due) p.set("due", "1");
    }
  }
  return "/api/export?" + p.toString();
}

function drawBulk() {
  const box = $("#bulk");
  if (!box) return;
  const n = S.selected.size;
  if (!n) { box.innerHTML = ""; return; }
  box.innerHTML = `<div class="bulkbar"><b>${n} selected</b>
    <select id="b-stage"><option value="">Move to stage…</option>${S.state.stages.map((s) => `<option>${s}</option>`).join("")}</select>
    <input id="b-tag" placeholder="tag" style="width:120px"><button id="b-tag-add" class="sm">+ Tag</button><button id="b-tag-rm" class="sm">− Tag</button>
    <input id="b-date" type="date" title="next action date"><button id="b-date-set" class="sm">Set follow-up</button>
    <a class="btn sm" href="/api/export?format=csv&ids=${encodeURIComponent([...S.selected].join(","))}">Export</a>
    <span class="spacer"></span><button class="ghost sm" id="b-clear">Clear selection</button></div>`;
  const go = async (body, msg) => {
    try {
      const res = await api("bulk", Object.assign({ ids: [...S.selected] }, body));
      toast(`${msg}: ${res.updated.length} updated`);
      await loadAll(); drawTable();
    } catch (e) { fail(e); }
  };
  $("#b-stage").addEventListener("change", (e) => e.target.value && go({ stage: e.target.value, note: "bulk change in GUI" }, `Moved to ${e.target.value}`));
  $("#b-tag-add").addEventListener("click", () => $("#b-tag").value && go({ add_tags: [$("#b-tag").value] }, "Tagged"));
  $("#b-tag-rm").addEventListener("click", () => $("#b-tag").value && go({ remove_tags: [$("#b-tag").value] }, "Untagged"));
  $("#b-date-set").addEventListener("click", () => $("#b-date").value && go({ next_action_date: $("#b-date").value, next_action: "Follow up" }, "Follow-up set"));
  $("#b-clear").addEventListener("click", () => { S.selected.clear(); drawTable(); });
}

// ---------- lead drawer ----------
async function openLead(id) {
  const d = $("#drawer");
  d.hidden = false;
  d.innerHTML = `<div class="loading">Loading…</div>`;
  let data;
  try { data = await api("lead?id=" + encodeURIComponent(id)); } catch (e) { d.hidden = true; return fail(e); }
  const r = data.lead;
  const editable = ["company", "website", "industry", "size", "location", "contact_name", "contact_role", "contact_email", "contact_linkedin", "fit_score"];
  d.innerHTML = `
    <button class="ghost close" id="d-close" title="Close (Esc)">✕</button>
    <div class="row">${scoreBadge(r)} ${stageBadge(r.stage)} <span class="muted small">${esc(r.id)} · added ${esc(r.added_on)} · updated ${esc(r.updated_on)}</span></div>
    <h1 style="margin-top:8px">${esc(r.company)}</h1>
    <p class="sub">${r.website ? link(r.website) : ""} ${esc([r.industry, r.size, r.location].filter(Boolean).join(" · "))}</p>
    ${r.stage === "candidate" ? `<div class="callout warn">Unverified candidate: harvested from a list and not researched yet. Verify before contacting.</div>` : ""}
    <div class="row" style="margin-bottom:14px">
      ${S.state.stages.map((s) => `<button class="sm ${s === r.stage ? "primary" : ""}" data-stage="${s}">${s.replace("_", " ")}</button>`).join("")}
    </div>
    <dl class="kv">
      <dt>Why</dt><dd>${esc(r.fit_reason)}</dd>
      <dt>Signals</dt><dd>${splitList(r.signals).map(esc).join("<br>") || "<span class=muted>none</span>"}</dd>
      <dt>Contact</dt><dd>${esc(r.contact_name) || "<span class=muted>no named contact</span>"} ${r.contact_role ? `<span class="muted">(${esc(r.contact_role)})</span>` : ""}
        ${r.contact_email ? `<br><a href="mailto:${esc(r.contact_email)}">${esc(r.contact_email)}</a>` : ""}${r.contact_linkedin ? `<br>${link(r.contact_linkedin, "LinkedIn")}` : ""}</dd>
      <dt>Sources</dt><dd>${splitList(r.sources).map((s) => link(s)).join("<br>")}</dd>
      <dt>Tags</dt><dd><span id="d-tags">${splitList(r.tags).map((t) => `<span class="tag">${esc(t)}<button data-rmtag="${esc(t)}" title="remove">✕</button></span>`).join("")}</span>
        <input id="d-newtag" placeholder="add tag" list="taglist" style="width:120px;padding:2px 6px"><datalist id="taglist">${allTags().map((t) => `<option>${esc(t)}</option>`).join("")}</datalist></dd>
    </dl>
    <div class="card" style="margin-bottom:14px">
      <h2>Next action</h2>
      <div class="row"><input id="d-na" value="${esc(r.next_action)}" placeholder="e.g. Send first email" style="flex:1"><input id="d-nd" type="date" value="${esc(r.next_action_date)}">
      <button class="primary" id="d-na-save">Save</button></div>
      <div class="row small" style="margin-top:6px">Snooze: <button class="sm" data-snooze="1">+1 day</button><button class="sm" data-snooze="3">+3 days</button><button class="sm" data-snooze="7">+1 week</button><button class="sm" data-snooze="30">+1 month</button><button class="sm ghost" id="d-na-clear">Clear</button></div>
    </div>
    <div class="card" style="margin-bottom:14px">
      <h2>Add a note</h2>
      <textarea id="d-note" rows="2" placeholder="Called, left voicemail…"></textarea>
      <div class="row end" style="margin-top:6px"><button id="d-note-save">Add note</button></div>
      <h3>Activity and research</h3>
      <div class="notes">${esc(data.notes || "No notes yet.")}</div>
    </div>
    <div class="card" style="margin-bottom:14px">
      <div class="row"><h2 style="margin:0">Outreach</h2><span class="spacer"></span>
        <a class="btn sm" href="#/outreach?id=${encodeURIComponent(r.id)}" id="d-tpl">Draft from template</a>
        ${S.state.claude ? `<button class="sm" data-run="draft-outreach">AI draft (/draft-outreach)</button>` : ""}</div>
      ${data.outreach ? `<div class="notes" style="margin-top:10px">${esc(data.outreach)}</div>` : `<p class="muted">No drafts yet.</p>`}
    </div>
    ${S.state.claude ? `<div class="card" style="margin-bottom:14px"><h2>Ask the agent</h2><div class="row">
      ${r.stage === "candidate" ? `<button data-run="verify-candidates">Verify this candidate</button>` : ""}
      <button data-run="enrich">Enrich (people, news, re-score)</button><button data-run="more-like">Find lookalikes</button></div></div>` : ""}
    <details class="card"><summary><b>Edit fields</b></summary>
      <div class="fields" style="margin-top:10px">${editable.map((c) => `<label class="f">${c.replace(/_/g, " ")}<input data-field="${c}" value="${esc(r[c])}"></label>`).join("")}
        <label class="f wide">fit reason<textarea data-field="fit_reason" rows="2">${esc(r.fit_reason)}</textarea></label>
        <label class="f wide">signals (separate with ;)<textarea data-field="signals" rows="2">${esc(r.signals)}</textarea></label>
        <label class="f wide">sources (separate with ;)<textarea data-field="sources" rows="2">${esc(r.sources)}</textarea></label>
        <label class="f wide">notes column<textarea data-field="notes" rows="2">${esc(r.notes)}</textarea></label></div>
      <div class="row end" style="margin-top:8px"><button class="primary" id="d-fields-save">Save changes</button></div>
      <p class="small muted">Every fact needs a source URL. Never guess contact details: blank is correct when it isn't public.</p>
    </details>`;
  const upd = async (body, msg) => {
    try {
      const res = await api("lead/update", Object.assign({ id: r.id }, body));
      toast(res.changes.length ? msg || res.changes.join("; ") : "No change");
      await loadAll();
      if ($("#table")) drawTable(); else if (location.hash.startsWith("#/review")) {} else route();
      openLead(r.id);
    } catch (e) { fail(e); }
  };
  $("#d-close").addEventListener("click", closeDrawer);
  $$("[data-stage]", d).forEach((b) => b.addEventListener("click", () => b.dataset.stage !== r.stage && upd({ stage: b.dataset.stage, note: "changed in GUI" })));
  $$("[data-rmtag]", d).forEach((b) => b.addEventListener("click", () => upd({ remove_tags: [b.dataset.rmtag] })));
  $("#d-newtag").addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.value.trim()) upd({ add_tags: [e.target.value.trim()] }); });
  $("#d-na-save").addEventListener("click", () => upd({ next_action: $("#d-na").value, next_action_date: $("#d-nd").value }));
  $("#d-na-clear").addEventListener("click", () => upd({ next_action: "", next_action_date: "" }));
  $$("[data-snooze]", d).forEach((b) => b.addEventListener("click", () => upd({ next_action: r.next_action || "Follow up", next_action_date: addDays(+b.dataset.snooze) })));
  $("#d-note-save").addEventListener("click", () => $("#d-note").value.trim() && upd({ note: $("#d-note").value }, "Note added"));
  $("#d-fields-save").addEventListener("click", () => {
    const fields = {};
    $$("[data-field]", d).forEach((i) => { if (i.value !== (r[i.dataset.field] || "")) fields[i.dataset.field] = i.value; });
    if (!Object.keys(fields).length) return toast("No change");
    if ("sources" in fields && !fields.sources.trim()) return toast("A lead needs at least one source URL", true);
    upd({ fields, note: "edited in GUI" });
  });
  $("#d-tpl").addEventListener("click", () => closeDrawer());
  $$("[data-run]", d).forEach((b) => b.addEventListener("click", () => {
    const cmd = b.dataset.run;
    const args = cmd === "verify-candidates" ? `1 ${r.id}` : r.id;
    startRun(cmd, args);
  }));
}
function closeDrawer() { $("#drawer").hidden = true; }
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#drawer").hidden) closeDrawer(); });

function openNewLead() {
  const d = $("#drawer");
  d.hidden = false;
  const cols = ["company", "website", "industry", "size", "location", "contact_name", "contact_role", "contact_email", "contact_linkedin", "fit_score"];
  d.innerHTML = `<button class="ghost close" id="d-close">✕</button><h1>Add a lead</h1>
    <p class="sub">For leads you found yourself. The agent's own finds come in through Run agent.</p>
    <div class="fields">${cols.map((c) => `<label class="f">${c.replace(/_/g, " ")}${c === "company" ? " *" : ""}<input data-field="${c}"></label>`).join("")}
      <label class="f">stage<select data-field="stage">${S.state.stages.map((s) => `<option ${s === "new" ? "selected" : ""}>${s}</option>`).join("")}</select></label>
      <label class="f">tags<input data-field="tags" placeholder="a; b"></label>
      <label class="f wide">fit reason<input data-field="fit_reason"></label>
      <label class="f wide">signals (separate with ;)<input data-field="signals"></label>
      <label class="f wide">sources * (URLs, separate with ;)<input data-field="sources"></label>
      <label class="f wide">research notes<textarea data-field="research" rows="3"></textarea></label></div>
    <div class="row end" style="margin-top:10px"><button class="primary" id="n-save">Add lead</button></div>`;
  $("#d-close").addEventListener("click", closeDrawer);
  $("#n-save").addEventListener("click", async () => {
    const lead = {};
    $$("[data-field]", d).forEach((i) => (lead[i.dataset.field] = i.value.trim()));
    lead.signals = splitList(lead.signals); lead.sources = splitList(lead.sources);
    try {
      const res = await api("lead/add", { lead });
      if (res.added.length) { toast(`Added ${res.added[0]}`); await loadAll(); route(); openLead(res.added[0]); }
      else toast(`Not added: ${res.skipped.map((s) => s[1]).join(", ")}`, true);
    } catch (e) { fail(e); }
  });
}

// ---------- board ----------
PAGES.board = async (el) => {
  const stages = (S.boardCandidates ? ["candidate"] : []).concat(["new", "approved", "contacted", "replied", "meeting", "won", "lost", "not_now"]);
  const LIMIT = 40;
  el.innerHTML = `<h1>Pipeline board</h1><p class="sub">Drag a card to another column to change its stage. Each column shows the ${LIMIT} highest-scoring leads.</p>
    <div class="toolbar"><label class="row small"><input type="checkbox" id="b-cand" ${S.boardCandidates ? "checked" : ""}> show unverified candidates</label>
    <input type="search" id="b-q" placeholder="Filter cards…"></div>
    <div class="board" id="board"></div>`;
  const draw = () => {
    const q = $("#b-q").value.toLowerCase();
    $("#board").innerHTML = stages.map((s) => {
      const rows = S.leads.filter((r) => r.stage === s && (!q || Object.values(r).join(" ").toLowerCase().includes(q))).sort((a, b) => b.fit_score - a.fit_score);
      return `<div class="col" data-col="${s}"><h4><span>${s.replace("_", " ")}</span><span class="muted">${fmtNum(rows.length)}</span></h4>
        ${rows.slice(0, LIMIT).map((r) => `<div class="kcard" draggable="true" data-id="${esc(r.id)}"><div class="t"><span>${esc(r.company)}</span>${scoreBadge(r)}</div>
          <div class="m">${esc(r.contact_name || r.location || "")}</div>${r.next_action_date ? `<div class="m ${r.next_action_date < S.state.today ? "overdue" : ""}">${esc(r.next_action_date)} ${esc(r.next_action)}</div>` : ""}</div>`).join("")}
        ${rows.length > LIMIT ? `<a class="small" href="#/leads?stage=${s}">+${fmtNum(rows.length - LIMIT)} more</a>` : ""}</div>`;
    }).join("");
    $$(".kcard").forEach((c) => {
      c.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", c.dataset.id));
      c.addEventListener("click", () => openLead(c.dataset.id));
    });
    $$(".col").forEach((col) => {
      col.addEventListener("dragover", (e) => { e.preventDefault(); col.classList.add("over"); });
      col.addEventListener("dragleave", () => col.classList.remove("over"));
      col.addEventListener("drop", async (e) => {
        e.preventDefault(); col.classList.remove("over");
        const id = e.dataTransfer.getData("text/plain"), stage = col.dataset.col;
        if (!id || S.byId[id]?.stage === stage) return;
        try { await api("lead/update", { id, stage, note: "moved on board" }); toast(`${S.byId[id].company} → ${stage}`); await loadAll(); draw(); } catch (err) { fail(err); }
      });
    });
  };
  $("#b-cand").addEventListener("change", (e) => { S.boardCandidates = e.target.checked; PAGES.board(el); });
  $("#b-q").addEventListener("input", draw);
  draw();
};

// ---------- review queue ----------
PAGES.review = async (el) => {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const mode = params.get("stage") === "candidate" ? "candidate" : "new";
  const queue = S.leads.filter((r) => r.stage === mode).sort((a, b) => b.fit_score - a.fit_score);
  const skipped = new Set();
  let i = 0;
  const draw = () => {
    while (i < queue.length && (skipped.has(queue[i].id) || S.byId[queue[i].id]?.stage !== mode)) i++;
    const r = queue[i];
    el.innerHTML = `<div class="review">
      <div class="row"><h1>Review queue</h1><span class="spacer"></span>
        <a class="btn sm ${mode === "new" ? "primary" : ""}" href="#/review">Researched leads</a><a class="btn sm ${mode === "candidate" ? "primary" : ""}" href="#/review?stage=candidate">Unverified candidates</a></div>
      <p class="sub">${mode === "new" ? "Approve or reject researched leads, best first. Rejection reasons can teach your ICP." : "Triage harvested candidates: keep the promising ones for verification, reject the obvious misses."}
        Keys: <span class="kbd">A</span> approve <span class="kbd">R</span> reject <span class="kbd">L</span> later <span class="kbd">S</span> skip</p>
      ${r ? `<div class="card">
        <div class="row">${scoreBadge(r)} <span class="muted small">${queue.length - i - [...skipped].length > 0 ? fmtNum(queue.filter((x) => S.byId[x.id]?.stage === mode && !skipped.has(x.id)).length) : 0} left</span></div>
        <h2>${esc(r.company)}</h2>
        <div class="muted">${r.website ? link(r.website) : ""} ${esc([r.industry, r.size, r.location].filter(Boolean).join(" · "))}</div>
        <dl class="kv">
          <dt>Why</dt><dd>${esc(r.fit_reason)}</dd>
          <dt>Signals</dt><dd>${splitList(r.signals).map(esc).join("<br>") || "<span class=muted>none</span>"}</dd>
          <dt>Contact</dt><dd>${esc(r.contact_name) || "<span class=muted>none found</span>"} ${r.contact_role ? `(${esc(r.contact_role)})` : ""} ${r.contact_email ? "· " + esc(r.contact_email) : ""} ${r.contact_linkedin ? "· " + link(r.contact_linkedin, "LinkedIn") : ""}</dd>
          <dt>Sources</dt><dd>${splitList(r.sources).map((s) => link(s)).join("<br>")}</dd>
        </dl>
        <label class="f">Reason (optional, saved to the lead's notes)<input id="rv-reason" placeholder="e.g. too big, wrong country, agency not product company"></label>
        <label class="row small" style="margin-top:6px"><input type="checkbox" id="rv-learn"> also add this reason to the ICP's learned disqualifiers</label>
        <div class="row" style="margin-top:12px">
          ${mode === "new" ? `<button class="good" data-act="approved">Approve (A)</button>` : `<button class="good" data-act="keep">Keep for verification (A)</button>`}
          <button class="bad" data-act="rejected">Reject (R)</button><button data-act="not_now">Later (L)</button><button class="ghost" data-act="skip">Skip (S)</button>
          <span class="spacer"></span><button class="ghost" id="rv-open">Open full record</button></div>
      </div>` : `<div class="empty">Nothing left to review here. ${mode === "new" ? `<a href="#/run?cmd=find-leads">Find more leads</a> or <a href="#/review?stage=candidate">triage candidates</a>.` : `<a href="#/run?cmd=verify-candidates">Verify candidates</a>.`}</div>`}
    </div>`;
    if (!r) return;
    $$("[data-act]", el).forEach((b) => b.addEventListener("click", () => act(b.dataset.act)));
    $("#rv-open").addEventListener("click", () => openLead(r.id));
  };
  const act = async (a) => {
    const r = queue[i];
    if (!r) return;
    if (a === "skip") { skipped.add(r.id); return draw(); }
    if (a === "keep") { try { await api("lead/update", { id: r.id, add_tags: ["verify-next"], note: "kept in candidate triage" }); } catch (e) { return fail(e); } skipped.add(r.id); toast("Tagged verify-next"); await loadAll(); return draw(); }
    const reason = $("#rv-reason").value.trim();
    try {
      await api("lead/update", { id: r.id, stage: a, note: reason || (a === "approved" ? "approved in review" : a === "rejected" ? "rejected in review" : "later") });
      if (a === "rejected" && reason && $("#rv-learn").checked) {
        const res = await api("icp/learn", { rule: reason, id: r.id });
        toast(res.added ? "Rejected, and the ICP learned: " + reason : "Rejected (rule already in ICP)");
      } else toast(`${r.company}: ${a.replace("_", " ")}`);
      await loadAll();
      draw();
    } catch (e) { fail(e); }
  };
  draw();
  keyHandler = (e) => {
    if (!location.hash.startsWith("#/review") || ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) || !$("#drawer").hidden) return;
    const map = { a: mode === "new" ? "approved" : "keep", r: "rejected", l: "not_now", s: "skip" };
    if (map[e.key.toLowerCase()]) { e.preventDefault(); act(map[e.key.toLowerCase()]); }
  };
};
let keyHandler = null;
document.addEventListener("keydown", (e) => keyHandler && keyHandler(e));

// ---------- follow-ups ----------
PAGES.followups = async (el) => {
  const days = 14;
  const b = await api("due?days=" + days);
  el.innerHTML = `<div class="row"><h1>Follow-ups</h1><span class="spacer"></span>
      <a class="btn" href="/api/export?format=ics" title="Import into Google Calendar, Outlook or Apple Calendar">Download calendar (.ics)</a></div>
    <p class="sub">Next actions on open leads. Snooze pushes the date out; Done clears it and logs a note.</p>
    <div class="grid g2">
      <div class="card"><h2>Overdue <span class="badge warn">${b.overdue.length}</span></h2>${todoList(b.overdue) || `<p class="muted">Nothing overdue.</p>`}</div>
      <div class="card"><h2>Due today <span class="badge">${b.today.length}</span></h2>${todoList(b.today) || `<p class="muted">Nothing due today.</p>`}</div>
      <div class="card"><h2>Next ${days} days <span class="badge">${b.soon.length}</span></h2>${todoList(b.soon) || `<p class="muted">Nothing scheduled.</p>`}</div>
      <div class="card"><h2>Active, no follow-up date <span class="badge">${b.no_date.length}</span></h2>${todoList(b.no_date.slice(0, 30)) || `<p class="muted">Every active lead has a date.</p>`}</div>
    </div>`;
  bindTodo(el);
};
function todoList(rows, compact) {
  if (!rows.length) return "";
  const t = S.state.today;
  return `<div class="todo">${rows.map((r) => `<div class="todo-item" data-id="${esc(r.id)}">
    <div class="main" data-open><div class="t">${esc(r.company)} ${stageBadge(r.stage)}</div>
    <div class="m"><span class="${r.next_action_date && r.next_action_date < t ? "overdue" : ""}">${esc(r.next_action_date || "no date")}</span> · ${esc(r.next_action || "no next action")}${r.contact_name ? " · " + esc(r.contact_name) : ""}</div></div>
    ${compact ? "" : `<button class="sm" data-snz="3">+3d</button><button class="sm" data-snz="7">+1w</button>`}<button class="sm" data-done>Done</button></div>`).join("")}</div>`;
}
function bindTodo(el) {
  $$(".todo-item", el).forEach((it) => {
    const id = it.dataset.id, r = S.byId[id];
    $("[data-open]", it).addEventListener("click", () => openLead(id));
    $$("[data-snz]", it).forEach((b) => b.addEventListener("click", async () => {
      try { await api("lead/update", { id, next_action: r.next_action || "Follow up", next_action_date: addDays(+b.dataset.snz) }); toast("Snoozed"); await refresh(); } catch (e) { fail(e); }
    }));
    $("[data-done]", it).addEventListener("click", async () => {
      const next = prompt(`Done: "${r.next_action || "follow up"}" for ${r.company}.\nWhat's the next action? (leave empty for none)`, "");
      if (next === null) return;
      let date = "";
      if (next) { date = prompt("When? (YYYY-MM-DD)", addDays(4)) || ""; }
      try { await api("lead/update", { id, note: `done: ${r.next_action || "follow up"}`, next_action: next, next_action_date: date }); toast("Logged"); await refresh(); } catch (e) { fail(e); }
    });
  });
}

// ---------- outreach ----------
PAGES.outreach = async (el) => {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const templates = await api("templates");
  let leadId = params.get("id") || "";
  let current = templates[0]?.name || "";
  const candidates = S.leads.filter((r) => ["approved", "new", "contacted", "replied", "meeting"].includes(r.stage)).sort((a, b) => b.fit_score - a.fit_score);
  if (!leadId && candidates.length) leadId = candidates[0].id;
  el.innerHTML = `<h1>Outreach</h1>
    <p class="sub">Fill a template for a lead, edit it, and save it as a draft in <code>outreach/${esc(S.state.product)}/</code>. Nothing is sent: you copy it and send it yourself.
    ${S.state.claude ? `For a fully researched, personalised draft use <b>AI draft</b>, which runs /draft-outreach.` : ""}</p>
    <div class="grid g2">
      <div class="card">
        <h2>1. Pick a lead and a template</h2>
        <label class="f">Lead<select id="o-lead">${candidates.map((r) => `<option value="${esc(r.id)}" ${r.id === leadId ? "selected" : ""}>${esc(r.fit_score)} · ${esc(r.company)} (${esc(r.stage)})</option>`).join("")}
          ${leadId && !candidates.find((r) => r.id === leadId) && S.byId[leadId] ? `<option value="${esc(leadId)}" selected>${esc(S.byId[leadId].company)}</option>` : ""}</select></label>
        <label class="f" style="margin-top:8px">Template<select id="o-tpl">${templates.map((t) => `<option ${t.name === current ? "selected" : ""}>${esc(t.name)}</option>`).join("")}</select></label>
        <div class="row" style="margin-top:10px"><button class="primary" id="o-render">Fill template</button>${S.state.claude ? `<button id="o-ai">AI draft (/draft-outreach)</button>` : ""}</div>
        <h3>Template text</h3>
        <textarea id="o-tpl-text" class="mono" rows="14"></textarea>
        <div class="row" style="margin-top:6px"><button class="sm" id="o-tpl-save">Save as product template</button><button class="sm ghost" id="o-tpl-del">Delete product template</button>
          <span class="small muted">Fields: {{greeting}} {{first_name}} {{company}} {{hook}} {{signals}} {{fit_reason}} {{source}} {{industry}} {{location}} {{contact_role}} {{product}} {{sender}}</span></div>
      </div>
      <div class="card">
        <h2>2. Edit and save the draft</h2>
        <div id="o-missing"></div>
        <textarea id="o-out" class="mono" rows="22" placeholder="The filled template appears here."></textarea>
        <div class="row" style="margin-top:8px"><button class="primary" id="o-save">Save draft to lead</button><button id="o-copy">Copy</button><a class="btn" id="o-mail" href="#">Open in email app</a></div>
        <p class="small muted">Saving logs "outreach drafted" on the lead and sets the next action to "Send first message". Move it to <b>contacted</b> after you send it.</p>
      </div>
    </div>`;
  const tplText = () => templates.find((t) => t.name === $("#o-tpl").value)?.text || "";
  $("#o-tpl-text").value = tplText();
  $("#o-tpl").addEventListener("change", () => ($("#o-tpl-text").value = tplText()));
  const updMail = () => {
    const r = S.byId[$("#o-lead").value];
    const text = $("#o-out").value;
    const m = text.match(/^Subject:\s*(.+)$/m);
    const body = text.replace(/^#.*$/gm, "").replace(/^Subject:.*$/m, "").trim();
    $("#o-mail").href = `mailto:${encodeURIComponent(r?.contact_email || "")}?subject=${encodeURIComponent(m ? m[1] : "")}&body=${encodeURIComponent(body)}`;
  };
  $("#o-render").addEventListener("click", async () => {
    try {
      const res = await api("render", { template: $("#o-tpl").value, id: $("#o-lead").value });
      $("#o-out").value = res.text;
      $("#o-missing").innerHTML = res.missing.length ? `<div class="callout warn">Fill these by hand: ${res.missing.map((m) => `<code>[${esc(m)}]</code>`).join(" ")}</div>` : "";
      updMail();
    } catch (e) { fail(e); }
  });
  $("#o-out").addEventListener("input", updMail);
  $("#o-ai")?.addEventListener("click", () => startRun("draft-outreach", $("#o-lead").value));
  $("#o-tpl-save").addEventListener("click", async () => {
    const name = prompt("Template name", $("#o-tpl").value);
    if (!name) return;
    try { await api("templates", { name, text: $("#o-tpl-text").value }); toast("Template saved for this product"); PAGES.outreach(el); } catch (e) { fail(e); }
  });
  $("#o-tpl-del").addEventListener("click", async () => {
    try { await api("templates/delete", { name: $("#o-tpl").value }); toast("Deleted"); PAGES.outreach(el); } catch (e) { fail(e); }
  });
  $("#o-copy").addEventListener("click", async () => { try { await navigator.clipboard.writeText($("#o-out").value); toast("Copied"); } catch { $("#o-out").select(); document.execCommand("copy"); toast("Copied"); } });
  $("#o-save").addEventListener("click", async () => {
    if (!$("#o-out").value.trim()) return toast("Fill the template first", true);
    try { const res = await api("outreach/save", { id: $("#o-lead").value, text: $("#o-out").value, label: $("#o-tpl").value }); toast("Saved to " + res.path); await loadAll(); } catch (e) { fail(e); }
  });
  if (params.get("id")) $("#o-render").click();
};

// ---------- analytics ----------
PAGES.analytics = async (el) => {
  const a = await api("analytics");
  const maxF = Math.max(1, ...a.funnel.map((f) => f.count));
  const bars = (items, max) => `<div class="bars">${items.map(([l, v, extra]) => `<div class="bar-row" title="${esc(l)}: ${fmtNum(v)}"><span class="lbl">${esc(l)}</span><div class="bar-track"><div class="bar-fill" style="width:${(100 * v) / Math.max(1, max)}%"></div></div><span class="val">${fmtNum(v)}${extra ? ` <span class="muted">${esc(extra)}</span>` : ""}</span></div>`).join("")}</div>`;
  const cols = (items) => { const m = Math.max(1, ...items.map((x) => x[1])); return `<div class="cols">${items.map(([l, v]) => `<div class="c" style="height:${(100 * v) / m}%" title="${esc(l)}: ${fmtNum(v)}"></div>`).join("")}</div><div class="cols-x">${items.map(([l]) => `<span>${esc(l)}</span>`).join("")}</div>`; };
  const tbl = (items, h) => items.length ? `<table class="simple"><tr><th>${h}</th><th class="num">Leads</th></tr>${items.map(([k, v]) => `<tr><td class="clip">${esc(k)}</td><td class="num">${fmtNum(v)}</td></tr>`).join("")}</table>` : `<p class="muted">No data.</p>`;
  const c = a.contactability;
  el.innerHTML = `<h1>Analytics</h1><p class="sub">${esc(a.product)}: ${fmtNum(a.total)} leads, ${fmtNum(a.searches)} searches logged.</p>
    <div class="tiles">
      <div class="tile"><div class="v">${fmtNum(c.researched)}</div><div class="l">Researched leads</div></div>
      <div class="tile"><div class="v">${a.avg_score}</div><div class="l">Average fit score (researched)</div></div>
      <div class="tile"><div class="v">${a.reply_rate}%</div><div class="l">Reply rate (of contacted)</div></div>
      <div class="tile"><div class="v">${a.win_rate == null ? "–" : a.win_rate + "%"}</div><div class="l">Win rate (won vs lost)</div></div>
      <div class="tile"><div class="v">${c.email}%</div><div class="l">Researched with an email</div></div>
      <div class="tile"><div class="v">${c.name}%</div><div class="l">Researched with a named contact</div></div>
    </div>
    <div class="grid g2">
      <div class="card"><h2>Funnel: leads that reached each stage</h2>${bars(a.funnel.map((f) => [f.stage, f.count, f.rate != null ? `${f.rate}%` : ""]), maxF)}
        <p class="small muted">Percent is of the stage before. Rejected and not-now leads count as reaching "new"; lost counts as reaching "contacted".</p></div>
      <div class="card"><h2>Leads added per week</h2>${cols(a.added_per_week.map((w) => [w.week.slice(5), w.count]))}<p class="small muted">Last 12 weeks, by Monday of the week.</p></div>
      <div class="card"><h2>Fit score spread: researched leads</h2>${bars(a.score_researched.map((h) => [h.bucket, h.count]), Math.max(...a.score_researched.map((h) => h.count)))}</div>
      <div class="card"><h2>Fit score spread: unverified candidates</h2>${bars(a.score_candidates.map((h) => [h.bucket, h.count]), Math.max(...a.score_candidates.map((h) => h.count)))}</div>
      <div class="card"><h2>Where leads come from</h2>${tbl(a.top_sources, "Source site")}</div>
      <div class="card"><h2>Locations</h2>${tbl(a.top_locations, "Country / region")}</div>
      <div class="card"><h2>Industries</h2>${tbl(a.top_industries, "Industry")}</div>
      <div class="card"><h2>Tags</h2>${tbl(a.top_tags, "Tag")}</div>
    </div>`;
};

// ---------- run agent ----------
let pollTimer = null;
function stopPolling() { clearTimeout(pollTimer); pollTimer = null; }
async function startRun(command, args) {
  try {
    const job = await api("jobs", { command, args });
    toast(`Started /${command}`);
    closeDrawer();
    location.hash = "#/run?job=" + job.id;
    S.state.running++;
    renderChrome();
  } catch (e) { fail(e); }
}
PAGES.run = async (el) => {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const st = S.state;
  const jobs = await api("jobs");
  const pre = params.get("cmd");
  el.innerHTML = `<h1>Run agent</h1>
    <p class="sub">Starts the agent's commands through your local Claude Code (<code>claude -p</code>), using your Claude Code login. No API keys. Results land in your lead list as the agent works.</p>
    ${st.claude ? "" : `<div class="callout warn">Claude Code CLI not found on this computer, so commands can't run from here. Install Claude Code, or start the GUI with <code>LEAD_AGENT_CLAUDE=/path/to/claude</code>. You can still run the commands in a Claude Code terminal.</div>`}
    <div class="grid g2">
      <div class="card"><h2>Commands</h2><div class="grid">
        ${st.commands.map((c) => `<div class="cmd"><div><b>/${esc(c.name)}</b> <span class="muted small">${esc(c.description)}</span></div>
          <div class="row">${c.name === "setup-product" ? `<div class="small muted">Writes into the selected product (${esc(st.product)}). For a new product, pick "+ New product…" in the sidebar first.</div>` : ""}<input data-args="${esc(c.name)}" placeholder="${esc(c.hint)}" style="flex:1" value="${pre === c.name ? (c.name === "verify-candidates" ? "20" : c.name === "find-leads" ? "10" : "") : ""}"><button class="${pre === c.name ? "primary" : ""}" data-go="${esc(c.name)}" ${st.claude ? "" : "disabled"}>Run</button></div></div>`).join("")}
        <div class="cmd"><div><b>Ask the agent anything</b> <span class="muted small">for example: "find 10 more Sportsbox-certified coaches in the UK"</span></div>
          <textarea id="ask" rows="2"></textarea><div class="row end"><button data-go="ask" ${st.claude ? "" : "disabled"}>Ask</button></div></div>
      </div></div>
      <div class="card"><h2>Runs</h2><div id="jobs"></div>
        <div id="joblog" style="margin-top:14px"></div>
      </div>
    </div>`;
  $$("[data-go]", el).forEach((b) => b.addEventListener("click", () => {
    const c = b.dataset.go;
    const args = c === "ask" ? $("#ask").value : $(`[data-args="${c}"]`).value;
    startRun(c, args);
  }));
  drawJobs(jobs);
  const jobId = params.get("job") || (jobs.find((j) => j.status === "running") || {}).id;
  if (jobId) showJob(jobId);
};
async function drawJobs(jobs) {
  jobs = jobs || (await api("jobs"));
  const box = $("#jobs");
  if (!box) return;
  box.innerHTML = jobs.length ? `<table class="simple">${jobs.map((j) => `<tr><td><a href="#/run?job=${j.id}">/${esc(j.command)} ${esc(j.args).slice(0, 40)}</a><div class="small muted">${esc(j.product)} · ${esc(j.started)}${j.cost ? ` · $${(+j.cost).toFixed(2)}` : ""}</div></td><td><span class="status ${j.status}">${j.status}</span></td></tr>`).join("")}</table>` : `<p class="muted">No runs yet in this session. Logs are also saved to <code>data/&lt;product&gt;/runs/</code>.</p>`;
}
async function showJob(id) {
  let since = 0, lines = [];
  const box = $("#joblog");
  if (!box) return;
  box.innerHTML = `<div class="row"><h3 style="margin:0" id="jl-title">Run</h3><span id="jl-status"></span><span class="spacer"></span><button class="sm" id="jl-cancel">Stop</button></div><div class="log" id="jl"></div>`;
  $("#jl-cancel").addEventListener("click", async () => { try { await api("job/cancel", { id }); } catch (e) { fail(e); } });
  const tick = async () => {
    let j;
    try { j = await api(`job?id=${id}&since=${since}`); } catch (e) { box.innerHTML = `<p class="muted">Run not found (the GUI was restarted). Saved logs are in data/&lt;product&gt;/runs/.</p>`; return; }
    if (!$("#jl")) return;
    since += j.new_lines.length;
    lines = lines.concat(j.new_lines);
    $("#jl-title").textContent = `/${j.command} ${j.args}`;
    $("#jl-status").innerHTML = `<span class="status ${j.status}">${j.status}</span>`;
    $("#jl-cancel").hidden = j.status !== "running";
    const log = $("#jl");
    const atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 30;
    log.innerHTML = lines.map((l) => `<div class="${l.startsWith("→") ? "tool" : l.startsWith("✓") ? "ok" : l.startsWith("✗") ? "err" : ""}">${esc(l) || "&nbsp;"}</div>`).join("");
    if (atBottom) log.scrollTop = log.scrollHeight;
    if (j.status === "running") pollTimer = setTimeout(tick, 1500);
    else { await loadAll(); drawJobs(); }
  };
  tick();
}

// ---------- product & data ----------
PAGES.data = async (el) => {
  const [prod, icp, searches, dupes] = await Promise.all([api("doc?name=product.md"), api("doc?name=icp.md"), api("doc?name=searches.log"), api("dupes")]);
  const fmts = [["csv", "All columns (CSV)"], ["hubspot", "HubSpot import (CSV)"], ["pipedrive", "Pipedrive import (CSV)"], ["json", "JSON"], ["ics", "Follow-up calendar (.ics)"]];
  el.innerHTML = `<h1>Product &amp; data</h1><p class="sub">Product <b>${esc(S.state.product)}</b>. Files live in <code>data/${esc(S.state.product)}/</code>.</p>
    <div class="grid g2">
      <div class="card"><h2>Export</h2>
        <div class="row"><select id="x-stage"><option value="">All stages</option>${S.state.stages.map((s) => `<option>${s}</option>`).join("")}<option value="new,approved,contacted,replied,meeting,won">researched only (no candidates)</option></select>
        <input id="x-min" type="number" placeholder="min score" style="width:100px"><select id="x-tag"><option value="">Any tag</option>${allTags().map((t) => `<option>${esc(t)}</option>`).join("")}</select></div>
        <div class="row" style="margin-top:10px">${fmts.map(([f, l]) => `<button data-fmt="${f}">${l}</button>`).join("")}</div>
        <p class="small muted">CSV opens in Google Sheets (File → Import). HubSpot and Pipedrive files use their import column names.</p></div>
      <div class="card"><h2>Import a CSV</h2>
        <p class="small muted">Headers like Company, Website, Email, Title, LinkedIn, Location are mapped automatically. Duplicates (same website or id) are skipped.</p>
        <input type="file" id="i-file" accept=".csv,text/csv">
        <div class="fields" style="margin-top:8px">
          <label class="f">Import as stage<select id="i-stage">${S.state.stages.map((s) => `<option ${s === "candidate" ? "selected" : ""}>${s}</option>`).join("")}</select></label>
          <label class="f">Tag every row<input id="i-tag" placeholder="e.g. trade-show-2026"></label>
          <label class="f wide">Source for rows without one (URL or where the list came from) <input id="i-src" placeholder="https://… or 'Event attendee list, Nov 2026'"></label></div>
        <div class="row" style="margin-top:8px"><button id="i-preview">Preview</button><button class="primary" id="i-go">Import</button></div>
        <div id="i-out" class="small" style="margin-top:8px"></div></div>
      <div class="card"><h2>Likely duplicates <span class="badge">${dupes.length}</span></h2>
        ${dupes.length ? `<table class="simple">${dupes.slice(0, 40).map((g) => `<tr><td class="small muted">${esc(g.reason)}</td><td>${g.ids.map((id) => `<a href="#" data-lead="${esc(id)}">${esc(S.byId[id]?.company || id)}</a> <span class="muted small">(${esc(S.byId[id]?.stage || "")}, ${esc(S.byId[id]?.fit_score || "")})</span>`).join("<br>")}</td>
          <td>${g.ids.length === 2 ? `<button class="sm" data-merge="${esc(g.ids[0])}|${esc(g.ids[1])}">Merge into first</button>` : ""}</td></tr>`).join("")}</table>
          <p class="small muted">Merging keeps the first lead, fills its blanks from the second, combines sources and tags, and moves the second to rejected with a "duplicate" tag.</p>` : `<p class="muted">No likely duplicates.</p>`}</div>
      <div class="card"><h2>Search log</h2><p class="small muted">Queries the agent already ran (it skips these).</p><div class="notes" style="max-height:260px">${esc(searches.text || "No searches logged yet.")}</div></div>
      <div class="card"><h2>Product description <code>product.md</code></h2><textarea id="doc-product" class="mono" rows="16">${esc(prod.text)}</textarea><div class="row end" style="margin-top:6px"><button data-doc="product.md">Save</button></div></div>
      <div class="card"><h2>Ideal customer profile <code>icp.md</code></h2><textarea id="doc-icp" class="mono" rows="16">${esc(icp.text)}</textarea><div class="row end" style="margin-top:6px"><button data-doc="icp.md">Save</button></div></div>
    </div>`;
  bindLeadLinks(el);
  $$("[data-fmt]", el).forEach((b) => b.addEventListener("click", () => {
    const p = new URLSearchParams({ format: b.dataset.fmt });
    if ($("#x-stage").value) p.set("stage", $("#x-stage").value);
    if ($("#x-min").value) p.set("min_score", $("#x-min").value);
    if ($("#x-tag").value) p.set("tag", $("#x-tag").value);
    location.href = "/api/export?" + p;
  }));
  $$("[data-doc]", el).forEach((b) => b.addEventListener("click", async () => {
    const name = b.dataset.doc;
    try { await api("doc", { name, text: $(name === "icp.md" ? "#doc-icp" : "#doc-product").value }); toast(`Saved ${name}`); await loadAll(); } catch (e) { fail(e); }
  }));
  $$("[data-merge]", el).forEach((b) => b.addEventListener("click", async () => {
    const [keep, dup] = b.dataset.merge.split("|");
    if (!confirm(`Merge ${dup} into ${keep}?`)) return;
    try { await api("merge", { keep, dup }); toast("Merged"); await loadAll(); PAGES.data(el); } catch (e) { fail(e); }
  }));
  const doImport = async (dry) => {
    const f = $("#i-file").files[0];
    if (!f) return toast("Choose a CSV file first", true);
    try {
      const res = await api("import", { csv: await f.text(), stage: $("#i-stage").value, tags: $("#i-tag").value, source: $("#i-src").value, dry_run: dry });
      const map = Object.entries(res.mapping).map(([h, c]) => `${esc(h)} → <b>${esc(c)}</b>`).join(", ");
      if (dry) $("#i-out").innerHTML = `<p>Columns: ${map}</p><p>${res.rows} rows. First rows: ${res.preview.map((p) => esc(p.company)).join(", ")}</p>${res.preview.some((p) => !p.sources) ? `<p class="overdue">Some rows have no source. Fill "Source for rows without one" or they will be skipped.</p>` : ""}`;
      else {
        const reasons = {};
        res.skipped.forEach(([, why]) => { const k = why.replace(/\(.*\)/, "").replace(/ [a-z0-9.-]+\.[a-z]{2,}.*/, "").trim(); reasons[k] = (reasons[k] || 0) + 1; });
        $("#i-out").innerHTML = `<p><b>${res.added.length} added</b>, ${res.skipped.length} skipped of ${res.rows}. ${Object.entries(reasons).map(([k, v]) => `${v} × ${esc(k)}`).join("; ")}</p>`;
        await loadAll();
      }
    } catch (e) { fail(e); }
  };
  $("#i-preview").addEventListener("click", () => doImport(true));
  $("#i-go").addEventListener("click", () => doImport(false));
};

// ---------- start ----------
loadAll().then(route).catch((e) => { $("#main").innerHTML = `<div class="empty">Could not load: ${esc(e.message)}</div>`; });
setInterval(async () => {
  // keep badges fresh, e.g. while the agent adds leads from a run
  if (document.hidden) return;
  try { const st = await api("state"); const changed = st.running !== S.state.running || st.product !== S.state.product; S.state = st; if (changed) await loadAll(); renderChrome(); } catch {}
}, 10000);
