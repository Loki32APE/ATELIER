// UI navigation and reusable interface helpers. Requires core.js.
const SECTION_LABELS = {
  studio: "STUDIO", scratchpad: "VISUAL LAB", library: "LIBRARY", saved: "SAVED", history: "HISTORY",
  about: "ABOUT", contact: "HELP & FEEDBACK", settings: "SETTINGS", terms: "TERMS OF USE", privacy: "PRIVACY"
};
const PAGE_IDS = ["landing", "home", "studio", "scratchpad", "library", "saved", "history", "about", "contact", "settings", "terms", "privacy"];

function switchMainTab(tab) {
  if (tab === "saved") { window.ATELIER_LIBRARY_VIEW = "prompts"; tab = "library"; }
  if (tab === "history") { window.ATELIER_LIBRARY_VIEW = "history"; tab = "library"; }
  if (tab !== "studio") window.ATELIER_VERSION_SOURCE_ID = null;
  PAGE_IDS.forEach(t => {
    const el = document.getElementById("tab-" + t);
    if (el) el.style.display = (t === tab) ? "block" : "none";
  });

  // Header: Home par koi header nahi (logo hi brand hai), baaki pages par sirf section ka naam
  const isHome = tab === "home" || tab === "landing";
  document.body.dataset.activeTab = tab;
  const hdr = document.getElementById("appHeader");
  const label = document.getElementById("sectionLabel");
  if (hdr) hdr.style.display = isHome ? "none" : "";
  if (label) label.textContent = SECTION_LABELS[tab] || "";

  document.querySelectorAll(".drawer-item").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  closeDrawer();
  closeInfoPanel();
  if (tab === "library" && typeof renderLibrary === "function") {
    if (window.ATELIER_LIBRARY_VIEW && typeof setLibraryView === "function") setLibraryView(window.ATELIER_LIBRARY_VIEW);
    else renderLibrary();
  }
  if (tab === "saved" && typeof renderSavedLooks === "function") renderSavedLooks();
  if (tab === "history" && typeof renderHistory === "function") renderHistory();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function launchAtelierWorkspace() {
  let preferred = "home";
  try {
    const saved = JSON.parse(localStorage.getItem("ape_settings_v1") || "{}");
    if (["home", "studio", "scratchpad", "library"].includes(saved.defaultWorkspace)) preferred = saved.defaultWorkspace;
  } catch (_) {}
  switchMainTab(preferred);
}

function setLandingExample(mode, button) {
  const examples = {
    raw: { label: "A starting idea", text: "A woman in a dramatic red outfit, standing in an old palace." },
    compiled: { label: "A more directed prompt", text: "Editorial portrait of an adult woman in a deep vermilion silk sari with a fine woven border, standing in a quiet palace corridor. Three-quarter pose, warm window light from camera left, natural skin texture, restrained background detail, vertical composition." }
  };
  const example = examples[mode];
  if (!example) return;
  const label = document.getElementById("landingExampleLabel");
  const text = document.getElementById("landingExampleText");
  if (label) label.textContent = example.label;
  if (text) text.textContent = example.text;
  document.querySelectorAll(".landing-segment button").forEach(item => {
    const active = item === button;
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-pressed", String(active));
  });
}

function openProfileSettings() {
  switchMainTab("settings");
  if (typeof window.setSettingsView === "function") window.setSettingsView("profile");
  const field = document.getElementById("settingDisplayName");
  if (field) field.focus({ preventScroll: true });
}

function openModelSettings() {
  switchMainTab("settings");
  if (typeof window.setSettingsView === "function") window.setSettingsView("prompt");
  const field = document.getElementById("settingTargetModel");
  if (field) field.focus({ preventScroll: true });
}

function copySupportTemplate() {
  const report = [
    "Atelier Prompt Engine · 2.5",
    "Screen:",
    "Steps to reproduce:",
    "Expected result:",
    "What happened:",
    "Browser and screen size:"
  ].join("\n");
  copyToClipboard(report, "Issue template copied.");
}

function updateDrawerCounts() {
  const library = document.getElementById("drawerLibraryCount");
  const saved = document.getElementById("drawerSavedCount");
  const hist = document.getElementById("drawerHistoryCount");
  const looks = JSON.parse(localStorage.getItem("pe_looks") || "[]");
  const history = JSON.parse(localStorage.getItem("pe_history") || "[]");
  if (saved) saved.textContent = looks.length ? String(looks.length) : "";
  if (hist) hist.textContent = history.length ? String(history.length) : "";
  if (library) library.textContent = (looks.length + history.length) ? String(looks.length + history.length) : "";
}

function isMobileNavigation() {
  return window.matchMedia("(max-width: 760px)").matches;
}

function openDrawer() {
  const drawer = document.getElementById("drawer");
  const backdrop = document.getElementById("drawerBackdrop");
  const toggle = document.querySelector(".menu-btn");
  if (isMobileNavigation()) {
    drawer.classList.add("open");
    backdrop.style.display = "block";
  } else {
    document.body.classList.remove("sidebar-collapsed");
  }
  if (toggle) toggle.setAttribute("aria-expanded", "true");
}

function toggleDrawer() {
  if (isMobileNavigation()) {
    if (document.getElementById("drawer").classList.contains("open")) closeDrawer();
    else openDrawer();
  } else if (document.body.classList.contains("sidebar-collapsed")) {
    openDrawer();
  } else {
    document.body.classList.add("sidebar-collapsed");
    const toggle = document.querySelector(".menu-btn");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }
}

function closeDrawer() {
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawerBackdrop").style.display = "none";
  if (!isMobileNavigation()) document.body.classList.add("sidebar-collapsed");
  const toggle = document.querySelector(".menu-btn");
  if (toggle) toggle.setAttribute("aria-expanded", "false");
}

function syncDrawerToggleState() {
  const drawer = document.getElementById("drawer");
  const toggle = document.querySelector(".menu-btn");
  if (!drawer || !toggle) return;
  const isMobile = isMobileNavigation();
  if (isMobile) document.body.classList.remove("sidebar-collapsed");
  else if (!drawer.classList.contains("open")) document.body.classList.add("sidebar-collapsed");
  const isOpen = isMobile ? drawer.classList.contains("open") : !document.body.classList.contains("sidebar-collapsed");
  toggle.setAttribute("aria-expanded", String(isOpen));
}

let lastNavigationIsMobile = isMobileNavigation();
window.addEventListener("resize", () => {
  const isMobile = isMobileNavigation();
  if (isMobile !== lastNavigationIsMobile) {
    document.getElementById("drawer")?.classList.remove("open");
    const backdrop = document.getElementById("drawerBackdrop");
    if (backdrop) backdrop.style.display = "none";
    lastNavigationIsMobile = isMobile;
  }
  syncDrawerToggleState();
});

function updateCount(id, countId) {
  $(countId).textContent = $(id).value.length + " chars";
}

function toggleSaveBox(id) {
  const el = $(id);
  const closing = el.style.display === "flex";
  el.style.display = closing ? "none" : "flex";
  if (closing && id === "lookSaveBox") window.ATELIER_VERSION_SOURCE_ID = null;
  if (el.style.display === "flex") {
    const inp = el.querySelector("input");
    if (inp) inp.focus();
  }
}

function toggleAdvancedAccordion() {
  const wrapper = $("advancedControlsWrapper");
  const btn = $("advToggleBtn");
  const isOpen = wrapper.style.display === "block";
  wrapper.style.display = isOpen ? "none" : "block";
  btn.classList.toggle("open", !isOpen);
  btn.setAttribute("aria-expanded", String(!isOpen));
}

document.addEventListener("keydown", event => {
  const outputCard = $("outputCard");
  const outputOpen = outputCard && outputCard.getAttribute("aria-hidden") === "false";
  if (outputOpen && event.key === "Escape") {
    event.preventDefault();
    minimizeOutput();
    return;
  }
  if (event.key === "Escape") {
    const drawer = document.getElementById("drawer");
    const isMobile = isMobileNavigation();
    const isDrawerOpen = isMobile ? drawer?.classList.contains("open") : !document.body.classList.contains("sidebar-collapsed");
    if (isDrawerOpen) { event.preventDefault(); closeDrawer(); return; }
  }
  if (outputOpen && event.key === "Tab") {
    const focusable = [...outputCard.querySelectorAll(
      'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [contenteditable="true"], [tabindex="0"]'
    )].filter(element => element.offsetParent !== null);
    if (focusable.length) {
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    return;
  }
  if (event.key !== "Enter" && event.key !== " ") return;
  const dock = event.target.closest("#minimizedDock");
  if (dock) { event.preventDefault(); expandOutput(); return; }
  const upload = event.target.closest("#dropLook, #dropOutfit");
  if (upload) { event.preventDefault(); const input = upload.querySelector("input[type=file]"); if (input) input.click(); return; }
  const accordion = event.target.closest("#advToggleBtn");
  if (accordion) { event.preventDefault(); toggleAdvancedAccordion(); }
});

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", syncDrawerToggleState);
else syncDrawerToggleState();
