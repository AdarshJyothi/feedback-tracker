/* Feedback Tracker — frontend logic (vanilla JS + Chart.js) */

const API = "http://localhost:8000/api/v1";

// ---------- state ----------
let USERS = [];
let OPTIONS = {};
let charts = {}; // Chart.js instances, keyed by canvas id
let currentDetailId = null;

// ---------- helpers ----------
async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (_) { /* ignore */ }
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

function toast(msg, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = `toast${isError ? " error" : ""}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), 3500);
}

const fmtDate = (d) => (d ? new Date(d).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pillStatus = (s) => `<span class="pill st-${s.replaceAll(" ", "")}">${esc(s)}</span>`;
const pillSeverity = (s) => `<span class="pill sev-${s}">${esc(s)}</span>`;
const currentUserId = () => Number(document.getElementById("current-user").value);

function fillSelect(sel, values, { placeholder = null, useNames = false } = {}) {
  sel.innerHTML = placeholder ? `<option value="">${placeholder}</option>` : "";
  for (const v of values) {
    const opt = document.createElement("option");
    if (useNames) { opt.value = v.id; opt.textContent = `${v.name} (${v.role})`; }
    else { opt.value = v; opt.textContent = v; }
    sel.appendChild(opt);
  }
}

// ---------- boot ----------
async function boot() {
  try {
    [USERS, OPTIONS] = await Promise.all([api("/meta/users"), api("/meta/options")]);
  } catch (e) {
    toast(`Cannot reach API at ${API} — is the backend running?`, true);
    return;
  }

  fillSelect(document.getElementById("current-user"), USERS, { useNames: true });

  // filters
  fillSelect(document.getElementById("filter-status"), OPTIONS.complaint_statuses, { placeholder: "All statuses" });
  fillSelect(document.getElementById("filter-category"), OPTIONS.categories, { placeholder: "All categories" });
  fillSelect(document.getElementById("filter-severity"), OPTIONS.severities, { placeholder: "All severities" });

  // new-complaint form selects
  const form = document.getElementById("new-form");
  fillSelect(form.elements.work_type, OPTIONS.work_types);
  fillSelect(form.elements.category, OPTIONS.categories);
  fillSelect(form.elements.severity, OPTIONS.severities);

  wireEvents();
  await renderDashboard();
}

// ---------- events ----------
function wireEvents() {
  document.querySelectorAll(".tab").forEach((tab) =>
    tab.addEventListener("click", () => switchView(tab.dataset.view))
  );

  let searchTimer;
  document.getElementById("filter-search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(renderComplaints, 300); // debounce
  });
  ["filter-status", "filter-category", "filter-severity", "filter-overdue"].forEach((id) =>
    document.getElementById(id).addEventListener("change", renderComplaints)
  );

  document.getElementById("btn-new").addEventListener("click", () =>
    document.getElementById("new-backdrop").classList.remove("hidden")
  );

  document.querySelectorAll("[data-close]").forEach((el) =>
    el.addEventListener("click", () => {
      el.closest(".modal-backdrop").classList.add("hidden");
    })
  );
  document.querySelectorAll(".modal-backdrop").forEach((bd) =>
    bd.addEventListener("click", (e) => { if (e.target === bd) bd.classList.add("hidden"); })
  );

  document.getElementById("new-form").addEventListener("submit", onCreateComplaint);
}

function switchView(view) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  document.getElementById("view-dashboard").classList.toggle("hidden", view !== "dashboard");
  document.getElementById("view-complaints").classList.toggle("hidden", view !== "complaints");
  if (view === "dashboard") renderDashboard();
  else renderComplaints();
}

// ---------- dashboard ----------
async function renderDashboard() {
  const [summary, byCat, byRC, bySev, byWT, trend] = await Promise.all([
    api("/stats/summary"),
    api("/stats/by-category"),
    api("/stats/by-root-cause"),
    api("/stats/by-severity"),
    api("/stats/by-work-type"),
    api("/stats/trend?weeks=12"),
  ]).catch((e) => { toast(e.message, true); return []; });
  if (!summary) return;

  const kpis = [
    { label: "Open", value: summary.open, cls: summary.open > 0 ? "warn" : "good" },
    { label: "Under investigation", value: summary.under_investigation, cls: "" },
    { label: "Overdue (open)", value: summary.overdue_open, cls: summary.overdue_open > 0 ? "bad" : "good" },
    { label: "Avg resolution (days)", value: summary.avg_resolution_days ?? "—", cls: "" },
    { label: `SLA met (≤${OPTIONS.sla_days}d)`, value: summary.sla_met_pct != null ? summary.sla_met_pct + "%" : "—", cls: summary.sla_met_pct >= 80 ? "good" : "warn" },
    { label: "Open actions", value: summary.open_actions, cls: "" },
    { label: "Overdue actions", value: summary.overdue_actions, cls: summary.overdue_actions > 0 ? "bad" : "good" },
  ];
  document.getElementById("kpi-row").innerHTML = kpis
    .map((k) => `<div class="kpi"><div class="label">${k.label}</div><div class="value ${k.cls}">${k.value}</div></div>`)
    .join("");

  const css = getComputedStyle(document.documentElement);
  const C = {
    accent: css.getPropertyValue("--accent").trim(),
    green: css.getPropertyValue("--green").trim(),
    amber: css.getPropertyValue("--amber").trim(),
    red: css.getPropertyValue("--red").trim(),
    purple: css.getPropertyValue("--purple").trim(),
    dim: css.getPropertyValue("--text-dim").trim(),
    border: css.getPropertyValue("--border").trim(),
  };
  Chart.defaults.color = C.dim;
  Chart.defaults.borderColor = C.border;

  makeChart("chart-trend", {
    type: "line",
    data: {
      labels: trend.map((t) => fmtDate(t.week_start)),
      datasets: [
        { label: "Received", data: trend.map((t) => t.received), borderColor: C.amber, backgroundColor: C.amber, tension: 0.3 },
        { label: "Resolved", data: trend.map((t) => t.resolved), borderColor: C.green, backgroundColor: C.green, tension: 0.3 },
      ],
    },
    options: { plugins: { legend: { position: "bottom" } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  makeChart("chart-category", {
    type: "bar",
    data: {
      labels: byCat.map((x) => x.label),
      datasets: [{ data: byCat.map((x) => x.count), backgroundColor: C.accent, borderRadius: 4 }],
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { ticks: { autoSkip: false, maxRotation: 45, minRotation: 30 } } } },
  });

  makeChart("chart-rootcause", {
    type: "bar",
    data: {
      labels: byRC.map((x) => x.label),
      datasets: [{ data: byRC.map((x) => x.count), backgroundColor: C.purple, borderRadius: 4 }],
    },
    options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  makeChart("chart-severity", {
    type: "doughnut",
    data: {
      labels: bySev.map((x) => x.label),
      datasets: [{ data: bySev.map((x) => x.count), backgroundColor: [C.green, C.accent, C.amber, C.red], borderWidth: 0 }],
    },
    options: { plugins: { legend: { position: "bottom" } }, cutout: "60%" },
  });

  makeChart("chart-worktype", {
    type: "bar",
    data: {
      labels: byWT.map((x) => x.label),
      datasets: [{ data: byWT.map((x) => x.count), backgroundColor: C.green, borderRadius: 4 }],
    },
    options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } },
  });
}

function makeChart(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

// ---------- complaints list ----------
async function renderComplaints() {
  const params = new URLSearchParams();
  const search = document.getElementById("filter-search").value.trim();
  const status = document.getElementById("filter-status").value;
  const category = document.getElementById("filter-category").value;
  const severity = document.getElementById("filter-severity").value;
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  if (severity) params.set("severity", severity);
  if (document.getElementById("filter-overdue").checked) params.set("overdue", "true");
  params.set("limit", "200");

  let data;
  try { data = await api(`/complaints?${params}`); }
  catch (e) { toast(e.message, true); return; }

  const tbody = document.querySelector("#complaints-table tbody");
  tbody.innerHTML = data.items
    .map((c) => {
      const days = c.resolution_days ?? Math.floor((Date.now() - new Date(c.received_date)) / 86400000);
      return `<tr data-id="${c.id}">
        <td class="ref">${esc(c.ref)}</td>
        <td>${fmtDate(c.received_date)}</td>
        <td>${esc(c.work_type)}</td>
        <td>${esc(c.category)}</td>
        <td>${pillSeverity(c.severity)}</td>
        <td>${pillStatus(c.status)}${c.is_overdue && c.status !== "Closed" ? '<span class="pill overdue">overdue</span>' : ""}</td>
        <td>${esc(c.root_cause ?? "—")}</td>
        <td>${days}</td>
      </tr>`;
    })
    .join("");
  document.getElementById("table-empty").classList.toggle("hidden", data.items.length > 0);
  tbody.querySelectorAll("tr").forEach((tr) =>
    tr.addEventListener("click", () => openDetail(Number(tr.dataset.id)))
  );
}

// ---------- detail ----------
async function openDetail(id) {
  currentDetailId = id;
  let c;
  try { c = await api(`/complaints/${id}`); }
  catch (e) { toast(e.message, true); return; }

  const rcOptions = OPTIONS.root_causes
    .map((rc) => `<option value="${rc}" ${c.root_cause === rc ? "selected" : ""}>${rc}</option>`)
    .join("");

  const transitions = c.allowed_transitions
    .map((t) => `<button class="btn small primary" data-transition="${t}">Move to ${t}</button>`)
    .join("");

  const actionsHtml = c.actions.length
    ? c.actions.map((a) => `
        <div class="action-item">
          <div class="row1">
            <span class="title">${esc(a.title)}</span>
            <span class="pill st-${a.status.replaceAll(" ", "")}">${a.status}</span>
            ${a.is_overdue ? '<span class="pill overdue">overdue</span>' : ""}
            <span class="pill">${a.action_type}</span>
          </div>
          ${a.description ? `<div class="meta">${esc(a.description)}</div>` : ""}
          <div class="meta">Owner: ${esc(a.owner.name)} · Due: ${fmtDate(a.due_date)}${a.completed_date ? ` · Completed: ${fmtDate(a.completed_date)}` : ""}</div>
          ${a.status !== "Verified" ? `<div class="inline-form">
            <select data-action-status="${a.id}">
              ${OPTIONS.action_statuses.map((s) => `<option ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}
            </select>
            <button class="btn small" data-action-save="${a.id}">Update</button>
          </div>` : ""}
        </div>`).join("")
    : '<p class="muted">No actions yet.</p>';

  const commentsHtml = c.comments.length
    ? c.comments.map((cm) => `
        <div class="comment-item">
          <div class="meta"><strong>${esc(cm.author.name)}</strong> · ${fmtDate(cm.created_at)}</div>
          <p>${esc(cm.text)}</p>
        </div>`).join("")
    : '<p class="muted">No comments yet.</p>';

  document.getElementById("detail-body").innerHTML = `
    <div class="detail-head">
      <h2>${esc(c.ref)}</h2>
      ${pillStatus(c.status)} ${pillSeverity(c.severity)}
      ${c.is_overdue && c.status !== "Closed" ? '<span class="pill overdue">overdue</span>' : ""}
    </div>
    <div class="detail-grid">
      <div class="item"><div class="k">Policy</div><div class="v">${esc(c.policy_ref)}</div></div>
      <div class="item"><div class="k">Work type</div><div class="v">${esc(c.work_type)}</div></div>
      <div class="item"><div class="k">Category</div><div class="v">${esc(c.category)}</div></div>
      <div class="item"><div class="k">Received</div><div class="v">${fmtDate(c.received_date)}</div></div>
      <div class="item"><div class="k">Resolved</div><div class="v">${fmtDate(c.resolved_date)}${c.resolution_days != null ? ` (${c.resolution_days}d)` : ""}</div></div>
      <div class="item"><div class="k">Raised by</div><div class="v">${esc(c.raised_by.name)}</div></div>
    </div>
    <div class="desc-block">${esc(c.description)}</div>

    <div class="workflow-bar">
      <label class="muted">Root cause:&nbsp;</label>
      <select id="detail-rootcause" ${c.status === "Closed" ? "disabled" : ""}>
        <option value="">— not recorded —</option>${rcOptions}
      </select>
      <button class="btn small" id="save-rootcause" ${c.status === "Closed" ? "disabled" : ""}>Save</button>
      <span class="spacer" style="flex:1"></span>
      ${transitions}
    </div>

    <div class="section-title">RCA actions (${c.actions.length})</div>
    ${actionsHtml}
    ${c.status !== "Closed" ? `
    <div class="inline-form">
      <input class="grow" id="new-action-title" placeholder="New action title…" maxlength="160" />
      <select id="new-action-type">${OPTIONS.action_types.map((t) => `<option>${t}</option>`).join("")}</select>
      <input id="new-action-due" type="date" />
      <button class="btn small primary" id="add-action">Add action</button>
    </div>` : ""}

    <div class="section-title">Comments (${c.comments.length})</div>
    ${commentsHtml}
    <div class="inline-form">
      <input class="grow" id="new-comment" placeholder="Add a comment…" maxlength="2000" />
      <button class="btn small primary" id="add-comment">Comment</button>
    </div>
  `;

  wireDetailEvents(c);
  document.getElementById("detail-backdrop").classList.remove("hidden");
}

function wireDetailEvents(c) {
  const body = document.getElementById("detail-body");

  body.querySelectorAll("[data-transition]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const status = btn.dataset.transition;
      const payload = { status };
      const rc = body.querySelector("#detail-rootcause")?.value;
      if (rc) payload.root_cause = rc;
      try {
        await api(`/complaints/${c.id}`, { method: "PATCH", body: JSON.stringify(payload) });
        toast(`${c.ref} moved to ${status}`);
        await openDetail(c.id);
        renderComplaints();
      } catch (e) { toast(e.message, true); }
    })
  );

  body.querySelector("#save-rootcause")?.addEventListener("click", async () => {
    const rc = body.querySelector("#detail-rootcause").value;
    if (!rc) return toast("Pick a root cause first.", true);
    try {
      await api(`/complaints/${c.id}`, { method: "PATCH", body: JSON.stringify({ root_cause: rc }) });
      toast("Root cause saved");
      await openDetail(c.id);
    } catch (e) { toast(e.message, true); }
  });

  body.querySelector("#add-action")?.addEventListener("click", async () => {
    const title = body.querySelector("#new-action-title").value.trim();
    if (title.length < 3) return toast("Action title needs at least 3 characters.", true);
    const payload = {
      title,
      action_type: body.querySelector("#new-action-type").value,
      owner_id: currentUserId(),
      due_date: body.querySelector("#new-action-due").value || null,
    };
    try {
      await api(`/complaints/${c.id}/actions`, { method: "POST", body: JSON.stringify(payload) });
      toast("Action added");
      await openDetail(c.id);
    } catch (e) { toast(e.message, true); }
  });

  body.querySelectorAll("[data-action-save]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const id = btn.dataset.actionSave;
      const status = body.querySelector(`[data-action-status="${id}"]`).value;
      try {
        await api(`/actions/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
        toast("Action updated");
        await openDetail(c.id);
      } catch (e) { toast(e.message, true); }
    })
  );

  body.querySelector("#add-comment").addEventListener("click", async () => {
    const text = body.querySelector("#new-comment").value.trim();
    if (!text) return;
    try {
      await api(`/complaints/${c.id}/comments`, {
        method: "POST",
        body: JSON.stringify({ author_id: currentUserId(), text }),
      });
      await openDetail(c.id);
    } catch (e) { toast(e.message, true); }
  });
}

// ---------- create ----------
async function onCreateComplaint(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    policy_ref: form.elements.policy_ref.value.trim(),
    work_type: form.elements.work_type.value,
    category: form.elements.category.value,
    severity: form.elements.severity.value,
    description: form.elements.description.value.trim(),
    raised_by_id: currentUserId(),
  };
  if (form.elements.received_date.value) payload.received_date = form.elements.received_date.value;

  try {
    const created = await api("/complaints", { method: "POST", body: JSON.stringify(payload) });
    document.getElementById("new-backdrop").classList.add("hidden");
    form.reset();
    toast(`${created.ref} created`);
    switchView("complaints");
  } catch (err) {
    toast(err.message, true);
  }
}

boot();
