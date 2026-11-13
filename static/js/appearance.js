/* Atelier Prompt Engine — appearance.js
   Split from the former static/script.js. Original source order is preserved. */
// Appearance picker interactions; catalog loading is handled by the current theme module.

// Picker Bottom-Sheet Modal Logic
let pickerTriggerElement = null;


const pickerDialog = document.getElementById("pickerModal");
if (pickerDialog) pickerDialog.addEventListener("keydown", event => {
  if (pickerDialog.getAttribute("aria-hidden") === "true") return;
  if (event.key === "Escape") {
    event.preventDefault();
    closePickerModal();
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = [...pickerDialog.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), [role="radio"][tabindex="0"]'
  )].filter(el => el.offsetParent !== null);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});

function openPickerModal(field) {
  pickerTriggerElement = document.activeElement;
  currentActiveField = field;
  $("pickerTitleText").textContent = field.label;
  $("pickerSearchInput").value = "";
  renderPickerOptions(field.options, selectedSettings[field.id] || "Any");
  
  $("pickerBackdrop").style.display = "block";
  $("pickerModal").style.display = "flex";
  $("pickerModal").setAttribute("aria-hidden", "false");
  $("pickerSearchInput").focus();
  triggerHaptic(10);
}

function closePickerModal() {
  $("pickerBackdrop").style.display = "none";
  $("pickerModal").style.display = "none";
  $("pickerModal").setAttribute("aria-hidden", "true");
  currentActiveField = null;
  if (pickerTriggerElement && pickerTriggerElement.isConnected) pickerTriggerElement.focus();
  pickerTriggerElement = null;
}

function renderPickerOptions(options, selectedValue) {
  const list = $("pickerOptionsList");
  list.innerHTML = "";

  options.forEach(opt => {
    const item = document.createElement("div");
    const selected = opt === selectedValue;
    item.className = "picker-radio-item" + (selected ? " selected" : "");
    item.dataset.optionValue = opt.toLowerCase();
    item.setAttribute("role", "radio");
    item.setAttribute("aria-checked", String(selected));
    item.tabIndex = selected ? 0 : -1;

    const lbl = document.createElement("span");
    lbl.className = "picker-item-label";
    lbl.textContent = opt;

    const circle = document.createElement("div");
    circle.className = "picker-radio-circle";

    item.append(lbl, circle);

    item.onclick = () => {
      selectPickerOption(opt);
    };
    item.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectPickerOption(opt);
        return;
      }
      if (!["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"].includes(event.key)) return;
      event.preventDefault();
      const available = [...list.querySelectorAll('[role="radio"]')].filter(node => node.style.display !== "none");
      const current = available.indexOf(item);
      const forward = event.key === "ArrowDown" || event.key === "ArrowRight";
      const next = available[(current + (forward ? 1 : -1) + available.length) % available.length];
      if (next) { next.focus(); next.click(); }
    });

    list.appendChild(item);
  });
}

function filterPickerOptions(query) {
  const q = query.trim().toLowerCase();
  const items = document.querySelectorAll(".picker-radio-item");
  items.forEach(el => {
    const val = el.dataset.optionValue || "";
    el.style.display = val.includes(q) ? "flex" : "none";
  });
  const allItems = [...document.querySelectorAll("#pickerOptionsList [role='radio']")];
  const visible = allItems.filter(el => el.style.display !== "none");
  const activeItem = visible.find(el => el.getAttribute("aria-checked") === "true") || visible[0] || null;

  // Keep exactly one visible radio in the Tab order, including after repeated filtering.
  allItems.forEach(el => {
    el.tabIndex = el === activeItem ? 0 : -1;
  });
}

function selectPickerOption(val) {
  if (!currentActiveField) return;
  triggerHaptic(12);

  let finalVal = val;
  if (val === "Random") {
    const filtered = currentActiveField.options.filter(o => o !== "Any" && o !== "Random");
    finalVal = filtered[Math.floor(Math.random() * filtered.length)] || "Any";
    showToast(`Random selection: ${finalVal}`);
  }

  if (finalVal === "Any") {
    delete selectedSettings[currentActiveField.id];
  } else {
    selectedSettings[currentActiveField.id] = finalVal;
  }

  const pillText = $(`valText-${currentActiveField.id}`);
  if (pillText) pillText.textContent = finalVal;

  closePickerModal();
}function filterSettings(query) {
  const q = query.trim().toLowerCase();
  const items = document.querySelectorAll(".attr-row-item");
  items.forEach(el => {
    const searchKey = el.dataset.searchLabel || "";
    el.style.display = searchKey.includes(q) ? "flex" : "none";
  });
}

// Master Scratchpad Prompt Synthesizer
