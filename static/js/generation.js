// Generation, optimization, polling and output completion flow.
function setDetail(level) {
  detail = level;
  ["fast", "balanced", "detailed"].forEach(l => { const button = $("det-" + l); button.classList.toggle("active", l === level); button.setAttribute("aria-pressed", String(l === level)); });
  const d = DETAIL[level];
  $("detailHint").textContent = `${d.label}: look ${d.look}px · outfit ${d.outfit}px · target ~${d.target} characters`;
}

function setBusy(on) {
  busy = on;
  $("genBtn").disabled = on || !(files.look || files.outfit);
  $("rawBtn").disabled = on || !files.look;
  $("genBtn").textContent = on ? "Synthesizing..." : "Generate Master Prompt";
  $("optimizeBtn").disabled = on;
  $("optimizeBtn").textContent = optRaw ? "Re-optimize" : "Optimize prompt";
}

function setStatus(msg, isError = false) {
  const el = $("statusText");
  el.textContent = msg;
  el.style.color = isError ? "var(--danger)" : "var(--champagne)";
}

function startTimer() {
  startTime = Date.now();
  $("timerText").textContent = "00:00";
  clearInterval(timerIv);
  timerIv = setInterval(() => { $("timerText").textContent = formatMMSS(Date.now() - startTime); }, 250);
}

function stopTimer() {
  clearInterval(timerIv);
  timerIv = null;
}

function stopPolling() {
  clearInterval(pollIv);
  pollIv = null;
  activeJobId = null;
}

function failJob(msg) {
  stopPolling();
  stopTimer();
  $("progressBox").style.display = "none";
  setBusy(false);
  setStatus(msg, true);
  if ($("studioAnalysisPanel") && $("studioAnalysisPanel").style.display !== "none") {
    const report = {
      status: "failed",
      score_note: "Analysis did not complete. Check the message below and retry the selected references.",
      notes: [msg],
      references: {
        look: { status: files.look ? "failed" : "not_used" },
        outfit: { status: files.outfit && activeOutputType !== "raw" ? "failed" : (activeOutputType === "raw" ? "excluded" : "not_used") }
      }
    };
    renderStudioAnalysis({ visual_analysis_status: "failed", reference_analysis: report });
  }
}


function renderStudioAnalysis(data = {}) {
  const panel = $("studioAnalysisPanel");
  if (!panel) return;
  panel.style.display = "block";
  const report = data.reference_analysis || {};
  const state = data.visual_analysis_status || report.status || "pending";
  const labels = {pending:"Waiting for analysis",analyzing:"Analyzing references…",ready:"Analysis complete",partial:"Partially analyzed · review recommended",failed:"Analysis failed · retry recommended"};
  $("studioAnalysisStatus").textContent = labels[state] || state;
  $("studioCoverageScore").textContent = Number.isFinite(report.coverage_score) ? report.coverage_score + "%" : "Not available";
  $("studioScoreNote").textContent = report.score_note || "Coverage measures returned analysis for selected references, not visual accuracy.";
  const refs = report.references || {};
  ["look","outfit"].forEach(role => {
    const item = refs[role] || {};
    const stateText = item.status || (state === "analyzing" ? "analyzing" : "pending");
    const stateLabel = {ready:"Ready",partial:"Partial · review",failed:"Failed",excluded:"Excluded in RAW",not_used:"Not selected",analyzing:"Analyzing",pending:"Pending"}[stateText] || stateText;
    $(role + "AnalysisState").textContent = stateLabel;
    $(role + "AnalysisSummary").textContent = item.summary || (stateText === "excluded" ? "RAW mode intentionally excludes the Outfit reference." : stateText === "failed" ? "No usable analysis was returned. Retry generation or replace this reference." : "Analysis details will appear here when available.");
  });
  const fillList = (containerId, listId, values) => {
    const box = $(containerId), list = $(listId);
    list.innerHTML = "";
    (values || []).forEach(value => { const li = document.createElement("li"); li.textContent = value; list.appendChild(li); });
    box.hidden = !(values || []).length;
  };
  fillList("studioConflictList","studioConflictItems",report.conflicts || []);
  fillList("studioAnalysisNotes","studioAnalysisNoteItems",report.notes || []);
  const retry = $("studioRetryAnalysis");
  if (retry) {
    const canRetry = ["partial", "failed"].includes(report.status || state) && Boolean(files.look || files.outfit);
    retry.hidden = !canRetry;
    retry.disabled = busy;
    retry.textContent = busy ? "Retrying analysis…" : "Retry selected references";
  }
}

function renderStudioQuality(quality = {}) {
  const panel = $("studioQualityReview");
  if (!panel) return;
  const warnings = quality.warnings || [];
  const suggestions = quality.suggestions || [];
  panel.hidden = !(warnings.length || suggestions.length);
  const status = $("studioQualityStatus");
  status.textContent = quality.status === "ready" ? "Passed" : "Review recommended";
  status.dataset.state = quality.status || "unknown";
  const fill = (id, values) => {
    const list = $(id);
    list.replaceChildren();
    values.forEach(value => {
      const item = document.createElement("li");
      item.textContent = value;
      list.appendChild(item);
    });
  };
  fill("studioQualityWarnings", warnings);
  fill("studioQualitySuggestionItems", suggestions);
  $("studioQualitySuggestions").hidden = !suggestions.length;
}

function retryStudioAnalysis() {
  if (busy) return;
  if (!files.look && !files.outfit) {
    showToast("Add a Look or Outfit reference before retrying.");
    return;
  }
  showToast("Re-running analysis for the selected references.");
  startJob(activeOutputType === "raw" ? "raw" : "full");
}

function pollJob(jobId, accessToken, onDone, onFail) {
  stopPolling();
  activeJobId = jobId;
  const deadline = Date.now() + MAX_POLL_MS;
  pollIv = setInterval(async () => {
    if (activeJobId !== jobId) return;
    if (Date.now() > deadline) { stopPolling(); onFail("Operation timed out. Please retry."); return; }

    let r, d;
    try {
      r = await fetch("/status/" + jobId, { headers: { "Authorization": "Bearer " + accessToken } });
      d = await r.json();
    } catch (e) {
      setStatus("Reconnecting to atelier worker...");
      return;
    }

    if (r.status === 404) { stopPolling(); onFail(d.error || "Job session expired."); return; }
    if (d.kind === "generate") renderStudioAnalysis(d);
    if (d.status === "running") setStatus((d.step || "Analyzing visual references") + "...");
    else if (d.status === "done") { stopPolling(); onDone(d); }
    else if (d.status === "error") { stopPolling(); onFail(d.error || "Execution failed."); }
  }, 2000);
}

function startGenerate() { 
  triggerHaptic(15);
  startJob("full"); 
}

async function startJob(output) {
  if (busy) return;
  const combinedDirectives = [ $("studioBrief")?.value || "", $("studioAdditional")?.value || "" ].filter(Boolean).join("\n");
  if (combinedDirectives.length > 1500) { showToast("Combined creative instructions must stay within 1500 characters."); return; }
  if (output === "raw") {
    if (!files.look) { showToast("Select a look reference photo for RAW output"); return; }
  } else if (!files.look && !files.outfit) {
    showToast("Select at least one reference photo");
    return;
  }

  activeOutputType = output;
  stopPolling();
  const sz = DETAIL[detail];
  const fd = new FormData();

  $("progressBox").style.display = "block";
  if ($("studioAnalysisPanel")) { $("studioAnalysisPanel").style.display = "block"; renderStudioAnalysis({visual_analysis_status:"pending"}); }
  setBusy(true);
  setStatus("Optimizing visual assets...");
  startTimer();

  try {
    if (files.look) fd.append("image1", await shrinkImage(files.look, sz.look), "look.jpg");
    if (output === "full" && files.outfit) fd.append("image2", await shrinkImage(files.outfit, sz.outfit), "outfit.jpg");
    fd.append("subject_text", $("subjectText").value);
    fd.append("hair_text", $("hairText").value);
    fd.append("pose_text", $("poseText").value);
    fd.append("outfit_override", $("outfitOverride").value);
    const brief = $("studioBrief")?.value || "";
    const extra = $("studioAdditional")?.value || "";
    fd.append("additional_instructions", [brief, extra].filter(Boolean).join("\n"));
    fd.append("detail", detail);
    fd.append("output", output);

    setStatus("Dispatching job to vision model...");
    const resp = await fetch("/generate", { method: "POST", body: fd });
    let data;
    try {
      data = await resp.json();
    } catch {
      data = { error: `Server returned unexpected response code ${resp.status}.` };
    }
    if (!resp.ok) throw new Error(data.error || "Failed to initiate generation");
    pollJob(data.job_id, data.access_token, output === "raw" ? finishRaw : finishGenerate, failJob);
  } catch (err) {
    failJob(err.message);
  }
}

function finishGenerate(d) {
  stopTimer();
  $("progressBox").style.display = "none";
  setBusy(false);
  triggerHaptic([20, 50, 20]);
  const used = DETAIL[d.detail] || DETAIL[detail];
  lastMode = d.mode || lastMode;
  lastDetail = d.detail || detail;
  currentTarget = used.target;
  setSkeleton(d.prompt);
  // Compact prompt ab generate ke saath hi aata hai (Optimize button ki zaroorat nahi)
  if (d.compact) {
    optRaw = d.compact;
    optSections = parseLabeled(d.compact);
    if (!hasSections(optSections)) optSections = {};
    $("optimizeBtn").style.display = "none";
  } else {
    $("optimizeBtn").style.display = "";
  }
  $("modelBadge").textContent = `${used.label} · Nemotron 3.5 VL`;
  renderStudioAnalysis(d);
  renderStudioQuality(d.studio_quality || {});
  setStatus(d.studio_quality?.status === "needs_review" ? "Master prompt ready · review recommended" : "Master prompt ready · " + $("timerText").textContent);
  if (d.compact_warnings && d.compact_warnings.length) {
    setStatus("Warning: " + d.compact_warnings.join(" | "), true);
  }
  saveToHistory(sectionsToRaw(currentSections) || currentRaw);
  
  activeOutputType = "full";
  configureTabVisibility();
  currentFormat = "prompt";
  expandOutput();
}

function finishRaw(d) {
  stopTimer();
  $("progressBox").style.display = "none";
  setBusy(false);
  triggerHaptic([20, 50, 20]);
  const used = DETAIL[d.detail] || DETAIL[detail];
  currentTarget = used.target;
  rawRaw = (d.prompt || "").trim();
  rawSections = parseLabeled(rawRaw);
  renderStudioAnalysis(d);
  renderStudioQuality(d.studio_quality || {});
  setStatus(d.studio_quality?.status === "needs_review" ? "RAW prompt ready · review recommended" : "RAW prompt ready · " + $("timerText").textContent);
  
  activeOutputType = "raw";
  configureTabVisibility();
  currentFormat = "raw";
  expandOutput();
}

function configureTabVisibility() {
  if (activeOutputType === "raw") {
    $("outputHeadingTitle").textContent = "RAW Prompt";
    $("fmt-prompt").style.display = "none";
    $("fmt-natural").style.display = "none";
    $("fmt-optimized").style.display = "none";
    $("fmt-json").style.display = "none";
    $("fmt-raw").style.display = "block";
  } else {
    $("outputHeadingTitle").textContent = "Master Prompt";
    $("fmt-prompt").style.display = "block";
    $("fmt-natural").style.display = "block";
    $("fmt-optimized").style.display = "block";
    $("fmt-json").style.display = "block";
    $("fmt-raw").style.display = "none";
  }
}

async function startOptimize() {
  if (busy) return;
  const skeleton = hasSections(currentSections) ? sectionsToRaw(currentSections) : currentRaw;
  if (!skeleton) { showToast("Generate a prompt prior to optimization"); return; }

  setBusy(true);
  $("progressBox").style.display = "block";
  setStatus("Optimizing editorial synthesis...");
  startTimer();

  try {
    const resp = await fetch("/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skeleton, mode: lastMode, detail: lastDetail })
    });
    let data;
    try {
      data = await resp.json();
    } catch {
      data = { error: `Server returned unexpected response code ${resp.status}.` };
    }
    if (!resp.ok) throw new Error(data.error || "Optimization service unavailable");
    pollJob(data.job_id, data.access_token, finishOptimize, failJob);
  } catch (err) {
    failJob(err.message);
  }
}

function finishOptimize(d) {
  stopTimer();
  $("progressBox").style.display = "none";
  setBusy(false);
  triggerHaptic([20, 40, 20]);
  const text = (d.prompt || "").trim();
  const parsed = parseLabeled(text);
  if (hasSections(parsed)) {
    optSections = mergeOptimized(parsed);
    optRaw = sectionsToRaw(optSections);
  } else {
    optSections = {};
    optRaw = text;
  }
  let msg = "Optimized prompt ready · " + $("timerText").textContent;
  if (d.optimizer_model) msg += " · " + d.optimizer_model.split("/").pop();
  setStatus(msg);
  if (d.over_budget) {
    setStatus("Warning: " + (d.warnings || []).join(" | "), true);
  } else if (d.warnings && d.warnings.length) {
    showToast(d.warnings[0]);
  }
  currentFormat = "optimized";
  syncFormatTabs();
  renderFormat();
}

function mergeOptimized(opt) {
  const merged = {};
  LABELS.forEach(lbl => {
    if (opt[lbl] && opt[lbl].trim()) merged[lbl] = opt[lbl].trim();
  });
  return merged;
}

