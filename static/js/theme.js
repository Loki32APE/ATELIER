/* Atelier Prompt Engine — theme.js
   Split from the former static/script.js. Original source order is preserved. */
const CATALOG_V1 = { global: null, index: null, themes: {} };

async function loadCatalogV1() {
  try {
    const catalog = await AtelierCatalogService.loadThemeCatalog();
    CATALOG_V1.global = catalog.global;
    CATALOG_V1.index = catalog.index;
    CATALOG_V1.themes = catalog.themes;
    if (catalog.errors.length) console.warn("Theme catalog partial errors:", catalog.errors);
    console.info("Catalog v1 loaded:", Object.keys(CATALOG_V1.themes).length, "themes");
  } catch (err) {
    console.error("Catalog v1 load failed:", err.message);
  }
}

loadCatalogV1();

// ================= Scratchpad settings UI (Catalog v1) =================
// Order: Camera -> Theme -> Art Style -> Background -> Attire -> Appearance -> Action -> Character
const SHOT_IDS = { "Close-up": "close_up", "Half body": "half_body", "Full body": "full_body", "3/4 shot": "three_quarter" };
const SHOT_LABELS = ["Close-up", "Half body", "Full body", "3/4 shot"];
const SETTINGS_OPEN = new Set(["camera"]);
const ITEM_KEYS = ["lens", "lighting", "artstyle", "background", "outfit", "jewellery", "accessories", "objects", "hairstyle", "makeup", "poses", "actions"];

function themeEntries() {
  const idx = CATALOG_V1.index;
  if (!idx) return [];
  return idx.themes.filter(t => t.enabled !== false).map(t => ({ id: t.id, data: CATALOG_V1.themes[t.id] })).filter(t => t.data);
}

function currentTheme() {
  if (!selectedSettings.theme) return null;
  const hit = themeEntries().find(t => (t.data.name || t.data.title) === selectedSettings.theme);
  return hit ? hit.data : null;
}

function currentShotId() {
  return SHOT_IDS[selectedSettings.shot] || null;
}

// Har item ke liye allowed options (shot + theme ke hisaab se)
function optionsFor(key) {
  const theme = currentTheme();
  const shot = currentShotId();
  if (key === "artstyle") return CATALOG_V1.global ? (CATALOG_V1.global.art_styles || []) : [];
  if (!theme) return [];
  // shot-wise data (v1) ya top-level data (v2)
  const s = (theme.shots && shot && theme.shots[shot]) || theme;
  switch (key) {
    case "lens": return s.camera || [];
    case "lighting": return s.lighting || [];
    case "background": return s.backgrounds || s.background || [];
    case "outfit": return s.outfit || [];
    case "jewellery": return s.jewellery || [];
    case "accessories": return s.accessories || [];
    case "objects": return s.objects || [];
    case "hairstyle": return s.hairstyle || [];
    case "makeup": return s.makeup || [];
    case "poses": return s.poses || [];
    case "actions": return s.actions || [];
  }
  return [];
}

// Shot ya theme badle to jo selection ab allowed nahi, use clear karo.
function chipGroup(title, key, items, disabledMsg) {
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
  const row = document.createElement("div");
  row.className = "chip-row";
  items.forEach(val => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip" + (selectedSettings[key] === val ? " active" : "");
    b.textContent = val;
    b.onclick = () => {
      selectedSettings[key] = val;
      renderSettingsV1();
    };
    row.appendChild(b);
  });
  wrap.appendChild(row);
  return wrap;
}

function sectionNode(id, label, bodyEl) {
  const node = document.createElement("div");
  node.className = "category-node";
  node.id = "node-" + id;
  const head = document.createElement("div");
  head.className = "category-node-header";
  head.onclick = () => toggleCategoryNode(id);
  head.innerHTML = `<span class="cat-title">${label}</span><span class="cat-arrow">${SETTINGS_OPEN.has(id) ? "▼" : "▶"}</span>`;
  const body = document.createElement("div");
  body.className = "category-node-body";
  body.style.display = SETTINGS_OPEN.has(id) ? "block" : "none";
  body.appendChild(bodyEl);
  node.appendChild(head);
  node.appendChild(body);
  return node;
}function buildCharacterBody() {
  const m = document.createElement("div");
  m.className = "gen-hint";
  m.textContent = "Character design abhi catalog mein nahi hai (next step).";
  return m;
}// Override: accordion toggle (open-state yaad rakhta hai)
function toggleCategoryNode(id) {
  if (SETTINGS_OPEN.has(id)) SETTINGS_OPEN.delete(id); else SETTINGS_OPEN.add(id);
  renderSettingsV1();
}

// Override: sab clear, phir re-render// Shot mandatory: Generate se pehle shot check
const __origGenerateFromScratchpad = generateFromScratchpad;
generateFromScratchpad = function () {
  if (!selectedSettings.shot) {
    showToast("Pehle shot type chuniye");
    return;
  }
  return __origGenerateFromScratchpad();
};

// Chips ki basic styling (theme.css mein nahi thi)
const __chipStyle = document.createElement("style");
__chipStyle.textContent = `
  .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0 14px; }
  .chip { background: transparent; color: #d8d0c0; border: 1px solid rgba(201,169,97,0.35); border-radius: 999px;
    padding: 7px 12px; font-size: 0.8rem; cursor: pointer; }
  .chip.active { background: linear-gradient(135deg,#f1dc9a,#c9a961); color: #140f06; border-color: transparent; font-weight: 600; }
  .ct { font-size: .7rem; letter-spacing: .14em; text-transform: uppercase; color: #c9a961; margin: 8px 0 4px; }
`;
document.head.appendChild(__chipStyle);

// Catalog load hone ke baad settings render karo
const __origLoadCatalogV1 = loadCatalogV1;
loadCatalogV1 = async function () {
  await __origLoadCatalogV1();
  renderSettingsV1();
};
loadCatalogV1();

// ================= v2: dropdown format + multi-select (jewellery 4, accessories 3) =================
