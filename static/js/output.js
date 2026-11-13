/* Output rendering and formatting helpers.
 * Loaded as a classic script after core.js and before script.js.
 * It intentionally uses shared state/constants initialised by script.js at runtime.
 */

// Prompt Parsing & Formatting
function parseLabeled(raw) {
  const out = {};
  let active = null;
  for (const line of (raw || "").split(/\r?\n/)) {
    const t = line.trim();
    if (!t) continue;
    const hit = LABELS.find(l => t.toUpperCase().startsWith(l + ":"));
    if (hit) {
      active = hit;
      out[hit] = t.slice(hit.length + 1).trim();
    } else if (active) {
      out[active] = (out[active] ? out[active] + " " : "") + t;
    }
  }
  return out;
}

function hasSections(map) {
  return !!map && Object.values(map).some(v => v && v.trim());
}

function sectionsToRaw(map) {
  return LABELS
    .filter(l => map[l] && map[l].trim())
    .map(l => `${l}: ${map[l].trim()}`)
    .join("\n\n");
}

function setSkeleton(raw) {
  currentRaw = (raw || "").trim();
  currentSections = parseLabeled(currentRaw);
  optSections = {};
  optRaw = "";
}

function cleanClause(str) {
  if (!str) return "";
  const s = str.trim();
  return /[.!?]$/.test(s) ? s.slice(0, -1).trim() : s;
}

function buildNatural(map, raw) {
  if (!hasSections(map)) return raw || "";
  const sec = k => cleanClause(map[k]);
  const comp = sec("COMPOSITION") || "vertical 9:16 portrait";
  const sub = sec("SUBJECT PHYSIQUE")
    .replace(/^Use the person from the reference photo\.?\s*/i, "")
    .replace(/^Keep her facial bone structure[^.]*\.?\s*/i, "")
    .trim();
  const hair = sec("HAIRSTYLE");
  const makeup = sec("MAKEUP");
  const outfit = sec("OUTFIT");
  const ja = sec("JEWELLERY AND ACCESSORIES");
  const pose = sec("POSE AND ACTION");
  const gaze = sec("AND GAZE");
  const bg = sec("BACKGROUND AND ENVIRONMENT");
  const light = sec("LIGHTING AND CAMERA");
  const qual = sec("QUALITY");
  const neg = sec("NEGATIVE PROMPT");

  const s = [];
  s.push(`Strictly preserving the exact facial identity and bone structure from the uploaded reference photo, captured in a ${comp}.`);
  if (sub) s.push(sub.charAt(0).toUpperCase() + sub.slice(1) + ".");
  if (hair && makeup) s.push(`Her hair is styled with ${hair}, complemented by ${makeup}.`);
  else if (hair) s.push(`Her hair is styled with ${hair}.`);
  else if (makeup) s.push(`Her makeup features ${makeup}.`);

  if (outfit) {
    let line = `She is wearing ${outfit.replace(/^(she wears|she is wearing|wearing)\s+/i, "")}`;
    line += ja && ja.toLowerCase() !== "none" ? `, paired with ${ja}.` : ".";
    s.push(line);
  } else if (ja && ja.toLowerCase() !== "none") {
    s.push(`Her look is accessorized with ${ja}.`);
  }

  if (pose && gaze) s.push(`She poses with ${pose}, while her gaze shows ${gaze}.`);
  else if (pose) s.push(`She poses with ${pose}.`);
  else if (gaze) s.push(`Her gaze shows ${gaze}.`);

  if (bg) s.push(`The setting features ${bg}.`);
  if (light) s.push(`Lighting and optics: ${light}.`);
  if (qual) s.push(`${qual}.`);
  if (neg) s.push(`Avoid: ${neg}.`);
  return s.join(" ");
}

function buildJson(map, raw, source) {
  const meta = { source, mode: lastMode, detail: lastDetail, target_chars: currentTarget };
  if (!hasSections(map)) return JSON.stringify({ meta, prompt: raw }, null, 2);

  const sections = {};
  let negative = [];
  LABELS.forEach(lbl => {
    const v = (map[lbl] || "").trim();
    if (!v) return;
    if (lbl === "NEGATIVE PROMPT") negative = v.split(",").map(x => x.trim()).filter(Boolean);
    else sections[JSON_KEYS[lbl]] = v;
  });
  meta.char_count = sectionsToRaw(map).length;
  return JSON.stringify({ meta, sections, negative_prompt: negative }, null, 2);
}

// UI Cards & Formats Rendering
function card(label, val, editable, map) {
  const c = document.createElement("div");
  c.className = "sk-card";

  const h = document.createElement("div");
  h.className = "sk-header";

  const t = document.createElement("span");
  t.className = "sk-label";
  t.textContent = label;

  const b = document.createElement("button");
  b.className = "icon-btn";
  b.textContent = "Copy section";
  b.onclick = () => {
    copyToClipboard(`${label}: ${map[label] || ""}`, `${label} copied to clipboard`);
    b.textContent = "Copied";
    b.classList.add("copied");
    setTimeout(() => {
      b.textContent = "Copy section";
      b.classList.remove("copied");
    }, 1500);
  };

  h.append(t, b);

  const body = document.createElement("div");
  body.className = "sk-body";
  body.contentEditable = editable ? "true" : "false";
  body.textContent = val;
  body.oninput = () => {
    if (editable) map[label] = body.innerText.trim();
    updateOutputCharCount();
  };

  c.append(h, body);
  return c;
}

function renderCards(map, editable, rawFallback) {
  const box = $("sectionView");
  box.innerHTML = "";
  if (!hasSections(map)) {
    const fb = { PROMPT: rawFallback || "" };
    box.appendChild(card("PROMPT", fb.PROMPT, false, fb));
    return;
  }
  LABELS.forEach(lbl => {
    const v = (map[lbl] || "").trim();
    if (v) box.appendChild(card(lbl, v, editable, map));
  });
}

function syncFormatTabs() {
  ["prompt", "natural", "optimized", "json", "raw"].forEach(f => {
    const el = $("fmt-" + f);
    if (el) {
      const active = f === currentFormat;
      el.classList.toggle("active", active);
      el.setAttribute("aria-pressed", String(active));
    }
  });
}

function setFormat(fmt) {
  currentFormat = fmt;
  syncFormatTabs();
  renderFormat();
  $("sheetScrollBody").scrollTop = 0;
}

function renderFormat() {
  const sv = $("sectionView");
  const tv = $("textView");
  $("formatHint").textContent = FORMAT_HINT[currentFormat];
  $("optimizeArea").style.display = currentFormat === "optimized" ? "block" : "none";
  $("optimizeBtn").textContent = optRaw ? "Re-optimize" : "Optimize prompt";

  const diffContainer = $("diffBadgeContainer");
  if (currentFormat === "optimized" && optRaw && (sectionsToRaw(currentSections) || currentRaw)) {
    const origLen = (sectionsToRaw(currentSections) || currentRaw).length;
    const optLen = optRaw.length;
    if (origLen > optLen) {
      const diffChars = origLen - optLen;
      const pct = Math.round((diffChars / origLen) * 100);
      $("diffBadgeText").textContent = `${pct}% more compact · Reduced ${diffChars} characters`;
      diffContainer.style.display = "block";
    } else {
      diffContainer.style.display = "none";
    }
  } else {
    diffContainer.style.display = "none";
  }

  if (currentFormat === "prompt") {
    tv.style.display = "none";
    sv.style.display = "block";
    renderCards(currentSections, true, currentRaw);
  } else if (currentFormat === "raw") {
    tv.style.display = "none";
    sv.style.display = "block";
    renderCards(rawSections, true, rawRaw);
  } else if (currentFormat === "natural") {
    sv.style.display = "none";
    tv.style.display = "block";
    tv.textContent = buildNatural(currentSections, currentRaw);
  } else if (currentFormat === "optimized") {
    tv.style.display = "none";
    sv.style.display = "block";
    if (!optRaw) {
      sv.innerHTML = '<div class="list-sub" style="text-align:center;padding:24px 8px;">Prompt has not been optimized yet. Tap Optimize prompt below.</div>';
    } else {
      renderCards(optSections, false, optRaw);
    }
  } else {
    sv.style.display = "none";
    tv.style.display = "block";
    tv.textContent = optRaw
      ? buildJson(optSections, optRaw, "optimized")
      : buildJson(currentSections, currentRaw, "skeleton");
  }
  updateOutputCharCount();
}

function getFormattedText() {
  if (currentFormat === "prompt") return hasSections(currentSections) ? sectionsToRaw(currentSections) : currentRaw;
  if (currentFormat === "raw") return hasSections(rawSections) ? sectionsToRaw(rawSections) : rawRaw;
  if (currentFormat === "natural") return buildNatural(currentSections, currentRaw);
  if (currentFormat === "optimized") return optRaw;
  return optRaw
    ? buildJson(optSections, optRaw, "optimized")
    : buildJson(currentSections, currentRaw, "skeleton");
}

function updateOutputCharCount() {
  const n = getFormattedText().length;
  const el = $("outputCharCount");
  el.textContent = `${n} / ~${currentTarget} chars`;
  el.style.color = n > currentTarget * 1.15 ? "#e5a93c" : "var(--muted)";
}

const FORMAT_LABEL = {
  prompt: "Prompt", natural: "Natural prompt", optimized: "Optimized prompt", json: "JSON", raw: "RAW prompt"
};

function copyFullPrompt() {
  const txt = getFormattedText();
  if (!txt) { showToast("No active prompt to copy"); return; }
  copyToClipboard(txt, FORMAT_LABEL[currentFormat] + " copied to clipboard");
}

// Bottom-Sheet Persistent Architecture
function expandOutput() {
  const card = $("outputCard");
  const backdrop = $("outputBackdrop");
  const dock = $("minimizedDock");
  
  card.classList.add("expanded");
  card.setAttribute("aria-hidden", "false");
  backdrop.style.display = "block";
  dock.style.display = "none";
  const minimizeButton = card.querySelector(".sheet-drag-pill");
  if (minimizeButton) minimizeButton.focus();
  syncFormatTabs();
  renderFormat();
}

function minimizeOutput() {
  const card = $("outputCard");
  const backdrop = $("outputBackdrop");
  const dock = $("minimizedDock");
  
  card.classList.remove("expanded");
  card.setAttribute("aria-hidden", "true");
  backdrop.style.display = "none";

  const hasContent = (activeOutputType === "raw" && (rawRaw || hasSections(rawSections))) ||
                      (activeOutputType === "full" && (currentRaw || hasSections(currentSections)));

  if (hasContent) {
    $("dockTitle").textContent = activeOutputType === "raw" ? "RAW Prompt Ready" : "Master Prompt Ready";
    dock.style.display = "flex";
    dock.focus();
  } else {
    dock.style.display = "none";
  }
}

function clearOutputCompletely() {
  setSkeleton("");
  rawSections = {};
  rawRaw = "";
  optSections = {};
  optRaw = "";
  minimizeOutput();
  $("minimizedDock").style.display = "none";
  $("progressBox").style.display = "none";
  showToast("Output dismissed & cleared");
}

