/* Local, non-secret Atelier preferences. Provider credentials remain server-side. */
(function () {
  "use strict";
  const root = document.getElementById("tab-settings");
  if (!root) return;
  const KEY = "ape_settings_v1";
  const defaults = {
    displayName: "",
    profileNote: "",
    theme: "dark",
    accent: "vermilion",
    reducedMotion: false,
    defaultWorkspace: "home",
    defaultMode: "basic",
    targetModel: "",
    detail: "balanced",
    language: "English",
    preserveInstructions: true
  };

  function readSettings() {
    try {
      const stored = JSON.parse(localStorage.getItem(KEY) || "{}") || {};
      const settings = { ...defaults, ...stored };
      delete settings.viewMode;
      if (!['dark', 'light'].includes(settings.theme)) settings.theme = 'dark';
      settings.accent = 'vermilion';
      return settings;
    }
    catch (error) { return { ...defaults }; }
  }

  function setStatus(message) {
    const node = document.getElementById("settingsStatus");
    if (node) node.textContent = message || "";
  }

  function applySettings(settings) {
    const theme = settings.theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    const themeMeta = document.querySelector('meta[name="theme-color"]');
    if (themeMeta) themeMeta.content = theme === "light" ? "#F6F4EF" : "#111215";
    document.querySelectorAll("img[data-theme-dark][data-theme-light]").forEach(image => {
      image.src = image.getAttribute(`data-theme-${theme}`) || image.src;
    });
    const toggle = document.getElementById("themeToggleButton");
    if (toggle) {
      toggle.setAttribute("aria-label", theme === "light" ? "Switch to dark theme" : "Switch to light theme");
      toggle.title = theme === "light" ? "Switch to dark theme" : "Switch to light theme";
    }
    document.body.dataset.reducedMotion = settings.reducedMotion ? "true" : "false";
    const model = document.getElementById("vlModel");
    if (model && settings.targetModel) model.value = settings.targetModel;
    if (typeof setDetail === "function" && ["fast", "balanced", "detailed"].includes(settings.detail)) {
      setDetail(settings.detail);
    }
    if (settings.defaultWorkspace === "studio" && typeof setStudioMode === "function") {
      setStudioMode(settings.defaultMode === "advanced" ? "advanced" : "basic");
    }
  }

  window.toggleAtelierTheme = function () {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    const settings = readSettings();
    settings.theme = next;
    try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch (error) {}
    const selector = document.getElementById("settingTheme");
    if (selector) selector.value = next;
    applySettings(settings);
  };

  function collectSettings() {
    return {
      displayName: document.getElementById("settingDisplayName").value.trim(),
      profileNote: document.getElementById("settingProfileNote").value.trim(),
      theme: document.getElementById("settingTheme").value,
      accent: document.getElementById("settingAccent").value,
      reducedMotion: document.getElementById("settingReducedMotion").checked,
      defaultWorkspace: document.getElementById("settingDefaultWorkspace").value,
      defaultMode: document.getElementById("settingDefaultMode").value,
      targetModel: document.getElementById("settingTargetModel").value,
      detail: document.getElementById("settingDetail").value,
      language: document.getElementById("settingLanguage").value,
      preserveInstructions: true
    };
  }

  function populate(settings) {
    document.getElementById("settingDisplayName").value = settings.displayName || "";
    document.getElementById("settingProfileNote").value = settings.profileNote || "";
    document.getElementById("settingTheme").value = settings.theme || defaults.theme;
    document.getElementById("settingAccent").value = settings.accent || defaults.accent;
    document.getElementById("settingReducedMotion").checked = Boolean(settings.reducedMotion);
    document.getElementById("settingDefaultWorkspace").value = settings.defaultWorkspace || "home";
    document.getElementById("settingDefaultMode").value = settings.defaultMode || "basic";
    document.getElementById("settingTargetModel").value = settings.targetModel || "";
    document.getElementById("settingDetail").value = settings.detail || "balanced";
    document.getElementById("settingLanguage").value = settings.language || "English";
    document.getElementById("settingPreserveInstructions").checked = true;
  }

  function setSettingsView(view) {
    root.querySelectorAll("[data-settings-view]").forEach(button => {
      const active = button.dataset.settingsView === view;
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    root.querySelectorAll("[data-settings-panel]").forEach(panel => {
      panel.hidden = panel.dataset.settingsPanel !== view;
    });
  }
  window.setSettingsView = setSettingsView;

  async function updateStorageUsage() {
    const output = document.getElementById("settingsStorageUsage");
    let localBytes = 0;
    for (let index = 0; index < localStorage.length; index++) {
      const key = localStorage.key(index) || "";
      if (key.startsWith("pe_") || key.startsWith("ape_") || key.startsWith("atelier_")) {
        const value = localStorage.getItem(key) || "";
        localBytes += (key.length + value.length) * 2;
      }
    }
    let estimate = null;
    try {
      if (navigator.storage && navigator.storage.estimate) estimate = await navigator.storage.estimate();
    } catch (error) {}
    const localLabel = (localBytes / 1024).toFixed(1) + " KB of local preferences and prompt data";
    output.textContent = estimate && estimate.usage != null
      ? localLabel + " · Browser storage usage: " + (estimate.usage / 1024 / 1024).toFixed(1) + " MB"
      : localLabel;
  }

  root.querySelectorAll("[data-settings-view]").forEach(button => {
    button.addEventListener("click", () => setSettingsView(button.dataset.settingsView));
  });

  document.getElementById("settingsSaveBtn").addEventListener("click", () => {
    const settings = collectSettings();
    try {
      localStorage.setItem(KEY, JSON.stringify(settings));
      applySettings(settings);
      setStatus("Settings saved on this device.");
      showToast("Atelier settings saved.");
    } catch (error) {
      setStatus("Settings could not be saved. Browser storage may be full or unavailable.");
    }
  });

  document.getElementById("settingsExportBtn").addEventListener("click", () => {
    if (typeof exportBackup === "function") exportBackup();
    else setStatus("Backup export is not available.");
  });

  document.getElementById("settingsImportInput").addEventListener("change", event => {
    try {
      if (typeof importBackup === "function") importBackup(event.target.files[0]);
      else setStatus("Backup import is not available.");
    } finally {
      event.target.value = "";
    }
  });

  document.getElementById("settingsClearHistoryBtn").addEventListener("click", () => {
    if (!confirm("Clear all generation history from this device?")) return;
    localStorage.setItem("pe_history", "[]");
    if (typeof renderLibrary === "function") renderLibrary();
    if (typeof updateDrawerCounts === "function") updateDrawerCounts();
    setStatus("Generation history cleared.");
  });

  document.getElementById("settingsResetBtn").addEventListener("click", () => {
    if (!confirm("Reset all Atelier data stored in this browser? This also deletes local reference images and cannot be undone.")) return;
    [
      "pe_looks", "pe_history", "pe_subjects", "pe_hairs", "pe_poses",
      "ape_projects", "ape_settings_v1", "ape_view_mode", "atelier_vision_lab_profiles_v1"
    ].forEach(key => localStorage.removeItem(key));
    setStatus("Local Atelier data reset. Reloading the workspace…");
    try {
      if (!("indexedDB" in window)) { window.location.reload(); return; }
      const request = indexedDB.deleteDatabase("AtelierLibraryDB");
      request.onsuccess = () => window.location.reload();
      request.onerror = () => window.location.reload();
      request.onblocked = () => setStatus("Close other Atelier tabs to finish clearing local reference storage.");
    } catch (error) { window.location.reload(); }
  });

  const settings = readSettings();
  populate(settings);
  setSettingsView("profile");
  applySettings(settings);
  updateStorageUsage();
  window.ATELIER_SETTINGS = Object.freeze({ read: readSettings });
})();
