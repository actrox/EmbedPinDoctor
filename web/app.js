const state = { chips: [], modules: [], allocation: [], risks: [], filter: "all", hasScanned: false };
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
    project_name: $("projectName").value.trim() || "untitled_project",
    notes: $("notes").value.trim(),
    chip_id: $("chipSelect").value,
    module_ids: selectedModuleIds(),
    allocation: state.allocation,
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
  $("allocationBody").innerHTML = state.allocation.map((item, index) => `<tr>
    <td><strong>${escapeHtml(item.module_name)}</strong><small>${escapeHtml(item.module_pin)}</small></td>
    <td><input data-index="${index}" class="pin-input" value="${escapeHtml(item.chip_pin)}" aria-label="${escapeHtml(item.module_name)} 引脚"></td>
    <td><code>${escapeHtml(item.function)}</code></td>
    <td><span class="pin-score ${Number(item.score) < 50 ? "low" : ""}">${item.score ?? "—"}</span></td>
    <td class="note-cell">${escapeHtml(item.note || "—")}</td>
  </tr>`).join("");
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
    return `<article class="risk ${meta.cls}" style="--delay:${index * 45}ms">
      <div class="risk-icon">${meta.icon}</div>
      <div class="risk-copy"><div><span class="risk-tag">${meta.label}</span><code>${escapeHtml(risk.code || "check")}</code></div>
      <h4>${escapeHtml(risk.message)}</h4><p><strong>医生建议</strong>${escapeHtml(risk.suggestion || "请结合芯片手册进行复核。")}</p></div>
    </article>`;
  }).join("") : `<div class="all-clear"><span>✓</span><div><strong>这个分类下没有问题</strong><small>当前配置看起来很健康。</small></div></div>`;
}

function renderScore() {
  const errors = state.risks.filter((risk) => risk.level === "错误").length;
  const warnings = state.risks.filter((risk) => risk.level === "警告").length;
  const tips = state.risks.filter((risk) => risk.level === "提示" && risk.code !== "no_major_risk").length;
  const score = Math.max(0, 100 - errors * 25 - warnings * 10 - tips * 2);
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
    state.allocation[Number(input.dataset.index)].chip_pin = input.value.trim() || "未分配";
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
    const data = await api("/api/allocate", { method: "POST", body: JSON.stringify(isRecheck ? payload() : { ...payload(), allocation: undefined }) });
    state.allocation = data.allocation;
    state.risks = data.risks;
    state.hasScanned = true;
    renderAllocation(); renderScore(); renderRisks();
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

async function loadProjects() {
  const data = await api("/api/projects");
  $("projectList").innerHTML = data.projects.length ? data.projects.map((name) => `<button class="project-item" data-name="${escapeHtml(name)}">${escapeHtml(name)} <span>→</span></button>`).join("") : `<p class="no-match">暂无保存记录</p>`;
  document.querySelectorAll(".project-item").forEach((btn) => btn.addEventListener("click", () => openProject(btn.dataset.name)));
}

async function openProject(name) {
  const project = await api(`/api/project?name=${encodeURIComponent(name)}`);
  $("projectName").value = project.project_name || name;
  $("notes").value = project.notes || "";
  $("chipSelect").value = project.chip_id;
  document.querySelectorAll(".module-check").forEach((check) => { check.checked = (project.module_ids || []).includes(check.value); });
  updateSelectedCount(); state.allocation = project.allocation || []; await recheck();
}

function resetForm() {
  $("projectName").value = "sensor_board_v1"; $("notes").value = ""; $("chipSearch").value = ""; $("moduleSearch").value = "";
  state.allocation = []; state.risks = []; state.hasScanned = false; state.filter = "all";
  document.querySelectorAll(".filter").forEach((btn) => btn.classList.toggle("active", btn.dataset.filter === "all"));
  loadChips(); loadModules(); $("emptyState").classList.remove("hidden"); $("resultContent").classList.add("hidden"); $("scanTime").textContent = "等待扫描";
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
  $("resetBtn").addEventListener("click", resetForm);
  $("exportMdBtn").addEventListener("click", () => exportFile("markdown").catch(handleError));
  [["exportPinsBtn", "pins"], ["exportArduinoBtn", "arduino"], ["exportStm32Btn", "stm32_hal"], ["exportEspBtn", "esp_idf"], ["exportKicadBtn", "kicad"]].forEach(([id, kind]) => $(id).addEventListener("click", () => exportFile(kind).catch(handleError)));
  document.querySelectorAll(".filter").forEach((btn) => btn.addEventListener("click", () => { state.filter = btn.dataset.filter; document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === btn)); renderRisks(); }));
}

function handleError(error) { showToast("操作未完成", error.message); }

async function init() {
  bindEvents();
  await Promise.all([loadChips(), loadModules(), loadProjects()]);
  api("/api/version").then((data) => { $("versionLabel").textContent = `v${data.version} · 本地服务`; }).catch(() => {});
  await allocate();
}

init().catch(handleError);
