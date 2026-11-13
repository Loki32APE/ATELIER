/* Atelier Prompt Engine — jewellery.js
   Split from the former static/script.js. Original source order is preserved. */
const MULTI_LIMITS = { jewellery: 4, accessories: 3 };
const MULTI_STATE = { jewellery: [], accessories: [] };

function syncMulti(key) {
  const arr = MULTI_STATE[key];
  if (arr.length) selectedSettings[key] = arr.join(", ");
  else delete selectedSettings[key];
}

function sanitizeSelections() {
  for (const k of ITEM_KEYS) {
    const allowed = optionsFor(k);
    if (MULTI_LIMITS[k]) {
      MULTI_STATE[k] = MULTI_STATE[k].filter(x => allowed.includes(x)).slice(0, MULTI_LIMITS[k]);
      syncMulti(k);
      continue;
    }
    const v = selectedSettings[k];
    if (v && !allowed.includes(v)) delete selectedSettings[k];
  }
}

// Single-select dropdown (sab categories)
function selectField(title, key, items, disabledMsg, groups) {
  const wrap = document.createElement("div");
  wrap.className = "cat";
  const t = document.createElement("div");
  t.className = "ct";
  t.textContent = title;
  wrap.appendChild(t);
  if (disabledMsg) {
    const m = document.createElement("div");
    m.className = "gen-hint";
    m.textContent = disabledMsg;
    wrap.appendChild(m);
    return wrap;
  }
  const sel = document.createElement("select");
  sel.className = "settings-select";
  sel.appendChild(new Option("-- Select --", ""));
  if (groups) {
    groups.forEach(g => {
      const og = document.createElement("optgroup");
      og.label = g.label;
      if (g.note) {
        const o = new Option(g.note, "", false, false);
        o.disabled = true;
        og.appendChild(o);
      }
      g.options.forEach(v => og.appendChild(new Option(v, v)));
      sel.appendChild(og);
    });
  } else {
    items.forEach(v => sel.appendChild(new Option(v, v)));
  }
  sel.value = selectedSettings[key] || "";
  sel.onchange = () => {
    if (sel.value) selectedSettings[key] = sel.value;
    else delete selectedSettings[key];
    renderSettingsV1();
  };
  wrap.appendChild(sel);
  return wrap;
}

// Multi-select checklist with limit (jewellery, accessories)
function multiField(title, key, items, disabledMsg) {
  const wrap = document.createElement("div");
  wrap.className = "cat";
  const limit = MULTI_LIMITS[key];
  const head = document.createElement("div");
  head.className = "multi-head";
  head.innerHTML = `<span class="ct">${title}</span><span class="multi-count">${MULTI_STATE[key].length} / ${limit}</span>`;
  wrap.appendChild(head);
  if (disabledMsg) {
    const m = document.createElement("div");
    m.className = "gen-hint";
    m.textContent = disabledMsg;
    wrap.appendChild(m);
    return wrap;
  }
  const list = document.createElement("div");
  list.className = "multi-list";
  items.forEach(val => {
    const row = document.createElement("label");
    row.className = "check-row";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = MULTI_STATE[key].includes(val);
    cb.onchange = () => {
      const arr = MULTI_STATE[key];
      if (cb.checked) {
        if (arr.length >= limit) {
          cb.checked = false;
          showToast(`${title} mein max ${limit} select kar sakte hain`);
          return;
        }
        arr.push(val);
      } else {
        MULTI_STATE[key] = arr.filter(x => x !== val);
      }
      syncMulti(key);
      renderSettingsV1();
    };
    const txt = document.createElement("span");
    txt.textContent = val;
    row.appendChild(cb);
    row.appendChild(txt);
    list.appendChild(row);
  });
  wrap.appendChild(list);
  return wrap;
}function buildThemeBody() {
  const groupsMap = {};
  themeEntries().forEach(t => {
    const g = t.data.group || "indian/other";
    (groupsMap[g] = groupsMap[g] || []).push(t.data.name || t.data.title);
  });
  const order = ["indian/festival", "indian/events", "indian/casual", "indian/royal", "indian/studio", "indian/other"];
  const labels = { "indian/festival": "Indian · Festival", "indian/events": "Indian · Events",
    "indian/casual": "Indian · Casual", "indian/royal": "Indian · Royal", "indian/studio": "Indian · Studio", "indian/other": "Indian · Themes" };
  const groups = order.filter(g => groupsMap[g]).map(g => ({ label: labels[g], options: groupsMap[g] }));
  groups.push({ label: "Western", options: [], note: "More themes coming soon" });
  return selectField("Theme", "theme", null, null, groups);
}

function buildArtBody() {
  return selectField("Art style", "artstyle", optionsFor("artstyle"));
}

function buildSimple(title, keys) {
  const box = document.createElement("div");
  const msg = !selectedSettings.shot ? "Pehle shot type chuniye" : !selectedSettings.theme ? "Pehle theme chuniye" : null;
  keys.forEach(([key, label]) => {
    if (MULTI_LIMITS[key]) box.appendChild(multiField(label, key, optionsFor(key), msg));
    else box.appendChild(selectField(label, key, optionsFor(key), msg));
  });
  return box;
}

function clearAllSettings() {
  for (const k of Object.keys(selectedSettings)) delete selectedSettings[k];
  for (const k of Object.keys(MULTI_STATE)) MULTI_STATE[k] = [];
  renderSettingsV1();
}

// Styles
const __v2Style = document.createElement("style");
__v2Style.textContent = `
  .settings-select { width: 100%; background: #0c0b0a; color: #f1e6cc; border: 1px solid rgba(201,169,97,0.35);
    border-radius: 12px; padding: 12px 12px; font-size: 0.95rem; margin-bottom: 10px; }
  .multi-head { display: flex; justify-content: space-between; align-items: center; margin: 8px 0 4px; }
  .multi-count { font-size: 0.75rem; color: #c9a961; }
  .multi-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
  .check-row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid rgba(201,169,97,0.25);
    border-radius: 10px; color: #f1e6cc; font-size: 0.92rem; }
  .check-row input { accent-color: #c9a961; width: 18px; height: 18px; }
`;
document.head.appendChild(__v2Style);

// ================= Layer 4 loader (Step 4a) =================
// static/Catalog/layer4.json ki list ke hisaab se sab category files load karta hai.
// CATALOG_L4.byCategory[cat][file] = { items: [...] }  |  CATALOG_L4.byId[id] = item
const CATALOG_L4 = { manifest: null, byCategory: {}, byId: {}, errors: [] };

async function loadLayer4() {
  try {
    const catalog = await AtelierCatalogService.loadLayer4Catalog();
    CATALOG_L4.manifest = catalog.manifest;
    CATALOG_L4.byCategory = catalog.byCategory;
    CATALOG_L4.byId = catalog.byId;
    CATALOG_L4.errors = catalog.errors;
    if (CATALOG_L4.errors.length) console.warn("Layer 4 load errors:", CATALOG_L4.errors);
    console.info("Layer 4 loaded:", Object.keys(CATALOG_L4.byId).length, "items");
    if (typeof renderSettingsV1 === "function") renderSettingsV1();
  } catch (err) {
    console.error("Layer 4 manifest load failed:", err.message);
  }
}

loadLayer4();

// ================= Step 4b: layer 4 dropdowns + camera (device -> lens) =================
let CATALOG_CAM = null;
(async () => {
  try {
    CATALOG_CAM = await AtelierCatalogService.loadCameraCatalog();
  } catch (e) {
    console.warn("camera.json load failed:", e.message);
  }
  renderSettingsV1();
})();

const DEVICE_LABELS = { smartphone: "Smartphone", dedicated: "Dedicated camera" };

function l4Items(cat, file) {
  const byCat = CATALOG_L4.byCategory[cat] || {};
  if (file) return (byCat[file] && byCat[file].items) || [];
  return Object.values(byCat).flatMap(f => f.items || []);
}
function shotId() { return SHOT_IDS[selectedSettings.shot] || null; }
function themeId() {
  const h = themeEntries().find(t => (t.data.name || t.data.title) === selectedSettings.theme);
  return h ? h.id : null;
}
// Item list -> names, shot ke hisaab se filter; suggested (theme match) alag
function l4Options(items, extraFilter) {
  const sh = shotId(), th = themeId();
  let ok = items.filter(it => !sh || (it.shots || []).includes(sh));
  if (extraFilter) ok = ok.filter(extraFilter);
  const sug = ok.filter(it => th && (it.themes || []).includes(th));
  return { suggested: sug.map(i => i.name), all: ok.map(i => i.name), byName: Object.fromEntries(ok.map(i => [i.name, i])) };
}
function lensOptions() {
  if (!CATALOG_CAM || !selectedSettings.device) return [];
  const dev = Object.keys(DEVICE_LABELS).find(k => DEVICE_LABELS[k] === selectedSettings.device);
  return dev && CATALOG_CAM.devices[dev] ? CATALOG_CAM.devices[dev].lenses.map(l => l.label) : [];
}
function poseTypeId() {
  const it = l4Items("pose", "type").find(i => i.name === selectedSettings.pose_type);
  return it ? it.id : null;
}
function expressionId() {
  const it = l4Items("expression", "expression").find(i => i.name === selectedSettings.expression);
  return it ? it.id : null;
}

// Har key ke liye allowed names (sanitize + dropdown ke liye)
function l4Spec(key) {
  switch (key) {
    case "device": return { all: Object.values(DEVICE_LABELS), suggested: [] };
    case "lens": return { all: lensOptions(), suggested: [] };
    case "outfit_top": return l4Options(l4Items("outfit", "top"));
    case "outfit_bottom": return l4Options(l4Items("outfit", "bottom"));
    case "outfit_full": return l4Options(l4Items("outfit", "full_dress"));
    case "footwear": return l4Options(l4Items("footwear", "footwear"));
    case "makeup_face": return l4Options(l4Items("makeup", "face"));
    case "makeup_eyes": return l4Options(l4Items("makeup", "eyes"));
    case "makeup_lips": return l4Options(l4Items("makeup", "lips"));
    case "makeup_skin": return l4Options(l4Items("makeup", "skin_texture"));
    case "hair_length": return l4Options(l4Items("hairstyle", "length"));
    case "hair_colour": return l4Options(l4Items("hairstyle", "colour"));
    case "hair_partition": return l4Options(l4Items("hairstyle", "partition"));
    case "hair_style": return l4Options(l4Items("hairstyle", "style"));
    case "pose_type": return l4Options(l4Items("pose", "type"));
    case "pose_object": {
      const pid = poseTypeId();
      return l4Options(l4Items("pose", "object"), it => pid && it.parent === pid);
    }
    case "expression": return l4Options(l4Items("expression", "expression"));
    case "gaze": {
      const eid = expressionId();
      return l4Options(l4Items("gaze", "gaze"), it => eid && (it.expressions || []).includes(eid));
    }
    case "artstyle": return { all: CATALOG_V1.global ? CATALOG_V1.global.art_styles : [], suggested: [] };
    case "lighting": return { all: optionsFor("lighting"), suggested: [] };
    case "background": return { all: optionsFor("background"), suggested: [] };
  }
  if (key.startsWith("jew_")) return l4Options(l4Items("jewellery", key.slice(4)));
  if (key === "acc_1" || key === "acc_2") {
    const other = key === "acc_1" ? selectedSettings.acc_2 : selectedSettings.acc_1;
    const otherIsBag = other && l4Items("accessories").some(i => i.name === other && i.id.startsWith("bag_"));
    return l4Options(l4Items("accessories"), it => {
      if (it.name === other) return false;
      if (otherIsBag && it.id.startsWith("bag_")) return false; // handbag + ek aur accessory
      return true;
    });
  }
  return { all: [], suggested: [] };
}

// Sanitize: jo value ab allowed nahi, use hatao
sanitizeSelections = function () {
  const keys = Object.keys(selectedSettings).filter(k => !["shot", "theme"].includes(k));
  for (const k of keys) {
    const spec = l4Spec(k);
    const allowed = new Set([...(spec.all || [])]);
    if (!allowed.has(selectedSettings[k])) delete selectedSettings[k];
  }
};

function l4Select(title, key, disabledMsg, extraNote) {
  const spec = l4Spec(key);
  const groups = [];
  if (spec.suggested && spec.suggested.length) groups.push({ label: "Recommended", options: spec.suggested });
  groups.push({ label: "All options", options: spec.all });
  if (extraNote) groups[0] = groups[0] || { label: "", options: [] };
  return selectField(title, key, null, disabledMsg, groups);
}

const NEED_SHOT = "Pehle shot type chuniye";
const NEED_THEME = "Pehle theme chuniye";

function buildCameraBody() {
  const box = document.createElement("div");
  box.appendChild(selectField("Shot type (mandatory)", "shot", SHOT_LABELS));
  box.appendChild(selectField("Device", "device", Object.values(DEVICE_LABELS)));
  const lensMsg = !selectedSettings.device ? "Pehle device chuniye" : null;
  box.appendChild(selectField("Lens", "lens", lensOptions(), lensMsg));
  const lightMsg = !selectedSettings.shot ? NEED_SHOT : !selectedSettings.theme ? NEED_THEME : null;
  box.appendChild(selectField("Lighting", "lighting", optionsFor("lighting"), lightMsg));
  return box;
}

function buildAttireBody() {
  const box = document.createElement("div");
  const sMsg = !selectedSettings.shot ? NEED_SHOT : null;
  if (sMsg) { const m = document.createElement("div"); m.className = "gen-hint"; m.textContent = sMsg; box.appendChild(m); return box; }
  // Outfit: full dress chuna to top/bottom grey
  const fullChosen = !!selectedSettings.outfit_full;
  const tb = fullChosen ? "Full dress chuna hai, top/bottom ki zaroorat nahi" : null;
  box.appendChild(l4Select("Top", "outfit_top", tb));
  box.appendChild(l4Select("Bottom", "outfit_bottom", tb));
  box.appendChild(l4Select("Full dress", "outfit_full", null));
  const zones = ["ear", "nose", "hair", "forehead", "neck", "waist", "hand", "foot"];
  zones.forEach(z => box.appendChild(l4Select("Jewellery · " + z, "jew_" + z, null)));
  box.appendChild(l4Select("Accessory 1", "acc_1", null));
  box.appendChild(l4Select("Accessory 2", "acc_2", null));
  const foot = selectedSettings.shot === "Full body" ? null : "Footwear sirf full body mein dikhega";
  box.appendChild(l4Select("Footwear", "footwear", foot));
  return box;
}

function buildAppearanceBody() {
  const box = document.createElement("div");
  const m = !selectedSettings.shot ? NEED_SHOT : null;

  // Appearance ke andar Makeup aur Hair ko alag nested dropdown groups mein rakho.
  const makeupBox = document.createElement("div");
  ["makeup_face", "makeup_eyes", "makeup_lips", "makeup_skin"].forEach((k, i) => {
    const labels = ["Face", "Eyes", "Lips", "Skin texture"];
    makeupBox.appendChild(l4Select(labels[i], k, m));
  });
  box.appendChild(sectionNode("appearance-makeup", "Makeup", makeupBox));

  const hairBox = document.createElement("div");
  ["hair_length", "hair_colour", "hair_partition", "hair_style"].forEach((k, i) => {
    const labels = ["Length", "Colour", "Partition", "Style"];
    hairBox.appendChild(l4Select(labels[i], k, m));
  });
  box.appendChild(sectionNode("appearance-hair", "Hair", hairBox));

  return box;
}

function buildActionBody() {
  const box = document.createElement("div");
  const m = !selectedSettings.shot ? NEED_SHOT : null;
  box.appendChild(l4Select("Pose type", "pose_type", m));
  box.appendChild(l4Select("Object", "pose_object", m || (!selectedSettings.pose_type ? "Pehle pose type chuniye" : null)));
  box.appendChild(l4Select("Expression", "expression", m));
  box.appendChild(l4Select("Gaze", "gaze", m || (!selectedSettings.expression ? "Pehle expression chuniye" : null)));
  return box;
}

function renderSettingsV1() {
  const tree = document.getElementById("settingsTree");
  if (!tree) return;
  if (!CATALOG_V1.index) { tree.innerHTML = '<div class="empty-state">Catalog load ho raha hai...</div>'; return; }
  sanitizeSelections();
  tree.innerHTML = "";
  tree.appendChild(sectionNode("camera", "Camera settings", buildCameraBody()));
  tree.appendChild(sectionNode("theme", "Theme / Genre", buildThemeBody()));
  tree.appendChild(sectionNode("artstyle", "Art Style", selectField("Art style", "artstyle", null, null, [{ label: "All options", options: l4Spec("artstyle").all }])));
  const bgMsg = !selectedSettings.shot ? NEED_SHOT : !selectedSettings.theme ? NEED_THEME : null;
  tree.appendChild(sectionNode("background", "Background / Location", selectField("Background", "background", optionsFor("background"), bgMsg)));
  tree.appendChild(sectionNode("attire", "Attire", buildAttireBody()));
  tree.appendChild(sectionNode("appearance", "Appearance", buildAppearanceBody()));
  tree.appendChild(sectionNode("action", "Action", buildActionBody()));
  tree.appendChild(sectionNode("character", "Character Design", buildCharacterBody()));
}

// ---- Model badge (kaun sa model ne prompt banaya) ----
