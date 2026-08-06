const state = { chips: [], modules: [], allocation: [], risks: [], alternatives: [], locks: {}, filter: "all", hasScanned: false, scan: null, comparison: null };
const $ = (id) => document.getElementById(id);
const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || "请求失败");
  return data;
}

function selectedModuleIds() {
  return [...document.querySelectorAll(".module-check:checked")].map((item) => item.value);
}

function payload() {
  return {
    schema_version: 2,
    project_name: $("projectName").value.trim() || "untitled_project",
    notes: $("notes").value.trim(),
    project_path: $("projectPath").value.trim(),
    use_detected_chip: true,
    chip_id: $("chipSelect").value,
    module_ids: selectedModuleIds(),
    allocation: state.allocation,
    locked_pins: state.locks,
    preferred_allocation: state.allocation,
    strategy: $("strategySelect").value,
    include_alternatives: true,
    alternative_count: 3,
  };
}

async function loadChips() {
  const selected = $("chipSelect").value;
  state.chips = (await api(`/api/chips?q=${encodeURIComponent($("chipSearch").value)}`)).chips;
  $("chipCount").textContent = state.chips.length;
  $("chipSelect").innerHTML = state.chips.map((chip) => `<option value="${escapeHtml(chip.id)}">${escapeHtml(chip.name)} · ${escapeHtml(chip.voltage)}</option>`).join("");
  if (state.chips.some((chip) => chip.id === selected)) $("chipSelect").value = selected;
}

async function loadModules() {
  const selected = new Set(selectedModuleIds());
  state.modules = (await api(`/api/modules?q=${encodeURIComponent($("moduleSearch").value)}`)).modules;
  $("moduleCount").textContent = state.modules.length;
  renderModules(selected);
}

function moduleIcon(module) {
  const id = module.id.toLowerCase();
  if (/oled|display/.test(id)) return "▤";
  if (/sd|flash/.test(id)) return "▰";
  if (/button|encoder/.test(id)) return "◎";
  if (/buzzer|motor|relay/.test(id)) return "ϟ";
  if (/lora|uart/.test(id)) return "⌁";
  return "◈";
}

function renderModules(selected = new Set()) {
  $("moduleList").innerHTML = state.modules.length ? state.modules.map((module, index) => {
    const checked = selected.has(module.id) || (!selected.size && index < 4);
    return `<label class="module-item">
      <input class="module-check" type="checkbox" value="${escapeHtml(module.id)}" ${checked ? "checked" : ""}>
      <span class="module-icon">${moduleIcon(module)}</span>
      <span class="module-info"><strong>${escapeHtml(module.name)}</strong><small>${escapeHtml(module.description || module.voltage || "硬件模块")}</small></span>
      <span class="check-ui">✓</span>
    </label>`;
  }).join("") : `<p class="no-match">没有匹配的模块</p>`;
  document.querySelectorAll(".module-check").forEach((item) => item.addEventListener("change", updateSelectedCount));
  updateSelectedCount();
}

function updateSelectedCount() {
  $("selectedCount").textContent = `已选 ${selectedModuleIds().length}`;
}

function renderAllocation() {
  $("allocationSummary").textContent = `${state.allocation.length} 条连接`;
  $("allocationBody").innerHTML = state.allocation.map((item, index) => { const key = `${item.module_id}:${item.module_pin}`; return `<tr>
    <td><label class="lock-control" title="锁定当前引脚"><input type="checkbox" class="pin-lock" data-key="${escapeHtml(key)}" ${state.locks[key] ? "checked" : ""}><span>⌾</span></label></td>
    <td><strong>${escapeHtml(item.module_name)}</strong><small>${escapeHtml(item.module_pin)}</small></td>
    <td><input data-index="${index}" class="pin-input" value="${escapeHtml(item.chip_pin)}" aria-label="${escapeHtml(item.module_name)} 引脚"></td>
    <td><code>${escapeHtml(item.function)}</code></td>
    <td><span class="pin-score ${Number(item.score) < 50 ? "low" : ""}">${item.score ?? "—"}</span></td>
    <td class="note-cell">${escapeHtml(item.note || "—")}</td>
  </tr>`; }).join("");
  document.querySelectorAll(".pin-lock").forEach((input) => input.addEventListener("change", () => {
    const row = state.allocation.find((item) => `${item.module_id}:${item.module_pin}` === input.dataset.key);
    if (input.checked && row?.chip_pin && row.chip_pin !== "未分配") state.locks[input.dataset.key] = row.chip_pin;
    else delete state.locks[input.dataset.key];
  }));
}

function renderAlternatives() {
  const section = $("alternativeSection");
  if (!state.alternatives.length) { section.classList.add("hidden"); return; }
  section.classList.remove("hidden");
  $("alternativeCount").textContent = `${state.alternatives.length} 套`;
  $("alternativeList").innerHTML = state.alternatives.map((plan, index) => `<article class="alternative-card ${index === 0 ? "recommended" : ""}">
    <div><span>${index === 0 ? "推荐" : `备选 ${index}`}</span><strong>${escapeHtml(plan.name)}</strong><small>${plan.change_count ? `${plan.change_count} 路引脚与推荐方案不同` : "当前综合最优方案"}</small></div>
    <div class="alternative-score"><strong>${plan.score}</strong><small>引脚评分</small></div>
    <button class="apply-plan" data-index="${index}" ${index === 0 ? "disabled" : ""}>${index === 0 ? "当前方案" : "采用"}</button>
  </article>`).join("");
  document.querySelectorAll(".apply-plan:not(:disabled)").forEach((button) => button.addEventListener("click", () => applyAlternative(Number(button.dataset.index))));
}

function applyAlternative(index) {
  state.allocation = state.alternatives[index].allocation.map((item) => ({ ...item }));
  renderAllocation();
  recheck().catch(handleError);
}

function riskMeta(level) {
  if (level === "错误") return { cls: "error", label: "严重", icon: "!" };
  if (level === "警告") return { cls: "warning", label: "注意", icon: "△" };
  return { cls: "tip", label: "建议", icon: "i" };
}

function renderRisks() {
  const shown = state.filter === "all" ? state.risks : state.risks.filter((risk) => risk.level === state.filter);
  $("riskList").innerHTML = shown.length ? shown.map((risk, index) => {
    const meta = riskMeta(risk.level);
    const source = risk.item?.source ? `<div class="risk-source">${escapeHtml(risk.item.source)}${risk.item.line ? `:${risk.item.line}` : ""}</div>` : "";
    const fix = risk.item?.fix_snippet ? `<pre class="fix-snippet">${escapeHtml(risk.item.fix_snippet)}</pre>` : "";
    return `<article class="risk ${meta.cls}" style="--delay:${index * 45}ms">
      <div class="risk-icon">${meta.icon}</div>
      <div class="risk-copy"><div><span class="risk-tag">${meta.label}</span><code>${escapeHtml(risk.code || "check")}</code></div>
      <h4>${escapeHtml(risk.message)}</h4>${source}<p><strong>医生建议</strong>${escapeHtml(risk.suggestion || "请结合芯片手册进行复核。")}</p>${fix}</div>
    </article>`;
  }).join("") : `<div class="all-clear"><span>✓</span><div><strong>这个分类下没有问题</strong><small>当前配置看起来很健康。</small></div></div>`;
}

function renderScanOverview() {
  const panel = $("scanOverview");
  if (!state.scan) { panel.classList.add("hidden"); return; }
  panel.classList.remove("hidden");
  $("scanProjectTypes").textContent = state.scan.project_types.length ? state.scan.project_types.join(" · ") : "通用源码工程";
  $("scanRoot").textContent = state.scan.root;
  $("scanFileCount").textContent = state.scan.files_scanned;
  $("scanPinCount").textContent = state.scan.summary.pin_use_count;
  $("scanMatchCount").textContent = state.comparison?.matched_symbols ?? 0;
  $("scanSourceList").innerHTML = state.scan.pin_uses.length ? state.scan.pin_uses.map((item) => `<div class="scan-source-item"><code>${escapeHtml(item.symbol)}</code><strong>${escapeHtml(item.pin)}</strong><span>${escapeHtml(item.kind)} · ${escapeHtml(item.source)}${item.line ? `:${item.line}` : ""}</span></div>`).join("") : `<p class="no-match">没有扫描到明确的引脚定义</p>`;
}

function renderScore() {
  const errors = state.risks.filter((risk) => risk.level === "错误").length;
  const warnings = state.risks.filter((risk) => risk.level === "警告").length;
  const tips = state.risks.filter((risk) => risk.level === "提示" && risk.code !== "no_major_risk").length;
  const score = Math.max(0, Math.round(100 - state.risks.reduce((total, risk) => total + Number(risk.weight ?? (risk.level === "错误" ? 25 : risk.level === "警告" ? 10 : 2)), 0)));
  $("healthScore").textContent = score;
  $("scoreRing").style.setProperty("--score", `${score * 3.6}deg`);
  $("errorCount").textContent = errors;
  $("warningCount").textContent = warnings;
  $("tipCount").textContent = tips;
  $("issueTotal").textContent = `${state.risks.length} 项`;
  if (errors) {
    $("healthTitle").textContent = "存在需要立即处理的问题";
    $("healthSummary").textContent = `检测到 ${errors} 个严重问题，建议修复后再进入打样。`;
  } else if (warnings) {
    $("healthTitle").textContent = "整体良好，但仍可优化";
    $("healthSummary").textContent = `没有发现硬性冲突，有 ${warnings} 项设计细节值得确认。`;
  } else {
    $("healthTitle").textContent = "项目状态健康";
    $("healthSummary").textContent = "未发现明显的引脚或电气风险，可以继续下一步设计。";
  }
}

function syncAllocationFromTable() {
  document.querySelectorAll(".pin-input").forEach((input) => {
    const item = state.allocation[Number(input.dataset.index)];
    item.chip_pin = input.value.trim() || "未分配";
    const key = `${item.module_id}:${item.module_pin}`;
    if (state.locks[key]) state.locks[key] = item.chip_pin;
  });
}

async function allocate(isRecheck = false) {
  if (!$("chipSelect").value) throw new Error("请先选择主控芯片");
  if (!selectedModuleIds().length) throw new Error("请至少选择一个项目模块");
  const button = $("allocateBtn");
  button.classList.add("loading");
  button.querySelector("span:nth-child(2)").textContent = "正在扫描…";
  const started = performance.now();
  try {
    const requestPayload = isRecheck ? payload() : { ...payload(), allocation: undefined };
    const endpoint = requestPayload.project_path ? "/api/scan-project" : "/api/allocate";
    const data = await api(endpoint, { method: "POST", body: JSON.stringify(requestPayload) });
    state.allocation = data.allocation;
    state.risks = data.risks;
    state.alternatives = data.alternatives || [];
    state.scan = data.scan || (isRecheck ? state.scan : null);
    state.comparison = data.comparison || (isRecheck ? state.comparison : null);
    if (data.chip?.id && state.chips.some((chip) => chip.id === data.chip.id)) $("chipSelect").value = data.chip.id;
    state.hasScanned = true;
    renderAllocation(); renderScore(); renderRisks(); renderScanOverview(); renderAlternatives();
    $("emptyState").classList.add("hidden");
    $("resultContent").classList.remove("hidden");
    $("scanTime").textContent = `刚刚完成 · ${Math.max(0.1, (performance.now() - started) / 1000).toFixed(1)}s`;
    showToast(isRecheck ? "复检完成" : "项目扫描完成", `发现 ${state.risks.length} 项诊断信息`);
  } finally {
    button.classList.remove("loading");
    button.querySelector("span:nth-child(2)").textContent = "开始扫描项目";
  }
}

async function recheck() { syncAllocationFromTable(); await allocate(true); }
async function saveProject() { syncAllocationFromTable(); const data = await api("/api/save", { method: "POST", body: JSON.stringify(payload()) }); showToast("项目已保存", data.path); await loadProjects(); }
async function exportFile(kind) { syncAllocationFromTable(); const data = await api(`/api/export/${kind}`, { method: "POST", body: JSON.stringify(payload()) }); showToast("文件已生成", data.path); }

async function applyProject(project, fallbackName = "") {
  $("projectName").value = project.project_name || fallbackName;
  $("notes").value = project.notes || "";
  $("projectPath").value = project.project_path || "";
  $("strategySelect").value = project.strategy || "recommended";
  state.locks = project.locked_pins || {};
  $("chipSelect").value = project.chip_id;
  document.querySelectorAll(".module-check").forEach((check) => { check.checked = (project.module_ids || []).includes(check.value); });
  updateSelectedCount();
  state.allocation = project.allocation || [];
  await recheck();
}

async function restoreProject(action) {
  const name = $("projectName").value.trim();
  const data = await api(`/api/project/${action}`, { method: "POST", body: JSON.stringify({ project_name: name }) });
  await applyProject(data.project, name);
  showToast(action === "undo" ? "已恢复上一版本" : "已重新应用版本", `可撤销 ${data.history.undo} 次 · 可重做 ${data.history.redo} 次`);
}

async function loadProjects() {
  const data = await api("/api/projects");
  $("projectList").innerHTML = data.projects.length ? data.projects.map((name) => `<button class="project-item" data-name="${escapeHtml(name)}">${escapeHtml(name)} <span>→</span></button>`).join("") : `<p class="no-match">暂无保存记录</p>`;
  document.querySelectorAll(".project-item").forEach((btn) => btn.addEventListener("click", () => openProject(btn.dataset.name)));
}

async function loadEcosystem() {
  const data = await api("/api/ecosystem");
  $("ecosystemList").innerHTML = data.packages.length ? data.packages.map((item) => `<article class="ecosystem-item">
    <div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.type)} · v${escapeHtml(item.version)}</small></div>
    ${item.type === "plugin" ? `<button class="ecosystem-toggle" data-id="${escapeHtml(item.id)}" data-enabled="${item.enabled ? "true" : "false"}">${item.enabled ? "停用" : "启用"}</button>` : "<span></span>"}
    <button class="ecosystem-remove" data-id="${escapeHtml(item.id)}">卸载</button>
  </article>`).join("") : `<p class="no-match">暂无用户扩展包</p>`;
  document.querySelectorAll(".ecosystem-toggle").forEach((button) => button.addEventListener("click", () => api("/api/ecosystem/enable", { method: "POST", body: JSON.stringify({ id: button.dataset.id, enabled: button.dataset.enabled !== "true" }) }).then(loadEcosystem).catch(handleError)));
  document.querySelectorAll(".ecosystem-remove").forEach((button) => button.addEventListener("click", () => api("/api/ecosystem/uninstall", { method: "POST", body: JSON.stringify({ id: button.dataset.id }) }).then(() => { showToast("扩展包已卸载", button.dataset.id); return loadEcosystem(); }).catch(handleError)));
}

async function installEcosystemPackage() {
  const packageDir = $("ecosystemPath").value.trim();
  if (!packageDir) throw new Error("请填写扩展包目录");
  const data = await api("/api/ecosystem/install", { method: "POST", body: JSON.stringify({ package_dir: packageDir }) });
  showToast(data.updated ? "扩展包已更新" : "扩展包已安装", `${data.package.name} v${data.package.version}`);
  await Promise.all([loadEcosystem(), loadChips(), loadModules()]);
}

async function openProject(name) {
  const project = await api(`/api/project?name=${encodeURIComponent(name)}`);
  if (project._migration?.length) showToast("项目已自动升级", project._migration.join("、"));
  await applyProject(project, name);
}

function resetForm() {
  $("projectName").value = "sensor_board_v1"; $("projectPath").value = ""; $("notes").value = ""; $("chipSearch").value = ""; $("moduleSearch").value = "";
  $("strategySelect").value = "recommended";
  state.allocation = []; state.risks = []; state.alternatives = []; state.locks = {}; state.hasScanned = false; state.filter = "all"; state.scan = null; state.comparison = null;
  document.querySelectorAll(".filter").forEach((btn) => btn.classList.toggle("active", btn.dataset.filter === "all"));
  loadChips(); loadModules(); $("emptyState").classList.remove("hidden"); $("resultContent").classList.add("hidden"); $("scanOverview").classList.add("hidden"); $("alternativeSection").classList.add("hidden"); $("scanTime").textContent = "等待扫描";
}

let toastTimer;
function showToast(title, text = "") {
  clearTimeout(toastTimer); $("toastTitle").textContent = title; $("toastText").textContent = text; $("toast").classList.add("show");
  toastTimer = setTimeout(() => $("toast").classList.remove("show"), 3600);
}

function bindEvents() {
  let chipTimer; let moduleTimer;
  $("chipSearch").addEventListener("input", () => { clearTimeout(chipTimer); chipTimer = setTimeout(() => loadChips().catch(handleError), 180); });
  $("moduleSearch").addEventListener("input", () => { clearTimeout(moduleTimer); moduleTimer = setTimeout(() => loadModules().catch(handleError), 180); });
  $("allocateBtn").addEventListener("click", () => allocate().catch(handleError));
  $("recheckBtn").addEventListener("click", () => recheck().catch(handleError));
  $("saveBtn").addEventListener("click", () => saveProject().catch(handleError));
  $("undoBtn").addEventListener("click", () => restoreProject("undo").catch(handleError));
  $("redoBtn").addEventListener("click", () => restoreProject("redo").catch(handleError));
  $("ecosystemInstallBtn").addEventListener("click", () => installEcosystemPackage().catch(handleError));
  $("resetBtn").addEventListener("click", resetForm);
  $("exportMdBtn").addEventListener("click", () => exportFile("markdown").catch(handleError));
  [["exportPinsBtn", "pins"], ["exportArduinoBtn", "arduino"], ["exportStm32Btn", "stm32_hal"], ["exportEspBtn", "esp_idf"], ["exportKicadBtn", "kicad"]].forEach(([id, kind]) => $(id).addEventListener("click", () => exportFile(kind).catch(handleError)));
  document.querySelectorAll(".filter").forEach((btn) => btn.addEventListener("click", () => { state.filter = btn.dataset.filter; document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === btn)); renderRisks(); }));
}

function handleError(error) { showToast("操作未完成", error.message); }

async function init() {
  bindEvents();
  await Promise.all([loadChips(), loadModules(), loadProjects(), loadEcosystem()]);
  api("/api/version").then((data) => { $("versionLabel").textContent = `v${data.version} · 本地服务`; }).catch(() => {});
  await allocate();
}

init().catch(handleError);
