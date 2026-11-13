/* Shared catalog access for all Atelier browser workspaces.
 * All catalog JSON requests must pass through this service.
 */
(function (global) {
  "use strict";

  const ROOT = "/static/Catalog/";
  const FILE_PATH = /^\/static\/Catalog\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+\.json$/;
  const SEGMENT = /^[A-Za-z0-9_-]+$/;
  const cache = new Map();
  const pending = new Map();
  let cacheGeneration = 0;

  function catalogPath(path) {
    if (typeof path !== "string" || !FILE_PATH.test(path)) {
      throw new TypeError("Catalog paths must be JSON files inside /static/Catalog/.");
    }
    return path;
  }

  function catalogSegment(value, label) {
    if (typeof value !== "string" || !SEGMENT.test(value)) {
      throw new TypeError("Invalid catalog " + label + ".");
    }
    return value;
  }

  async function getJSON(path) {
    const url = catalogPath(path);
    if (cache.has(url)) return cache.get(url);
    if (pending.has(url)) return pending.get(url);

    // A shared request must not inherit one caller's AbortSignal: cancelling one
    // consumer must not cancel the same in-flight request for every other consumer.
    const generation = cacheGeneration;
    const request = (async () => {
      const response = await fetch(url, {
        headers: { Accept: "application/json" }
      });
      if (!response.ok) {
        throw new Error("Catalog request failed (" + response.status + "): " + url);
      }
      const data = await response.json();
      if (!data || typeof data !== "object") {
        throw new TypeError("Catalog JSON must contain an object or array: " + url);
      }
      if (generation === cacheGeneration) cache.set(url, data);
      return data;
    })();

    pending.set(url, request);
    try {
      return await request;
    } finally {
      // Do not let an older request erase a newer request after clearCache().
      if (pending.get(url) === request) pending.delete(url);
    }
  }

  async function loadThemeCatalog() {
    const pair = await Promise.all([
      getJSON(ROOT + "global.json"),
      getJSON(ROOT + "index.json")
    ]);
    const globalCatalog = pair[0];
    const index = pair[1];
    if (!globalCatalog || typeof globalCatalog !== "object" || Array.isArray(globalCatalog)) {
      throw new TypeError("Global catalog must be an object.");
    }
    if (!index || typeof index !== "object" || !Array.isArray(index.themes)) {
      throw new TypeError("Catalog index is missing its themes array.");
    }

    const themes = {};
    const errors = [];
    await Promise.all(index.themes.filter(item => item && item.enabled !== false).map(async item => {
      try {
        const id = catalogSegment(item.id, "theme id");
        if (typeof item.file !== "string" || !item.file.endsWith(".json")) {
          throw new TypeError("Invalid theme catalog file.");
        }
        const path = catalogPath(ROOT + item.file);
        themes[id] = await getJSON(path);
      } catch (error) {
        errors.push((item && item.id ? String(item.id) + ": " : "") + error.message);
      }
    }));
    return { global: globalCatalog, index, themes, errors };
  }

  async function loadLayer4Catalog() {
    const manifest = await getJSON(ROOT + "layer4.json");
    if (!manifest || typeof manifest !== "object" || !Array.isArray(manifest.categories)) {
      throw new TypeError("Layer 4 manifest is missing its categories array.");
    }

    const byCategory = {};
    const byId = {};
    const errors = [];
    const jobs = [];

    manifest.categories.forEach(category => {
      let categoryId;
      try {
        if (!category || !Array.isArray(category.files)) {
          throw new TypeError("Layer 4 manifest contains an invalid category.");
        }
        categoryId = catalogSegment(category.id, "category id");
      } catch (error) {
        errors.push(error.message);
        return;
      }
      if (Object.prototype.hasOwnProperty.call(byCategory, categoryId)) {
        errors.push("Layer 4 manifest contains duplicate category: " + categoryId);
        return;
      }
      byCategory[categoryId] = {};
      category.files.forEach(file => {
        jobs.push((async () => {
          try {
            const fileId = catalogSegment(file, "file id");
            const path = catalogPath(ROOT + categoryId + "/" + fileId + ".json");
            const data = await getJSON(path);
            byCategory[categoryId][fileId] = data;
            (Array.isArray(data.items) ? data.items : []).forEach(item => {
              if (item && typeof item.id === "string" && item.id) byId[item.id] = item;
            });
          } catch (error) {
            errors.push(categoryId + "/" + String(file) + ": " + error.message);
          }
        })());
      });
    });

    await Promise.all(jobs);
    return { manifest, byCategory, byId, errors };
  }

  async function loadCameraCatalog() {
    const catalog = await getJSON(ROOT + "camera.json");
    if (!catalog.devices || typeof catalog.devices !== "object" || Array.isArray(catalog.devices)) {
      throw new TypeError("Camera catalog is missing its devices object.");
    }
    Object.entries(catalog.devices).forEach(([id, device]) => {
      if (!device || !Array.isArray(device.lenses)) {
        throw new TypeError("Camera catalog device is missing its lenses array: " + id);
      }
    });
    return catalog;
  }

  async function loadVisualLabCatalog() {
    const catalog = await getJSON(ROOT + "visual_lab/modules.json");
    if (!catalog.modules || typeof catalog.modules !== "object" || Array.isArray(catalog.modules)) {
      throw new TypeError("Visual Lab catalog is missing its modules object.");
    }
    return catalog;
  }

  function clearCache() {
    cacheGeneration += 1;
    cache.clear();
    pending.clear();
  }

  global.AtelierCatalogService = Object.freeze({
    root: ROOT,
    getJSON,
    loadThemeCatalog,
    loadLayer4Catalog,
    loadCameraCatalog,
    loadVisualLabCatalog,
    clearCache
  });
})(window);
