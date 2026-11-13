/* Unified Library workspace. Keeps legacy pe_looks and pe_history data readable. */
(function () {
  "use strict";
  const root = document.getElementById("tab-library");
  if (!root) return;

  const PROJECT_KEY = "ape_projects";
  const DB_NAME = "AtelierLibraryDB";
  const DB_VERSION = 1;
  const REFERENCE_STORE = "references";
  let activeView = "prompts";
  const selectedPrompts = new Set();
  const selectedHistory = new Set();
  const selectedReferences = new Set();
  let referenceUrls = [];

  const byId = id => document.getElementById(id);
  const readArray = key => {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "[]");
      return Array.isArray(value) ? value : [];
    } catch (error) { return []; }
  };
  const writeArray = (key, value) => localStorage.setItem(key, JSON.stringify(value));
  const setStatus = message => { byId("libraryStatus").textContent = message || ""; };

  function prompts() {
    const current = readArray("pe_looks");
    let changed = false;
    const normalized = current.map(item => {
      if (!item || typeof item !== "object") return item;
      const next = { ...item };
      if (!next.id) { next.id = uid(); changed = true; }
      if (!next.versionGroupId) { next.versionGroupId = next.id; changed = true; }
      if (!Number.isInteger(next.version) || next.version < 1) { next.version = 1; changed = true; }
      if (typeof next.favorite !== "boolean") { next.favorite = false; changed = true; }
      if (typeof next.projectId !== "string") { next.projectId = ""; changed = true; }
      return next;
    });
    if (changed) writeArray("pe_looks", normalized);
    return normalized.filter(item => item && typeof item === "object");
  }

  function projects() {
    return readArray(PROJECT_KEY).filter(item => item && typeof item.name === "string");
  }

  function refreshProjectFilter() {
    const select = byId("libraryProjectFilter");
    const current = select.value;
    select.replaceChildren(new Option("All projects", ""));
    projects().forEach(project => select.add(new Option(project.name, project.id)));
    if ([...select.options].some(option => option.value === current)) select.value = current;
  }

  function empty(container, message) {
    container.replaceChildren();
    const node = document.createElement("div");
    node.className = "library-empty";
    node.textContent = message;
    container.appendChild(node);
  }

  function button(label, className, handler) {
    const element = document.createElement("button");
    element.type = "button";
    element.className = className || "btn btn-secondary btn-small";
    element.textContent = label;
    element.addEventListener("click", handler);
    return element;
  }

  function updatePrompt(id, patch) {
    const list = prompts();
    const index = list.findIndex(item => item.id === id);
    if (index < 0) return;
    list[index] = { ...list[index], ...patch, updatedAt: new Date().toISOString() };
    writeArray("pe_looks", list);
    renderActiveView();
    if (typeof updateDrawerCounts === "function") updateDrawerCounts();
  }

  function renderProjects() {
    const container = byId("libraryProjectList");
    const allProjects = projects();
    container.replaceChildren();
    if (!allProjects.length) {
      empty(container, "No projects yet. Create a project above to organise your saved prompts.");
      return;
    }
    allProjects.forEach(project => {
      const card = document.createElement("article");
      card.className = "library-project-card";
      const title = document.createElement("h3");
      title.textContent = project.name;
      const count = prompts().filter(item => item.projectId === project.id).length;
      const description = document.createElement("p");
      description.textContent = (project.description || "Creative project") + " · " + count + " saved prompts";
      card.append(title, description);
      const actions = document.createElement("div");
      actions.className = "library-item-actions";
      actions.append(
        button("View prompts", "btn btn-secondary btn-small", () => {
          byId("libraryProjectFilter").value = project.id;
          setLibraryView("prompts");
        }),
        button("Rename project", "btn btn-secondary btn-small", () => {
          const nextName = window.prompt("Rename project", project.name);
          if (nextName === null) return;
          const name = nextName.trim();
          if (!name) return setStatus("Project name cannot be empty.");
          if (name.length > 60) return setStatus("Project name must be 60 characters or fewer.");
          writeArray(PROJECT_KEY, projects().map(item => item.id === project.id ? { ...item, name } : item));
          refreshProjectFilter();
          renderProjects();
          setStatus("Project renamed.");
        }),
        button("Delete project", "btn btn-danger btn-small", () => {
          if (!confirm("Delete this project? Saved prompts will remain in the Library.")) return;
          writeArray(PROJECT_KEY, projects().filter(item => item.id !== project.id));
          writeArray("pe_looks", prompts().map(item => item.projectId === project.id ? { ...item, projectId: "" } : item));
          refreshProjectFilter();
          renderProjects();
          setStatus("Project deleted. Its saved prompts were kept.");
        })
      );
      card.appendChild(actions);
      container.appendChild(card);
    });
  }

  function makePromptCard(item, view) {
    const card = document.createElement("article");
    card.className = "library-item-card";
    const head = document.createElement("div");
    head.className = "library-item-head";
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = selectedPrompts.has(item.id);
    check.setAttribute("aria-label", "Select " + (item.name || "saved prompt"));
    check.addEventListener("change", () => {
      if (check.checked) selectedPrompts.add(item.id);
      else selectedPrompts.delete(item.id);
      syncPromptSelectAll(visiblePromptItems(view));
    });
    const titleWrap = document.createElement("div");
    const title = document.createElement("div");
    title.className = "library-item-title";
    title.textContent = item.name || "Untitled prompt";
    const meta = document.createElement("div");
    meta.className = "library-item-meta";
    meta.textContent = (item.ts || item.createdAt || "Saved prompt") + " · v" + (item.version || 1);
    titleWrap.append(title, meta);
    head.append(check, titleWrap);
    const snippet = document.createElement("div");
    snippet.className = "library-item-snippet";
    snippet.textContent = item.prompt || "No prompt text stored.";
    const actions = document.createElement("div");
    actions.className = "library-item-actions";
    actions.append(
      button("Open", "btn btn-secondary btn-small", () => openSavedItem("pe_looks", item.id)),
      button("Copy", "btn btn-secondary btn-small", () => copyToClipboard(item.optimized || item.prompt || "", "Prompt copied to clipboard")),
      button(item.favorite ? "Favorited" : "Favorite", "btn btn-secondary btn-small", () => updatePrompt(item.id, { favorite: !item.favorite })),
      button("Rename prompt", "btn btn-secondary btn-small", () => {
        const nextName = window.prompt("Rename saved prompt", item.name || "");
        if (nextName === null) return;
        const name = nextName.trim();
        if (!name) return setStatus("Prompt name cannot be empty.");
        if (name.length > 120) return setStatus("Prompt name must be 120 characters or fewer.");
        updatePrompt(item.id, { name });
        setStatus("Prompt renamed.");
      }),
      button("Save as new version", "btn btn-secondary btn-small", () => openAsNewVersion(item)),
      button("Delete", "btn btn-danger btn-small", () => {
        if (!confirm("Delete this saved prompt?")) return;
        writeArray("pe_looks", prompts().filter(entry => entry.id !== item.id));
        selectedPrompts.delete(item.id);
        renderActiveView();
        if (typeof updateDrawerCounts === "function") updateDrawerCounts();
      })
    );
    const projectSelect = document.createElement("select");
    projectSelect.setAttribute("aria-label", "Assign prompt to project");
    projectSelect.add(new Option("No project", ""));
    projects().forEach(project => projectSelect.add(new Option(project.name, project.id)));
    projectSelect.value = item.projectId || "";
    projectSelect.addEventListener("change", () => updatePrompt(item.id, { projectId: projectSelect.value }));
    actions.appendChild(projectSelect);
    card.append(head, snippet, actions);
    return card;
  }

  function visiblePromptItems(view) {
    const query = (view === "favorites" ? "" : byId("librarySearch").value).trim().toLowerCase();
    const projectId = view === "favorites" ? "" : byId("libraryProjectFilter").value;
    let items = prompts();
    if (view === "favorites") items = items.filter(item => item.favorite);
    if (projectId) items = items.filter(item => item.projectId === projectId);
    if (query) items = items.filter(item => ((item.name || "") + " " + (item.prompt || "")).toLowerCase().includes(query));
    return items.sort((a, b) => String(b.updatedAt || b.ts || "").localeCompare(String(a.updatedAt || a.ts || "")));
  }

  function syncPromptSelectAll(items) {
    const selectAll = byId("librarySelectAllPrompts");
    const visibleIds = new Set(items.map(item => item.id));
    selectedPrompts.forEach(id => { if (!visibleIds.has(id)) selectedPrompts.delete(id); });
    const selectedCount = items.filter(item => selectedPrompts.has(item.id)).length;
    selectAll.checked = items.length > 0 && selectedCount === items.length;
    selectAll.indeterminate = selectedCount > 0 && selectedCount < items.length;
    syncBulkActionStates();
  }

  function syncBulkActionStates() {
    const promptItems = visiblePromptItems("prompts");
    const visiblePromptIds = new Set(promptItems.map(item => item.id));
    const selectedPromptCount = [...selectedPrompts].filter(id => visiblePromptIds.has(id)).length;
    byId("librarySelectAllPrompts").disabled = promptItems.length === 0;
    byId("libraryBulkFavoriteBtn").disabled = selectedPromptCount === 0;
    byId("libraryBulkFavoriteBtn").title = selectedPromptCount ? "Add selected prompts to Favorites" : "Select one or more prompts first";
    byId("libraryBulkDeleteBtn").disabled = selectedPromptCount === 0;
    byId("libraryBulkDeleteBtn").title = selectedPromptCount ? "Delete selected prompts" : "Select one or more prompts first";
    byId("libraryCompareBtn").disabled = selectedPromptCount !== 2;
    byId("libraryCompareBtn").title = selectedPromptCount === 2 ? "Compare the selected prompts" : "Select exactly two prompts or versions to compare";

    const historyItems = visibleHistoryItems();
    byId("librarySelectAllHistory").disabled = historyItems.length === 0;
    byId("libraryBulkDeleteHistory").disabled = selectedHistory.size === 0;
    byId("libraryClearHistory").disabled = readArray("pe_history").length === 0;
    byId("libraryBulkDeleteReferences").disabled = selectedReferences.size === 0;
  }

  function renderPrompts(view) {
    const container = view === "favorites" ? byId("libraryFavoriteList") : byId("libraryPromptList");
    const items = visiblePromptItems(view);
    syncPromptSelectAll(items);
    container.replaceChildren();
    if (!items.length) {
    empty(container, view === "favorites" ? "No favourites yet. Use Favorite on a prompt to bookmark it." : "No saved prompts match this view. Save a prompt from Studio to add it here.");
      return;
    }
    items.forEach(item => container.appendChild(makePromptCard(item, view)));
  }

  function openAsNewVersion(item) {
    window.ATELIER_VERSION_SOURCE_ID = item.id;
    openSavedItem("pe_looks", item.id);
    const name = byId("lookNameInput");
    if (name) name.value = item.name || "";
    const saveBox = byId("lookSaveBox");
    if (saveBox && saveBox.style.display !== "flex" && typeof toggleSaveBox === "function") toggleSaveBox("lookSaveBox");
    setStatus("Edit the prompt in Studio, then save it as a new version.");
  }

  function visibleHistoryItems() {
    const query = byId("libraryHistorySearch").value.trim().toLowerCase();
    return readArray("pe_history").filter(item => !query || ((item.name || "") + " " + (item.prompt || "")).toLowerCase().includes(query));
  }

  function syncHistorySelectAll(items) {
    const selectAll = byId("librarySelectAllHistory");
    const visibleIds = new Set(items.map(item => item.id));
    selectedHistory.forEach(id => { if (!visibleIds.has(id)) selectedHistory.delete(id); });
    const selectedCount = items.filter(item => selectedHistory.has(item.id)).length;
    selectAll.checked = items.length > 0 && selectedCount === items.length;
    selectAll.indeterminate = selectedCount > 0 && selectedCount < items.length;
    syncBulkActionStates();
  }

  function renderHistory() {
    const container = byId("libraryHistoryList");
    const items = visibleHistoryItems();
    syncHistorySelectAll(items);
    container.replaceChildren();
    if (!items.length) { empty(container, "No generation history matches this view."); return; }
    items.forEach(item => {
      const card = document.createElement("article");
      card.className = "library-item-card";
      const head = document.createElement("div");
      head.className = "library-item-head";
      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = selectedHistory.has(item.id);
      check.setAttribute("aria-label", "Select " + (item.name || "history item"));
      check.addEventListener("change", () => {
        if (check.checked) selectedHistory.add(item.id);
        else selectedHistory.delete(item.id);
        syncHistorySelectAll(visibleHistoryItems());
      });
      const title = document.createElement("div");
      title.className = "library-item-title";
      title.textContent = item.name || "Prompt history";
      const meta = document.createElement("div");
      meta.className = "library-item-meta";
      meta.textContent = item.ts || "";
      head.append(check, title);
      const snippet = document.createElement("div");
      snippet.className = "library-item-snippet";
      snippet.textContent = item.prompt || "";
      const actions = document.createElement("div");
      actions.className = "library-item-actions";
      actions.append(
        button("Open in Studio", "btn btn-secondary btn-small", () => openSavedItem("pe_history", item.id)),
        button("Copy", "btn btn-secondary btn-small", () => copyToClipboard(item.prompt || "", "History prompt copied")),
        button("Delete", "btn btn-danger btn-small", () => {
          writeArray("pe_history", readArray("pe_history").filter(entry => entry.id !== item.id));
          selectedHistory.delete(item.id);
          renderHistory();
        })
      );
      card.append(head, meta, snippet, actions);
      container.appendChild(card);
    });
  }

  function openReferenceDB() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) { reject(new Error("This browser does not support local reference storage.")); return; }
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(REFERENCE_STORE)) db.createObjectStore(REFERENCE_STORE, { keyPath: "id" });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("Could not open reference storage."));
    });
  }

  function referenceTransaction(mode, callback) {
    return openReferenceDB().then(db => new Promise((resolve, reject) => {
      let tx;
      try { tx = db.transaction(REFERENCE_STORE, mode); }
      catch (error) { db.close(); reject(error); return; }
      const store = tx.objectStore(REFERENCE_STORE);
      let request;
      try { request = callback(store); } catch (error) { db.close(); reject(error); return; }
      tx.oncomplete = () => { db.close(); resolve(request && request.result); };
      tx.onerror = () => { db.close(); reject(tx.error || new Error("Reference storage failed.")); };
      tx.onabort = () => { db.close(); reject(tx.error || new Error("Reference storage was interrupted.")); };
    }));
  }

  async function validImageFile(file) {
    const allowed = new Set(["image/jpeg", "image/png", "image/webp"]);
    if (!allowed.has(file.type) || file.size > 8 * 1024 * 1024) return false;
    const bytes = new Uint8Array(await file.slice(0, 12).arrayBuffer());
    const jpeg = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
    const png = bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47;
    const webp = String.fromCharCode(...bytes.slice(0, 4)) === "RIFF" && String.fromCharCode(...bytes.slice(8, 12)) === "WEBP";
    return (file.type === "image/jpeg" && jpeg) || (file.type === "image/png" && png) || (file.type === "image/webp" && webp);
  }

  async function saveReferenceFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const valid = [];
    for (const file of files) {
      if (await validImageFile(file)) valid.push(file);
      else setStatus("Skipped " + file.name + ": unsupported or invalid image file.");
    }
    if (!valid.length) return;

    const db = await openReferenceDB();
    try {
      const existing = await new Promise((resolve, reject) => {
        const request = db.transaction(REFERENCE_STORE, "readonly").objectStore(REFERENCE_STORE).count();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error || new Error("Could not count saved reference images."));
      });
      if (existing + valid.length > 100) {
        throw new Error("Reference Library is limited to 100 images on this device.");
      }
      await new Promise((resolve, reject) => {
        const tx = db.transaction(REFERENCE_STORE, "readwrite");
        const store = tx.objectStore(REFERENCE_STORE);
        valid.forEach(file => store.put({
          id: uid(),
          name: String(file.name || "Reference image").slice(0, 120),
          type: file.type,
          size: file.size,
          createdAt: new Date().toISOString(),
          blob: file
        }));
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error || new Error("Could not save reference images."));
        tx.onabort = () => reject(tx.error || new Error("Reference save was interrupted."));
      });
    } finally {
      db.close();
    }
    setStatus(valid.length + " reference image(s) saved on this device.");
    await renderReferences();
  }

  function syncReferenceSelectAll(records) {
    const selectAll = byId("librarySelectAllReferences");
    const items = Array.isArray(records) ? records : [];
    const selectedCount = items.filter(item => selectedReferences.has(item.id)).length;
    selectAll.checked = items.length > 0 && selectedCount === items.length;
    selectAll.indeterminate = selectedCount > 0 && selectedCount < items.length;
    const existingIds = new Set(items.map(item => item.id));
    selectedReferences.forEach(id => { if (!existingIds.has(id)) selectedReferences.delete(id); });
    byId("librarySelectAllReferences").disabled = items.length === 0;
    byId("libraryBulkDeleteReferences").disabled = selectedReferences.size === 0;
  }

  async function renderReferences() {
    const container = byId("libraryReferenceList");
    container.textContent = "Loading saved reference images…";
    referenceUrls.forEach(url => URL.revokeObjectURL(url));
    referenceUrls = [];
    try {
      const records = await referenceTransaction("readonly", store => store.getAll());
      syncReferenceSelectAll(records);
      container.replaceChildren();
      if (!records || !records.length) { empty(container, "No reference images saved yet. Add images above to build your local Reference Library."); return; }
      records.sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
      records.forEach(item => {
        const card = document.createElement("article");
        card.className = "library-reference-card";
        const image = document.createElement("img");
        image.alt = item.name || "Saved reference";
        const url = URL.createObjectURL(item.blob);
        referenceUrls.push(url);
        image.src = url;
        const name = document.createElement("div");
        name.className = "ref-name";
        name.textContent = item.name;
        const meta = document.createElement("div");
        meta.className = "ref-meta";
        meta.textContent = item.type + " · " + (item.size / 1024 / 1024).toFixed(1) + " MB · " + new Date(item.createdAt).toLocaleDateString();
        const selectLabel = document.createElement("label");
        selectLabel.className = "ref-select";
        const check = document.createElement("input");
        check.type = "checkbox";
        check.checked = selectedReferences.has(item.id);
        check.setAttribute("aria-label", "Select " + item.name);
        check.addEventListener("change", () => {
          if (check.checked) selectedReferences.add(item.id);
          else selectedReferences.delete(item.id);
          syncReferenceSelectAll(records);
        });
        selectLabel.append(check, document.createTextNode("Select"));
        const remove = button("Delete", "btn btn-danger btn-small", async () => {
          try {
            await referenceTransaction("readwrite", store => store.delete(item.id));
            selectedReferences.delete(item.id);
            await renderReferences();
            setStatus("Reference image deleted.");
          } catch (error) {
            setStatus("Could not delete reference image: " + (error.message || "Reference storage failed."));
          }
        });
        card.append(image, name, meta, selectLabel, remove);
        container.appendChild(card);
      });
    } catch (error) {
      empty(container, error.message || "Reference storage is unavailable in this browser.");
      byId("librarySelectAllReferences").disabled = true;
      byId("libraryBulkDeleteReferences").disabled = true;
      setStatus(error.message);
    }
  }

  function renderActiveView() {
    refreshProjectFilter();
    if (activeView === "projects") renderProjects();
    else if (activeView === "prompts") renderPrompts("prompts");
    else if (activeView === "favorites") renderPrompts("favorites");
    else if (activeView === "history") renderHistory();
    else if (activeView === "references") renderReferences();
    syncBulkActionStates();
  }

  function setLibraryView(view) {
    const allowed = ["projects", "prompts", "references", "favorites", "history"];
    if (!allowed.includes(view)) return;
    activeView = view;
    root.querySelectorAll("[data-library-view]").forEach(tab => {
      const active = tab.dataset.libraryView === view;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    root.querySelectorAll("[data-library-panel]").forEach(panel => {
      panel.hidden = panel.dataset.libraryPanel !== view;
    });
    renderActiveView();
  }

  function renderLibrary() {
    setLibraryView(activeView);
  }

  root.querySelectorAll("[data-library-view]").forEach(tab => tab.addEventListener("click", () => setLibraryView(tab.dataset.libraryView)));
  const libraryTabList = root.querySelector(".library-tabs");
  libraryTabList.addEventListener("keydown", event => {
    const supportedKeys = ["ArrowRight", "ArrowLeft", "Home", "End"];
    if (!supportedKeys.includes(event.key)) return;
    const tabs = [...root.querySelectorAll("[data-library-view]")];
    const current = tabs.indexOf(document.activeElement);
    if (current < 0 || !tabs.length) return;
    event.preventDefault();
    let nextIndex = current;
    if (event.key === "ArrowRight") nextIndex = (current + 1) % tabs.length;
    else if (event.key === "ArrowLeft") nextIndex = (current - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = tabs.length - 1;
    tabs[nextIndex].focus();
    tabs[nextIndex].click();
  });
  byId("libraryProjectForm").addEventListener("submit", event => {
    event.preventDefault();
    const name = byId("libraryProjectName").value.trim();
    if (!name) return;
    const list = projects();
    if (list.some(project => project.name.toLowerCase() === name.toLowerCase())) {
      setStatus("A project with that name already exists.");
      return;
    }
    list.unshift({ id: uid(), name, description: byId("libraryProjectDescription").value.trim(), createdAt: new Date().toISOString() });
    writeArray(PROJECT_KEY, list);
    byId("libraryProjectName").value = "";
    byId("libraryProjectDescription").value = "";
    setStatus("Project created.");
    renderProjects();
    refreshProjectFilter();
  });
  byId("librarySearch").addEventListener("input", () => {
    selectedPrompts.clear();
    byId("librarySelectAllPrompts").checked = false;
    renderPrompts("prompts");
  });
  byId("libraryProjectFilter").addEventListener("change", () => {
    selectedPrompts.clear();
    byId("librarySelectAllPrompts").checked = false;
    renderPrompts("prompts");
  });
  byId("libraryHistorySearch").addEventListener("input", () => {
    selectedHistory.clear();
    byId("librarySelectAllHistory").checked = false;
    renderHistory();
  });
  byId("librarySelectAllPrompts").addEventListener("change", event => {
    visiblePromptItems("prompts").forEach(item => event.target.checked ? selectedPrompts.add(item.id) : selectedPrompts.delete(item.id));
    renderPrompts("prompts");
  });
  byId("libraryBulkFavoriteBtn").addEventListener("click", () => {
    if (!selectedPrompts.size) return setStatus("Select at least one prompt first.");
    writeArray("pe_looks", prompts().map(item => selectedPrompts.has(item.id) ? { ...item, favorite: true } : item));
    selectedPrompts.clear();
    renderPrompts("prompts");
    setStatus("Selected prompts added to Favorites.");
  });
  byId("libraryBulkDeleteBtn").addEventListener("click", () => {
    if (!selectedPrompts.size) return setStatus("Select at least one prompt first.");
    if (!confirm("Delete the selected saved prompts?")) return;
    writeArray("pe_looks", prompts().filter(item => !selectedPrompts.has(item.id)));
    selectedPrompts.clear();
    renderPrompts("prompts");
    if (typeof updateDrawerCounts === "function") updateDrawerCounts();
    setStatus("Selected prompts deleted.");
  });
  byId("libraryCompareBtn").addEventListener("click", () => {
    const chosen = prompts().filter(item => selectedPrompts.has(item.id));
    if (chosen.length !== 2) return setStatus("Select exactly two saved prompts or versions to compare.");
    byId("libraryCompareLabelA").firstChild.textContent = (chosen[0].name || "Prompt A") + " · v" + (chosen[0].version || 1);
    byId("libraryCompareLabelB").firstChild.textContent = (chosen[1].name || "Prompt B") + " · v" + (chosen[1].version || 1);
    byId("libraryCompareA").value = chosen[0].prompt || "";
    byId("libraryCompareB").value = chosen[1].prompt || "";
    byId("libraryComparePanel").hidden = false;
  });
  byId("libraryCloseCompare").addEventListener("click", () => { byId("libraryComparePanel").hidden = true; });
  byId("libraryExportBtn").addEventListener("click", () => {
    if (typeof exportBackup === "function") exportBackup();
    else setStatus("Backup export is not available.");
  });
  byId("libraryReferenceUpload").addEventListener("change", async event => {
    try { await saveReferenceFiles(event.target.files); }
    catch (error) { setStatus(error.message || "Reference images could not be saved."); }
    event.target.value = "";
  });
  byId("librarySelectAllReferences").addEventListener("change", async event => {
    try {
      const records = await referenceTransaction("readonly", store => store.getAll());
      selectedReferences.clear();
      if (event.target.checked) (records || []).forEach(item => selectedReferences.add(item.id));
      renderReferences();
    } catch (error) { setStatus(error.message); }
  });
  byId("libraryBulkDeleteReferences").addEventListener("click", async () => {
    if (!selectedReferences.size) return setStatus("Select at least one reference image first.");
    if (!confirm("Delete the selected reference images from this device?")) return;
    const ids = [...selectedReferences];
    try {
      await referenceTransaction("readwrite", store => {
        ids.forEach(id => store.delete(id));
        return null;
      });
      selectedReferences.clear();
      await renderReferences();
      setStatus("Selected reference images deleted.");
    } catch (error) {
      setStatus("Could not delete selected reference images: " + (error.message || "Reference storage failed."));
    }
  });
  byId("librarySelectAllHistory").addEventListener("change", event => {
    visibleHistoryItems().forEach(item => event.target.checked ? selectedHistory.add(item.id) : selectedHistory.delete(item.id));
    renderHistory();
  });
  byId("libraryBulkDeleteHistory").addEventListener("click", () => {
    if (!selectedHistory.size) return setStatus("Select at least one history item first.");
    if (!confirm("Delete the selected history items?")) return;
    writeArray("pe_history", readArray("pe_history").filter(item => !selectedHistory.has(item.id)));
    selectedHistory.clear();
    renderHistory();
    setStatus("Selected history items deleted.");
  });
  byId("libraryClearHistory").addEventListener("click", () => {
    if (!confirm("Clear all generation history?")) return;
    writeArray("pe_history", []);
    selectedHistory.clear();
    renderHistory();
    setStatus("Generation history cleared.");
  });

  window.renderLibrary = renderLibrary;
  window.setLibraryView = setLibraryView;
  renderLibrary();
})();
