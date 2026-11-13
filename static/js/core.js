// Shared helpers used by all classic-script modules. Keep this file loaded first.
const $ = id => document.getElementById(id);
const uid = () => (window.crypto && crypto.randomUUID)
  ? crypto.randomUUID()
  : Date.now().toString(36) + Math.random().toString(36).slice(2);

function triggerHaptic(duration = 10) {
  if ("vibrate" in navigator) {
    try { navigator.vibrate(duration); } catch (e) {}
  }
}

function showToast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => { t.style.display = "none"; }, 2200);
}

let lastClickedBtn = null;
document.addEventListener("click", e => {
  lastClickedBtn = e.target && e.target.closest ? e.target.closest("button") : null;
}, true);

function flashCopied(btn) {
  if (!btn) return;
  if (!btn.dataset.label) btn.dataset.label = btn.textContent;
  btn.textContent = "Copied";
  btn.classList.add("is-copied");
  clearTimeout(btn._copyT);
  btn._copyT = setTimeout(() => {
    btn.textContent = btn.dataset.label;
    btn.classList.remove("is-copied");
  }, 1400);
}

function copyToClipboard(text, msg) {
  const btn = lastClickedBtn;
  navigator.clipboard.writeText(text).then(
    () => {
      triggerHaptic(12);
      showToast(msg);
      flashCopied(btn);
    },
    () => showToast("Failed to copy")
  );
}


function getStorage(key) {
  try {
    const v = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(v) ? v : [];
  } catch { return []; }
}

function setStorage(key, arr) {
  localStorage.setItem(key, JSON.stringify(arr));
}

function formatMMSS(ms) {
  const s = Math.floor(ms / 1000);
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}
