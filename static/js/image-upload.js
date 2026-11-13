// Image upload, preview, compression and lightbox handlers.
const previewObjectUrls = { look: null, outfit: null };

function releasePreviewUrl(slot) {
  const previousUrl = previewObjectUrls[slot];
  if (previousUrl) {
    URL.revokeObjectURL(previousUrl);
    previewObjectUrls[slot] = null;
  }
}

const imageSlotSuffix = slot => slot === "look" ? "Look" : "Outfit";

function shrinkImage(file, maxSide) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      canvas.getContext("2d").drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      canvas.toBlob(
        b => b ? resolve(b) : reject(new Error("Image compression failed")),
        "image/jpeg",
        0.9
      );
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Unable to load asset")); };
    img.src = url;
  });
}

function handleFile(slot, file) {
  if (!file) return;
  const allowedImageTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
  if (!allowedImageTypes.has(file.type)) {
    showToast("Use a JPEG, PNG, or WebP image.");
    const input = $("file" + imageSlotSuffix(slot));
    if (input) input.value = "";
    return;
  }
  if (file.size > 4 * 1024 * 1024) {
    showToast("Each reference image must be 4 MB or smaller.");
    const input = $("file" + imageSlotSuffix(slot));
    if (input) input.value = "";
    return;
  }
  if (busy) {
    const input = $("file" + imageSlotSuffix(slot));
    if (input) input.value = "";
    showToast("Please wait until the current analysis finishes.");
    return;
  }
  resetStudioAnalysisForReferenceChange();
  files[slot] = file;
  const s = imageSlotSuffix(slot);
  const prev = $("prev" + s);
  releasePreviewUrl(slot);
  previewObjectUrls[slot] = URL.createObjectURL(file);
  prev.src = previewObjectUrls[slot];
  prev.style.display = "block";
  $("placeholder" + s).style.display = "none";
  $("clear" + s).style.display = "flex";
  $("zoom" + s).style.display = "flex";
  updateModeHint();
}

function clearImage(ev, slot) {
  ev.stopPropagation();
  if (busy) { showToast("Please wait until the current analysis finishes."); return; }
  resetStudioAnalysisForReferenceChange();
  files[slot] = null;
  releasePreviewUrl(slot);
  const s = imageSlotSuffix(slot);
  $("file" + s).value = "";
  $("prev" + s).removeAttribute("src");
  $("prev" + s).style.display = "none";
  $("placeholder" + s).style.display = "block";
  $("clear" + s).style.display = "none";
  $("zoom" + s).style.display = "none";
  updateModeHint();
}

function openLightbox(ev, slot) {
  ev.stopPropagation();
  const s = imageSlotSuffix(slot);
  const src = $("prev" + s).src;
  if (src) {
    $("lightboxImg").src = src;
    $("lightboxModal").style.display = "flex";
  }
}

function closeLightbox() {
  $("lightboxModal").style.display = "none";
}

function currentMode() {
  if (files.look && files.outfit) return "BOTH";
  if (files.look) return "LOOK_ONLY";
  if (files.outfit) return "OUTFIT_ONLY";
  return "NONE";
}

function updateModeHint() {
  updateGenerateState();
  $("modeHint").textContent = MODE_TEXT[currentMode()];
}


function resetStudioAnalysisForReferenceChange() {
  const panel = $("studioAnalysisPanel");
  if (!panel) return;
  panel.style.display = "none";
  $("studioAnalysisStatus").textContent = "Reference changed. Analysis will refresh on the next generation.";
  $("studioCoverageScore").textContent = "Not available";
  ["look", "outfit"].forEach(role => {
    const state = $(role + "AnalysisState");
    if (state) { state.textContent = "Pending"; state.dataset.state = "pending"; }
    const summary = $(role + "AnalysisSummary");
    if (summary) summary.textContent = "Analysis will run with the next generation.";
  });
  ["studioConflictList", "studioAnalysisNotes"].forEach(id => {
    const box = $(id);
    if (!box) return;
    box.hidden = true;
    const list = box.querySelector("ul");
    if (list) list.replaceChildren();
  });
  const retry = $("studioRetryAnalysis");
  if (retry) retry.hidden = true;
}
