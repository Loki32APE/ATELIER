/* Atelier Prompt Engine — history.js
   Split from the former static/script.js. Original source order is preserved. */
const MAX_POLL_MS = 15 * 60 * 1000;

const LABELS = [
  "SUBJECT PHYSIQUE", "HAIRSTYLE", "MAKEUP", "OUTFIT", "JEWELLERY AND ACCESSORIES",
  "POSE AND ACTION", "AND GAZE", "BACKGROUND AND ENVIRONMENT", "LIGHTING AND CAMERA",
  "COMPOSITION", "QUALITY", "NEGATIVE PROMPT"
];

const JSON_KEYS = {
  "SUBJECT PHYSIQUE": "subject_physique",
  "HAIRSTYLE": "hairstyle",
  "MAKEUP": "makeup",
  "OUTFIT": "outfit",
  "JEWELLERY AND ACCESSORIES": "jewellery_and_accessories",
  "POSE AND ACTION": "pose_and_action",
  "AND GAZE": "gaze",
  "BACKGROUND AND ENVIRONMENT": "background_and_environment",
  "LIGHTING AND CAMERA": "lighting_and_camera",
  "COMPOSITION": "composition",
  "QUALITY": "quality",
  "NEGATIVE PROMPT": "negative_prompt"
};

const MODE_TEXT = {
  BOTH: "Dual references active: Pose, makeup, lighting, framing, and garments analyzed from look; styling enriched from outfit.",
  LOOK_ONLY: "Single look reference: Pose, anatomy, makeup, and outfit directives extracted from look reference.",
  OUTFIT_ONLY: "Single outfit reference: Generating dedicated garment, texture, and jewelry styling prompts.",
  NONE: "Please select at least one reference photo to begin."
};

const FORMAT_HINT = {
  prompt: "Structured editorial skeleton: Tap any section block to edit text directly.",
  natural: "Unified narrative prose optimized for high-fidelity text-to-image renderers.",
  optimized: "Compact prompt: 1000 characters ke andar, photos aur text se seedha banta hai.",
  json: "Structured schema containing parameters, sections, and negative constraints.",
  raw: "RAW studio prompt: Direct look extraction with locked fabric directives."
};

const DETAIL = {
  fast:     { label: "Fast",     look: 768,  outfit: 768,  target: 1200 },
  balanced: { label: "Balanced", look: 1024, outfit: 768,  target: 2000 },
  detailed: { label: "Detailed", look: 1280, outfit: 1024, target: 3000 }
};

let files = { look: null, outfit: null };
let detail = "balanced";
let busy = false;
let currentSections = {};
let currentRaw = "";
let optSections = {};
let optRaw = "";
let rawSections = {};
let rawRaw = "";
let currentFormat = "prompt";
let currentTarget = DETAIL.balanced.target;
let lastMode = "BOTH";
let lastDetail = "balanced";
let timerIv = null, pollIv = null, startTime = 0, activeJobId = null;
let activeOutputType = "full";





let clearConfirmTimer = null;
function handleClearAllStudio() {
  const btn = $("clearAllBtn");
  if (btn.dataset.confirming === "true") {
    clearTimeout(clearConfirmTimer);
    btn.dataset.confirming = "false";
    btn.textContent = "Clear all";
    clearAllStudio();
  } else {
    btn.dataset.confirming = "true";
    btn.textContent = "Confirm?";
    clearConfirmTimer = setTimeout(() => {
      btn.dataset.confirming = "false";
      btn.textContent = "Clear all";
    }, 2200);
  }
}



// Profiles Storage & Handlers
const PROFILE = {
  subject: { key: "pe_subjects", sel: "subjectSelect", text: "subjectText", count: "subjectCount",
             nameIn: "subjectProfileName", box: "subjectSaveBox", ph: "-- Select saved physique profile --" },
  hair:    { key: "pe_hairs", sel: "hairSelect", text: "hairText", count: "hairCount",
             nameIn: "hairProfileName", box: "hairSaveBox", ph: "-- Select saved hairstyle profile --" },
  pose:    { key: "pe_poses", sel: "poseSelect", text: "poseText", count: "poseCount",
             nameIn: "poseProfileName", box: "poseSaveBox", ph: "-- Select saved pose profile --" }
};

function refreshProfileDropdowns() {
  for (const t of Object.keys(PROFILE)) {
    const c = PROFILE[t];
    const sel = $(c.sel);
    if (!sel) continue;
    const cur = sel.value;
    sel.innerHTML = "";
    sel.appendChild(new Option(c.ph, ""));
    getStorage(c.key).forEach(p => sel.appendChild(new Option(p.name, p.id)));
    if ([...sel.options].some(o => o.value === cur)) sel.value = cur;
  }
  updateDrawerCounts();
}

function saveProfile(type) {
  const c = PROFILE[type];
  const name = $(c.nameIn).value.trim();
  const text = $(c.text).value.trim();
  if (!name || !text) { showToast("Title and description are required"); return; }
  const list = getStorage(c.key);
  const id = uid();
  list.push({ id, name, text });
  setStorage(c.key, list);
  $(c.nameIn).value = "";
  $(c.box).style.display = "none";
  refreshProfileDropdowns();
  $(c.sel).value = id;
  showToast("Profile saved");
}

function loadProfile(type) {
  const c = PROFILE[type];
  const item = getStorage(c.key).find(x => x.id === $(c.sel).value);
  if (item) {
    $(c.text).value = item.text;
    updateCount(c.text, c.count);
  }
}

function deleteProfile(type) {
  const c = PROFILE[type];
  const id = $(c.sel).value;
  if (!id) return;
  setStorage(c.key, getStorage(c.key).filter(x => x.id !== id));
  refreshProfileDropdowns();
  showToast("Profile deleted");
}

// Asset Resizing & Lightbox
const suffix = slot => slot === "look" ? "Look" : "Outfit";

// Execution States & Timers
// Standard & RAW Generation Flow
// Optimization Logic
function clearAllStudio() {
  stopPolling();
  stopTimer();
  clearImage({ stopPropagation: () => {} }, "look");
  clearImage({ stopPropagation: () => {} }, "outfit");
  $("outfitOverride").value = "";
  $("subjectText").value = "";
  $("hairText").value = "";
  $("poseText").value = "";
  $("subjectSelect").value = "";
  $("hairSelect").value = "";
  $("poseSelect").value = "";
  updateCount("subjectText", "subjectCount");
  updateCount("hairText", "hairCount");
  updateCount("poseText", "poseCount");
  $("progressBox").style.display = "none";
  clearOutputCompletely();
  setBusy(false);
  showToast("Atelier workspace cleared");
}

// Output rendering and formatting helpers are in /static/js/output.js.

// Saved Collection & History Handling
function saveCurrentLook() {
  const nameIn = $("lookNameInput");
  const name = nameIn.value.trim();
  if (!name) { showToast("Please specify a look title"); return; }
  const raw = hasSections(currentSections) ? sectionsToRaw(currentSections) : currentRaw;
  if (!raw && !rawRaw) { showToast("No generated prompt available to store"); return; }
  const looks = getStorage("pe_looks");
  const sourceId = window.ATELIER_VERSION_SOURCE_ID || "";
  const source = sourceId ? looks.find(item => item.id === sourceId) : null;
  const id = uid();
  const groupId = source ? (source.versionGroupId || source.id) : id;
  const version = source
    ? Math.max(0, ...looks.filter(item => (item.versionGroupId || item.id) === groupId).map(item => Number(item.version) || 1)) + 1
    : 1;
  looks.unshift({
    id,
    name,
    prompt: raw,
    optimized: optRaw || "",
    raw: hasSections(rawSections) ? sectionsToRaw(rawSections) : (rawRaw || ""),
    mode: lastMode,
    detail: lastDetail,
    ts: new Date().toLocaleString(),
    createdAt: new Date().toISOString(),
    versionGroupId: groupId,
    version,
    parentId: source ? source.id : null,
    projectId: source ? (source.projectId || "") : "",
    favorite: source ? Boolean(source.favorite) : false
  });
  setStorage("pe_looks", looks);
  window.ATELIER_VERSION_SOURCE_ID = null;
  if (typeof renderLibrary === "function") renderLibrary();
  nameIn.value = "";
  $("lookSaveBox").style.display = "none";
  refreshProfileDropdowns();
  showToast("Look saved to atelier archive");
}

function saveToHistory(raw) {
  if (!raw) return;
  const hist = getStorage("pe_history");
  hist.unshift({
    id: uid(),
    name: "Prompt · " + new Date().toLocaleTimeString(),
    prompt: raw,
    ts: new Date().toLocaleString()
  });
  setStorage("pe_history", hist.slice(0, 15));
}

function mkBtn(label, cls, fn) {
  const b = document.createElement("button");
  b.className = cls;
  b.textContent = label;
  b.onclick = fn;
  return b;
}

function renderList(containerId, key, emptyMsg) {
  const cont = $(containerId);
  const q = (containerId === "savedList" && $("savedSearch")) ? $("savedSearch").value.trim().toLowerCase() : "";
  const items = getStorage(key).filter(x => !q || (x.name || "").toLowerCase().includes(q));
  cont.innerHTML = "";
  if (!items.length) {
    const d = document.createElement("div");
    d.className = "empty-state";
    const icon = document.createElement("span");
    icon.className = "empty-icon";
    icon.textContent = "";
    const msg = document.createElement("span");
    msg.textContent = q ? "No looks match your search." : emptyMsg;
    d.append(icon, msg);
    cont.appendChild(d);
    return;
  }
  items.forEach(item => {
    const row = document.createElement("div");
    row.className = "list-item";

    const left = document.createElement("div");
    const t = document.createElement("div");
    t.className = "list-title";
    t.textContent = item.name || "Untitled";
    const s = document.createElement("div");
    s.className = "list-sub";
    s.textContent = item.ts || "";
    left.append(t, s);

    const acts = document.createElement("div");
    acts.style.cssText = "display:flex;gap:6px;";
    acts.append(
      mkBtn("Open", "btn btn-ghost btn-small", () => openSavedItem(key, item.id)),
      mkBtn("Copy", "btn btn-ghost btn-small", () => copySavedItem(key, item.id)),
      mkBtn("Delete", "btn btn-danger btn-small", () => deleteSavedItem(key, item.id))
    );

    row.append(left, acts);
    cont.appendChild(row);
  });
}

function renderSavedLooks() { renderList("savedList", "pe_looks", "No saved looks in collection."); }
function renderHistory() { renderList("historyList", "pe_history", "History log is currently empty."); }

function openSavedItem(key, id) {
  const item = getStorage(key).find(x => x.id === id);
  if (!item) return;
  setSkeleton(item.prompt);
  if (item.optimized) {
    optRaw = item.optimized;
    optSections = parseLabeled(item.optimized);
    if (!hasSections(optSections)) optSections = {};
  }
  if (item.raw) {
    rawRaw = item.raw;
    rawSections = parseLabeled(item.raw);
  }
  if (item.mode) lastMode = item.mode;
  if (item.detail && DETAIL[item.detail]) {
    lastDetail = item.detail;
    currentTarget = DETAIL[item.detail].target;
  }
  activeOutputType = "full";
  configureTabVisibility();
  currentFormat = "prompt";
  expandOutput();
  switchMainTab("studio");
  showToast("Look loaded into Studio");
}

function copySavedItem(key, id) {
  const item = getStorage(key).find(x => x.id === id);
  if (!item) return;
  copyToClipboard(item.optimized || item.prompt, "Prompt copied to clipboard");
}

function deleteSavedItem(key, id) {
  setStorage(key, getStorage(key).filter(x => x.id !== id));
  refreshProfileDropdowns();
  if (key === "pe_looks") renderSavedLooks(); else renderHistory();
  showToast("Item deleted");
}

function clearSavedLooks() {
  if (!confirm("Delete all saved looks from archive?")) return;
  setStorage("pe_looks", []);
  refreshProfileDropdowns();
  renderSavedLooks();
}

function clearHistory() {
  if (!confirm("Clear full generation history?")) return;
  setStorage("pe_history", []);
  renderHistory();
}

// Backup Storage Handling
function exportBackup() {
  const data = {
    pe_subjects: getStorage("pe_subjects"),
    pe_hairs: getStorage("pe_hairs"),
    pe_poses: getStorage("pe_poses"),
    pe_looks: getStorage("pe_looks"),
    pe_history: getStorage("pe_history"),
    ape_projects: getStorage("ape_projects"),
    exported_at: new Date().toISOString()
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Atelier_PE_Backup_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("Atelier archive exported");
}

function isValidList(arr, textField) {
  return Array.isArray(arr) && arr.every(x =>
    x && typeof x.id === "string" && typeof x.name === "string" && typeof x[textField] === "string"
  );
}

function importBackup(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    try {
      const data = JSON.parse(e.target.result);
      if (isValidList(data.pe_subjects, "text")) setStorage("pe_subjects", data.pe_subjects);
      if (isValidList(data.pe_hairs, "text")) setStorage("pe_hairs", data.pe_hairs);
      if (isValidList(data.pe_poses, "text")) setStorage("pe_poses", data.pe_poses);
      if (isValidList(data.pe_looks, "prompt")) setStorage("pe_looks", data.pe_looks);
      if (isValidList(data.pe_history, "prompt")) setStorage("pe_history", data.pe_history);
      if (Array.isArray(data.ape_projects) && data.ape_projects.every(x => x && typeof x.id === "string" && typeof x.name === "string")) setStorage("ape_projects", data.ape_projects);
      refreshProfileDropdowns();
      if (typeof renderLibrary === "function") renderLibrary();
      renderSavedLooks();
      showToast("Atelier archive restored successfully");
    } catch {
      showToast("Invalid backup JSON format");
    }
  };
  reader.readAsText(file);
}

// ==========================================================================
// Scratchpad Mode & Node-Based Settings Architecture
// ==========================================================================
