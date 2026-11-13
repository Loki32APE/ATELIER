/* Atelier Prompt Engine — main.js
   Split from the former static/script.js. Original source order is preserved. */
// Vision Lab generation controller is loaded from vision-lab.js.\n\n// Live counter for scratch prompt
if ($("scratchMainPrompt")) {
  $("scratchMainPrompt").addEventListener("input", () => {
    $("scratchCharCount").textContent = $("scratchMainPrompt").value.length + " chars";
  });
}

// Service Worker for PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(err => {
      console.log('SW registration failed:', err);
    });
  });
}

function setStudioMode(mode) {
  const advanced = mode === "advanced";
  const page = $("tab-studio");
  if (!page) return;
  page.dataset.mode = advanced ? "advanced" : "basic";
  $("studioModeBasic").classList.toggle("active", !advanced);
  $("studioModeAdvanced").classList.toggle("active", advanced);
  $("studioModeBasic").setAttribute("aria-pressed", String(!advanced));
  $("studioModeAdvanced").setAttribute("aria-pressed", String(advanced));
  $("advancedControlsWrapper").style.display = advanced ? "block" : "none";
  $("advToggleBtn").classList.toggle("open", advanced);
  $("advToggleBtn").setAttribute("aria-expanded", String(advanced));
}

// Master Scratchpad prompt synthesis (legacy UI is still backed by the durable job API).
async function generateFromScratchpad() {
  const rawInput = $("scratchpadInput").value.trim();
  const ar = $("scAr").value;
  const style = $("scStyle").value;
  const detail = $("scDetail").value;
  const genBtn = document.querySelector(".generate-cta");
  const hasAttributes = Object.keys(selectedSettings).some(
    key => selectedSettings[key] && selectedSettings[key] !== "Any"
  );

  if (!rawInput && !hasAttributes) {
    showToast("Please enter raw keywords or select attributes below");
    return;
  }

  const resetButton = () => {
    if (!genBtn) return;
    genBtn.disabled = false;
    genBtn.textContent = "Generate";
  };

  if (genBtn) {
    genBtn.disabled = true;
    genBtn.textContent = "Synthesizing...";
  }
  triggerHaptic(15);
  showToast("Synthesizing master prompt...");

  try {
    const response = await fetch("/synthesize-scratch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        raw_keywords: rawInput,
        attributes: selectedSettings,
        style,
        ar,
        detail
      })
    });
    const data = await response.json().catch(() => ({
      error: `Server error (Code ${response.status})`
    }));
    if (!response.ok) throw new Error(data.error || "Synthesis request failed");
    if (!data.job_id || !data.access_token) {
      throw new Error("The server did not return a valid job session.");
    }

    pollJob(
      data.job_id,
      data.access_token,
      result => {
        resetButton();
        const finalPrompt = result.prompt || "";
        showScratchModel(result.optimizer_model);
        $("scratchMainPrompt").value = finalPrompt;
        $("scratchCharCount").textContent = finalPrompt.length + " chars";
        triggerHaptic([20, 50, 20]);
        showToast("Master prompt synthesized successfully!");
      },
      message => {
        resetButton();
        showToast(message || "Failed to synthesize prompt");
      }
    );
  } catch (error) {
    console.error("Scratchpad synthesis error:", error);
    resetButton();
    showToast(error.message || "Failed to synthesize prompt");
  }
}

function showScratchModel(modelId) {
  const count = document.getElementById("scratchCharCount");
  if (!count) return;
  let badge = document.getElementById("scratchModelBadge");
  if (!badge) {
    badge = document.createElement("span");
    badge.id = "scratchModelBadge";
    badge.style.cssText = "display:block;font-size:.68rem;color:#8c857a;margin-top:4px;text-align:right;letter-spacing:.04em;";
    count.parentNode.appendChild(badge);
  }
  badge.textContent = modelId ? "Model: " + modelId.replace(":free", "") : "";
}

// Workspace Initialization
refreshProfileDropdowns();
setDetail("balanced");
setStudioMode("basic");
updateModeHint();

// Init: drawer counts
updateDrawerCounts();

// ---- Patch helpers: info panel, generate state, top progress ----
function toggleInfoPanel() {
  const p = document.getElementById("infoPanel");
  if (!p) return;
  const open = p.style.display === "none";
  p.style.display = open ? "block" : "none";
  const button = document.getElementById("infoBtn");
  if (button) button.setAttribute("aria-expanded", String(open));
  if (!open) return;

  const studio = document.getElementById("tab-studio");
  const isStudio = studio && studio.style.display === "block";
  const title = document.getElementById("infoPanelTitle");
  const list = document.getElementById("infoSteps");
  if (!title || !list) return;
  title.textContent = isStudio ? "Vision Studio" : "Visual Lab";
  const items = isStudio
    ? ["Add a Look reference. Outfit is optional.", "Describe only the changes you want.", "Review the analysis, then generate and refine your prompt."]
    : ["Fill the brief sections that matter to your image.", "Add any instruction that must stay verbatim.", "Generate, review, edit and validate the prompt."];
  list.replaceChildren(...items.map((text, index) => {
    const item = document.createElement("li");
    const number = document.createElement("span");
    number.textContent = String(index + 1).padStart(2, "0");
    const copy = document.createElement("p");
    copy.textContent = text;
    item.append(number, copy);
    return item;
  }));
}

function closeInfoPanel() {
  const p = document.getElementById("infoPanel");
  if (p) p.style.display = "none";
  const button = document.getElementById("infoBtn");
  if (button) button.setAttribute("aria-expanded", "false");
}

function updateGenerateState() {
  const hasLook = !!files.look;
  const hasAny = hasLook || !!files.outfit;
  if (!busy) {
    const g = document.getElementById("genBtn");
    const r = document.getElementById("rawBtn");
    if (g) g.disabled = !hasAny;
    if (r) r.disabled = !hasLook;
  }
  const hint = document.getElementById("genHint");
  if (hint) hint.textContent = hasAny ? "" : "Add a reference photo to enable generation.";
}

(function setupTopProgress() {
  const pb = document.getElementById("progressBox");
  const bar = document.getElementById("topProgress");
  const st = document.getElementById("statusText");
  if (!pb || !bar) return;
  const sync = () => {
    const on = pb.style.display !== "none";
    bar.classList.toggle("on", on);
    if (st) st.classList.toggle("shimmer", on);
  };
  new MutationObserver(sync).observe(pb, { attributes: true, attributeFilter: ["style"] });
  sync();
})();

// Init
switchMainTab("landing");
updateGenerateState();

// ---- Catalog v1 loader (Scratchpad) ----
// Sub-step 3a: sirf data load karta hai, UI abhi nahi badalta.
