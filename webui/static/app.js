/* Lead list builder frontend. Plain JS, no build step. */

const $ = (sel) => document.querySelector(sel);

let META = null;
let selectedRunId = null;
let logOffset = 0;
let logTimer = null;

// ------------------------------------------------------------- helpers

async function api(path, opts) {
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail || detail; } catch (e) { /* not JSON */ }
    throw new Error(detail);
  }
  return resp.json();
}

function fmtSize(bytes) {
  if (bytes > 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
  if (bytes > 1024) return (bytes / 1024).toFixed(0) + " KB";
  return bytes + " B";
}

function currentMode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

function selectedTypes() {
  return [...document.querySelectorAll('#type-checkboxes input:checked')].map((el) => el.value);
}

// ------------------------------------------------------------- meta / form

async function loadMeta() {
  META = await api("/api/meta");

  const badges = $("#env-badges");
  badges.innerHTML = "";
  for (const [key, ok] of Object.entries(META.env)) {
    const span = document.createElement("span");
    span.className = "badge " + (ok ? "ok" : "missing");
    span.textContent = `${key} ${ok ? "✓" : "missing"}`;
    badges.appendChild(span);
  }

  const grid = $("#type-checkboxes");
  grid.innerHTML = "";
  for (const t of META.business_types) {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" value="${t.key}"> ${t.label}` +
      `<span class="count">${t.query_count} queries</span>`;
    label.querySelector("input").addEventListener("change", updateEstimate);
    grid.appendChild(label);
  }
  updateEstimate();
}

function updateEstimate() {
  if (!META) return;
  const mode = currentMode();
  if (mode !== "discover" && mode !== "full") { $("#estimate").textContent = ""; return; }

  const picked = selectedTypes();
  const active = META.business_types.filter((t) => picked.length === 0 || picked.includes(t.key));
  const queries = active.reduce((sum, t) => sum + t.query_count, 0);

  const maxCities = parseInt($("#max-cities").value || "0", 10);
  const cities = maxCities > 0 ? Math.min(maxCities, META.city_count) : META.city_count;

  let searches = queries * cities;
  const maxSearches = parseInt($("#max-searches").value || "0", 10);
  if (maxSearches > 0) searches = Math.min(searches, maxSearches);

  $("#estimate").textContent =
    `≈ ${searches.toLocaleString()} Serper searches (${queries} queries × ${cities} cities)`;
}

async function loadInputCsvOptions() {
  const files = await api("/api/files");
  const select = $("#input-csv");
  select.innerHTML = "";
  for (const f of files) {
    const opt = document.createElement("option");
    opt.value = f.name;
    opt.textContent = f.name;
    select.appendChild(opt);
  }
  if (files.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "— no CSVs in output/ yet, run discovery first —";
    select.appendChild(opt);
  }
}

function onModeChange() {
  const mode = currentMode();
  const needsCsv = mode === "enrich" || mode === "score";
  $("#input-csv-field").classList.toggle("hidden", !needsCsv);
  $("#types-field").classList.toggle("hidden", needsCsv);
  $("#limits-field").classList.toggle("hidden", needsCsv);
  if (needsCsv) loadInputCsvOptions();
  updateEstimate();
}

// ------------------------------------------------------------- runs

async function startRun() {
  const btn = $("#start-btn");
  const err = $("#start-error");
  err.textContent = "";
  btn.disabled = true;
  try {
    const mode = currentMode();
    const body = {
      mode,
      types: selectedTypes(),
      max_searches: parseInt($("#max-searches").value || "0", 10),
      max_cities: parseInt($("#max-cities").value || "0", 10),
      input_csv: $("#input-csv").value || "",
    };
    const run = await api("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    selectRun(run.id);
    await refreshRuns();
  } catch (e) {
    err.textContent = e.message;
  } finally {
    btn.disabled = false;
  }
}

async function refreshRuns() {
  const runs = await api("/api/runs");
  const list = $("#runs-list");
  list.innerHTML = "";
  if (runs.length === 0) {
    list.innerHTML = '<p class="sub">No runs yet. Start one above.</p>';
    return;
  }
  for (const run of runs) {
    const row = document.createElement("div");
    row.className = "run-row" + (run.id === selectedRunId ? " selected" : "");
    row.innerHTML =
      `<span class="status ${run.status}">${run.status}</span>` +
      `<span class="cmd">${run.command}</span>` +
      `<span class="hint">${run.started_at.replace("T", " ")}</span>`;
    row.addEventListener("click", () => selectRun(run.id));
    list.appendChild(row);
  }
}

function selectRun(runId) {
  selectedRunId = runId;
  logOffset = 0;
  $("#log-panel").classList.remove("hidden");
  $("#log-title").textContent = "run " + runId;
  $("#log-output").textContent = "";
  refreshRuns();
  pollLog();
}

async function pollLog() {
  clearTimeout(logTimer);
  if (!selectedRunId) return;
  try {
    const data = await api(`/api/runs/${selectedRunId}/log?offset=${logOffset}`);
    if (data.content) {
      const pre = $("#log-output");
      const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
      pre.textContent += data.content;
      if (atBottom) pre.scrollTop = pre.scrollHeight;
    }
    logOffset = data.offset;
    $("#stop-btn").classList.toggle("hidden", data.status !== "running");
    if (data.status === "running" || data.status === "stopping") {
      logTimer = setTimeout(pollLog, 2000);
    } else {
      refreshRuns();
      refreshFiles();
    }
  } catch (e) {
    logTimer = setTimeout(pollLog, 5000);
  }
}

async function stopRun() {
  if (!selectedRunId) return;
  try { await api(`/api/runs/${selectedRunId}/stop`, { method: "POST" }); } catch (e) { /* already done */ }
  pollLog();
}

// ------------------------------------------------------------- files

async function refreshFiles() {
  const files = await api("/api/files");
  const tbody = $("#files-table tbody");
  tbody.innerHTML = "";
  if (files.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="sub">Nothing in output/ yet.</td></tr>';
    return;
  }
  for (const f of files) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td class="name">${f.name}</td>` +
      `<td>${fmtSize(f.size)}</td>` +
      `<td>${f.modified.replace("T", " ")}</td>` +
      `<td><a href="/api/files/download?name=${encodeURIComponent(f.name)}">download</a></td>`;
    tbody.appendChild(tr);
  }
}

// ------------------------------------------------------------- init

document.querySelectorAll('input[name="mode"]').forEach((el) => el.addEventListener("change", onModeChange));
$("#max-cities").addEventListener("input", updateEstimate);
$("#max-searches").addEventListener("input", updateEstimate);
$("#start-btn").addEventListener("click", startRun);
$("#stop-btn").addEventListener("click", stopRun);

loadMeta();
refreshRuns();
refreshFiles();
setInterval(refreshRuns, 5000);
