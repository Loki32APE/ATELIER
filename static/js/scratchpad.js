/* Atelier Prompt Engine — scratchpad.js
   Split from the former static/script.js. Original source order is preserved. */
let activeAppearanceConfig = null;
let currentActiveField = null;
const selectedSettings = {};
const likedSettings = {};

function copyScratchPrompt() {
  const txt = ($("scratchMainPrompt").value || "").trim();
  if (!txt) { showToast("No synthesized prompt to copy"); return; }
  copyToClipboard(txt, "Scratch prompt copied to clipboard");
}

function clearRawKeywords(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  $("scratchpadInput").value = "";
  showToast("Raw keywords cleared");
}

function toggleScratchArea(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  const body = $("scratchBodyWrapper");
  const btn = $("scratchMinBtn");
  const isHidden = body.style.display === "none";
  body.style.display = isHidden ? "block" : "none";
  btn.textContent = isHidden ? "▼" : "▲";
}

function expandScratchCanvas() {
  const el = $("scratchMainPrompt");
  const isExpanded = el.classList.toggle("expanded");
  showToast(isExpanded ? "Canvas expanded (Full view)" : "Canvas minimized");
  el.focus();
}

function randomizeIdea() {
  const ideas = [
    "1970s Bollywood retro noir, moody amber lighting, heavy silk drape, melancholic gaze, 85mm prime lens",
    "High-fashion Vogue editorial, liquid glass sleek bun, brutalist sandstone studio, razor-sharp cheekbones",
    "Monsoon evening in Kolkata, wet road golden taxi reflection, organza saree, candid half-smile, atmospheric mist",
    "Royal Chettinad courtyard, antique temple jewellery, warm sunlight filtering through teak pillars, tranquil posture"
  ];
  const pick = ideas[Math.floor(Math.random() * ideas.length)];
  $("scratchpadInput").value = pick;
  showToast("Random aesthetic concept injected!");
}

function toggleMasterSettings(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  const body = $("masterSettingsBody");
  const arrow = $("masterSettingsArrow");
  const isOpen = body.style.display !== "none";
  body.style.display = isOpen ? "none" : "block";
  arrow.textContent = isOpen ? "▶" : "▼";
}let activeCameraConfig = null;

// Clear Main Canvas side utility button fix
function clearScratchCanvas() {
  const el = $("scratchMainPrompt");
  if (el) {
    el.value = "";
    const counter = $("scratchCharCount");
    if (counter) counter.textContent = "0 chars";
    triggerHaptic(10);
    showToast("Main prompt canvas cleared");
  }
}


// Comprehensive Multi-Catalog Loader with Intelligent Path Fallbacks
