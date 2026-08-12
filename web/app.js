const state = {
  chips: [],
  modules: [],
  allocation: [],
  risks: [],
  alternatives: [],
  locks: {},
  filter: "all",
  hasScanned: false,
  scan: null,
  comparison: null,
  scanSeconds: null,
  version: null,
  solver: null,
  dataTrust: null,
};
const $ = (id) => document.getElementById(id);
const escapeHtml = (value = "") =>
  String(value).replace(
    /[&<>'"]/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[
        char
      ],
  );
const t = (key, values) => window.I18N.t(key, values);
const demoMode =
  window.location.hostname.endsWith("github.io") ||
  new URLSearchParams(window.location.search).has("demo");

async function api(path, options = {}) {
  if (demoMode) return window.DemoAPI.request(path, options);
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || "请求失败");
  return data;
}

function selectedModuleIds() {
  return [...document.querySelectorAll(".module-check:checked")].map(
    (item) => item.value,
  );
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
    signal_mapping: readSignalMapping(),
  };
}

function readSignalMapping() {
  try {
    return JSON.parse(
      localStorage.getItem("embedpindoctor.signalMapping") || "{}",
    );
  } catch {
    return {};
  }
}

function mappingText(mapping = readSignalMapping()) {
  return Object.entries(mapping)
    .map(([source, target]) => `${source} = ${target}`)
    .join("\n");
}

function saveSignalMapping() {
  const mapping = {};
  $("signalMappingInput")
    .value.split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const [source, target] = line.split("=").map((item) => item.trim());
      if (source && target) mapping[source] = target;
    });
  localStorage.setItem("embedpindoctor.signalMapping", JSON.stringify(mapping));
  if ($("projectPath").value.trim()) recheck().catch(handleError);
  else showToast(t("saveMapping"), `${Object.keys(mapping).length}`);
}

async function loadChips() {
  const selected = $("chipSelect").value;
  state.chips = (
    await api(`/api/chips?q=${encodeURIComponent($("chipSearch").value)}`)
  ).chips;
  $("chipCount").textContent = state.chips.length;
  $("chipSelect").innerHTML = state.chips
    .map(
      (chip) =>
        `<option value="${escapeHtml(chip.id)}">${escapeHtml(chip.name)} · ${escapeHtml(chip.voltage)}</option>`,
    )
    .join("");
  if (state.chips.some((chip) => chip.id === selected))
    $("chipSelect").value = selected;
}

async function loadModules() {
  const selected = new Set(selectedModuleIds());
  state.modules = (
    await api(`/api/modules?q=${encodeURIComponent($("moduleSearch").value)}`)
  ).modules;
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
  $("moduleList").innerHTML = state.modules.length
    ? state.modules
        .map((module, index) => {
          const checked =
            selected.has(module.id) || (!selected.size && index < 4);
          return `<label class="module-item">
      <input class="module-check" type="checkbox" value="${escapeHtml(module.id)}" ${checked ? "checked" : ""}>
      <span class="module-icon">${moduleIcon(module)}</span>
      <span class="module-info"><strong>${escapeHtml(module.name)}</strong><small>${escapeHtml(module.description || module.voltage || "硬件模块")}</small></span>
      <span class="check-ui">✓</span>
    </label>`;
        })
        .join("")
    : `<p class="no-match">${t("noModules")}</p>`;
  document
    .querySelectorAll(".module-check")
    .forEach((item) => item.addEventListener("change", updateSelectedCount));
  updateSelectedCount();
}

function updateSelectedCount() {
  $("selectedCount").textContent = t("selected", {
    count: selectedModuleIds().length,
  });
}

function renderAllocation() {
  $("allocationSummary").textContent = t("connections", {
    count: state.allocation.length,
  });
  $("allocationBody").innerHTML = state.allocation
    .map((item, index) => {
      const key = `${item.module_id}:${item.module_pin}`;
      return `<tr>
    <td><label class="lock-control" title="锁定当前引脚"><input type="checkbox" class="pin-lock" data-key="${escapeHtml(key)}" ${state.locks[key] ? "checked" : ""}><span>⌾</span></label></td>
    <td><strong>${escapeHtml(item.module_name)}</strong><small>${escapeHtml(item.module_pin)}</small></td>
    <td><input data-index="${index}" class="pin-input" value="${escapeHtml(item.chip_pin)}" aria-label="${escapeHtml(item.module_name)} 引脚"></td>
    <td><code>${escapeHtml(item.function)}</code></td>
    <td><span class="pin-score ${Number(item.score) < 50 ? "low" : ""}">${item.score ?? "—"}</span></td>
    <td class="note-cell">${escapeHtml(item.note || "—")}</td>
  </tr>`;
    })
    .join("");
  document.querySelectorAll(".pin-lock").forEach((input) =>
    input.addEventListener("change", () => {
      const row = state.allocation.find(
        (item) => `${item.module_id}:${item.module_pin}` === input.dataset.key,
      );
      if (input.checked && row?.chip_pin && row.chip_pin !== "未分配")
        state.locks[input.dataset.key] = row.chip_pin;
      else delete state.locks[input.dataset.key];
    }),
  );
  document.querySelectorAll("#allocationBody tr").forEach((row, index) =>
    row.addEventListener("click", (event) => {
      if (event.target.closest("input,label")) return;
      showAllocationEvidence(state.allocation[index]);
    }),
  );
  renderWiringDiagram();
}

function showAllocationEvidence(item) {
  $("allocationEvidence").classList.remove("hidden");
  $("allocationEvidenceTitle").textContent =
    `${item.module_name} ${item.module_pin} → ${item.chip_pin}`;
  const reasons = item.reasons?.length
    ? item.reasons
    : [item.note || "当前约束下的最佳候选"];
  $("allocationEvidenceBody").innerHTML =
    `<div class="evidence-score"><strong>${item.score ?? "—"}</strong><span>${t("pinScore")}</span></div><ul>${reasons.map((reason) => `<li>✓ ${escapeHtml(reason)}</li>`).join("")}</ul><dl><div><dt>Function</dt><dd>${escapeHtml(item.function)}</dd></div><div><dt>Direction</dt><dd>${escapeHtml(item.direction)}</dd></div><div><dt>Solver</dt><dd>${escapeHtml(state.solver?.status || "—")} · ${state.solver?.elapsed_ms ?? "—"}ms${state.solver?.cache_hit ? " · cache" : ""}</dd></div></dl>`;
}

function renderWiringDiagram() {
  const canvas = $("wiringCanvas");
  if (!canvas) return;
  const chip = state.chips.find((item) => item.id === $("chipSelect").value);
  const grouped = new Map();
  state.allocation.forEach((item) => {
    if (!grouped.has(item.module_id)) grouped.set(item.module_id, []);
    grouped.get(item.module_id).push(item);
  });
  const modules = [...grouped.entries()];
  if (!modules.length) {
    canvas.innerHTML = `<div class="wiring-empty"><span>⌁</span><strong>等待生成架构图</strong><small>完成左侧配置后，这里会显示模块与主控的引脚连接。</small></div>`;
    return;
  }
  const rows = Math.max(1, Math.ceil(modules.length / 2));
  const height = Math.max(440, rows * 190 + 100);
  const centerY = height / 2;
  const leftModules = modules.filter((_, index) => index % 2 === 0);
  const rightModules = modules.filter((_, index) => index % 2 === 1);
  const moduleMarkup = [];
  const paths = [];
  const addSide = (items, side) => {
    items.forEach(([moduleId, connections], index) => {
      const y = 75 + index * 190;
      const x = side === "left" ? 7 : 76;
      const endX = side === "left" ? 31 : 69;
      const startX = side === "left" ? 24 : 76;
      const moduleName = connections[0]?.module_name || moduleId;
      const signals = connections.slice(0, 4);
      moduleMarkup.push(`<article class="diagram-module ${side}" style="left:${x}%;top:${y}px">
        <div class="module-board-head"><span>${moduleIcon({ id: moduleId })}</span><div><strong>${escapeHtml(moduleName)}</strong><small>${escapeHtml(moduleId)}</small></div></div>
        <div class="module-pins">${signals.map((item) => `<span><b>${escapeHtml(item.module_pin)}</b><em>${escapeHtml(item.chip_pin)}</em></span>`).join("")}</div>
      </article>`);
      signals.forEach((item, signalIndex) => {
        const sy = y + 66 + signalIndex * 24;
        const ty = centerY - 54 + ((paths.length % 5) - 2) * 27;
        const hue = [188, 156, 42, 334, 210][paths.length % 5];
        const d =
          side === "left"
            ? `M ${startX} ${sy} C 34 ${sy}, 35 ${ty}, ${endX + 8} ${ty}`
            : `M ${startX} ${sy} C 67 ${sy}, 65 ${ty}, ${endX - 8} ${ty}`;
        paths.push(
          `<path d="${d}" style="--wire:hsl(${hue} 80% 68%)"/><circle cx="${side === "left" ? endX + 8 : endX - 8}" cy="${ty}" r="3" style="--wire:hsl(${hue} 80% 68%)"/>`,
        );
      });
    });
  };
  addSide(leftModules, "left");
  addSide(rightModules, "right");
  canvas.style.minHeight = `${height}px`;
  canvas.innerHTML = `<div class="canvas-grid"></div>
    <svg class="wire-layer" viewBox="0 0 100 ${height}" preserveAspectRatio="none" aria-hidden="true">${paths.join("")}</svg>
    <article class="controller-board" style="top:${centerY - 128}px">
      <span class="board-status">● ONLINE</span><div class="chip-silkscreen"></div>
      <strong>${escapeHtml(chip?.name || $("chipSelect").value)}</strong><small>主控制器 · ${escapeHtml(chip?.voltage || "")}</small>
      <div class="board-pins left-pins">${state.allocation
        .slice(0, 5)
        .map((item) => `<i>${escapeHtml(item.chip_pin)}</i>`)
        .join("")}</div>
      <div class="board-pins right-pins">${state.allocation
        .slice(5, 10)
        .map((item) => `<i>${escapeHtml(item.chip_pin)}</i>`)
        .join("")}</div>
    </article>${moduleMarkup.join("")}`;
  canvas.querySelectorAll(".diagram-module").forEach((card) =>
    card.addEventListener("click", () => {
      canvas
        .querySelectorAll(".diagram-module")
        .forEach((item) => item.classList.toggle("dimmed", item !== card));
      card.classList.remove("dimmed");
      card.classList.toggle("focused");
      if (!card.classList.contains("focused"))
        canvas
          .querySelectorAll(".diagram-module")
          .forEach((item) => item.classList.remove("dimmed"));
    }),
  );
}

function exportDiagram() {
  const canvas = $("wiringCanvas");
  const clone = canvas.cloneNode(true);
  clone
    .querySelectorAll(".controller-board,.diagram-module")
    .forEach((node) => {
      node.setAttribute("xmlns", "http://www.w3.org/1999/xhtml");
    });
  const width = Math.max(900, canvas.clientWidth);
  const height = Math.max(500, canvas.scrollHeight);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><foreignObject width="100%" height="100%"><div xmlns="http://www.w3.org/1999/xhtml" style="width:${width}px;height:${height}px;background:#0a101d;color:white;font-family:Segoe UI,sans-serif">${clone.innerHTML}</div></foreignObject></svg>`;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  link.download = `${$("projectName").value.trim() || "hardware"}-architecture.svg`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function showEvidence() {
  const chip = state.chips.find((item) => item.id === $("chipSelect").value);
  $("evidenceContent").innerHTML =
    `<article class="evidence-card"><span class="trust-state ${state.dataTrust?.verified ? "verified" : "review"}">${state.dataTrust?.verified ? "VERIFIED" : "REVIEW REQUIRED"}</span><h3>${escapeHtml(chip?.name || "—")}</h3><dl><div><dt>Status</dt><dd>${escapeHtml(state.dataTrust?.status || "unknown")}</dd></div><div><dt>Solver</dt><dd>${escapeHtml(state.solver?.status || "unknown")}</dd></div><div><dt>Search nodes</dt><dd>${state.solver?.nodes_searched ?? "—"}</dd></div></dl>${state.dataTrust?.source ? `<a href="${escapeHtml(state.dataTrust.source)}" target="_blank" rel="noreferrer">Official datasheet ↗</a>` : ""}</article>`;
  $("evidenceDialog").showModal();
}

function createFromWizard(event) {
  event.preventDefault();
  $("projectName").value =
    $("wizardName").value.trim() || "new_hardware_project";
  $("notes").value = $("wizardRequirements").value.trim();
  selectPlatform($("wizardPlatform").value);
  const requirements = $("wizardRequirements").value.toLowerCase();
  const patterns = [
    [/oled|display|屏幕|显示/, /oled|display/],
    [/imu|motion|姿态|陀螺仪/, /mpu6050/],
    [/sd|storage|存储/, /sd_card/],
    [/buzzer|蜂鸣器/, /buzzer/],
    [/led|灯带/, /ws2812/],
    [/button|按键/, /button/],
  ];
  const desired = patterns
    .filter(([keyword]) => keyword.test(requirements))
    .map(([, modulePattern]) => modulePattern);
  if (desired.length) {
    document.querySelectorAll(".module-check").forEach((check) => {
      check.checked = desired.some((pattern) => pattern.test(check.value));
    });
    updateSelectedCount();
  }
  $("wizardDialog").close();
  allocate().catch(handleError);
}

function renderAlternatives() {
  const section = $("alternativeSection");
  if (!state.alternatives.length) {
    section.classList.add("hidden");
    return;
  }
  section.classList.remove("hidden");
  $("alternativeCount").textContent = t("planCount", {
    count: state.alternatives.length,
  });
  $("alternativeList").innerHTML = state.alternatives
    .map(
      (
        plan,
        index,
      ) => `<article class="alternative-card ${index === 0 ? "recommended" : ""}">
    <div><span>${index === 0 ? t("recommendedPlan") : t("alternativePlan", { count: index })}</span><strong>${escapeHtml(plan.name)}</strong><small>${plan.change_count ? `${plan.change_count} changes` : t("currentPlan")}</small></div>
    <div class="alternative-score"><strong>${plan.score}</strong><small>${t("pinScore")}</small></div>
    <button class="apply-plan" data-index="${index}" ${index === 0 ? "disabled" : ""}>${index === 0 ? t("currentPlan") : t("applyPlan")}</button>
  </article>`,
    )
    .join("");
  document
    .querySelectorAll(".apply-plan:not(:disabled)")
    .forEach((button) =>
      button.addEventListener("click", () =>
        applyAlternative(Number(button.dataset.index)),
      ),
    );
}

function applyAlternative(index) {
  state.allocation = state.alternatives[index].allocation.map((item) => ({
    ...item,
  }));
  renderAllocation();
  recheck().catch(handleError);
}

function riskMeta(level) {
  if (level === "错误") return { cls: "error", label: t("severe"), icon: "!" };
  if (level === "警告")
    return { cls: "warning", label: t("caution"), icon: "△" };
  return { cls: "tip", label: t("advice"), icon: "i" };
}

const englishRisks = {
  data_unverified: [
    "Hardware data has not received final human sign-off.",
    "Verify the affected pins against the official datasheet before manufacturing.",
  ],
  pin_duplicate: [
    "A non-shareable controller pin is assigned more than once.",
    "Move one signal to a compatible free pin.",
  ],
  unassigned: [
    "No compatible controller pin is available for this signal.",
    "Reduce constraints, select another controller, or assign a compatible pin manually.",
  ],
  voltage_mismatch: [
    "The module and controller use different I/O voltage domains.",
    "Verify logic thresholds and add level shifting where required.",
  ],
  pullup_required: [
    "The I2C bus requires suitable pull-up resistors.",
    "Check onboard resistors and calculate the effective pull-up for the bus speed and length.",
  ],
  boot_pin: [
    "This assignment uses a boot-configuration pin.",
    "Verify power-on levels or move the signal to a regular GPIO.",
  ],
  debug_pin: [
    "This assignment uses a debug pin.",
    "Prefer a regular GPIO if the debug interface must remain available.",
  ],
  i2c_address_conflict: [
    "Two devices share the same I2C address.",
    "Change an address option, move a device to another bus, or add an I2C multiplexer.",
  ],
  spi_mode_mixed: [
    "Devices on this SPI bus require different modes.",
    "Reconfigure CPOL/CPHA whenever selecting a different device.",
  ],
  pwm_timer_frequency_conflict: [
    "PWM channels on one timer require incompatible frequencies.",
    "Move signals to different timers or align their periods.",
  ],
};

function localizedRisk(risk) {
  if (window.I18N.locale !== "en" || !englishRisks[risk.code]) return risk;
  const [message, suggestion] = englishRisks[risk.code];
  return { ...risk, message, suggestion };
}

function renderRisks() {
  const shown =
    state.filter === "all"
      ? state.risks
      : state.risks.filter((risk) => risk.level === state.filter);
  $("riskList").innerHTML = shown.length
    ? shown
        .map((originalRisk, index) => {
          const risk = localizedRisk(originalRisk);
          const meta = riskMeta(risk.level);
          const source = risk.item?.source
            ? `<div class="risk-source">${escapeHtml(risk.item.source)}${risk.item.line ? `:${risk.item.line}` : ""}</div>`
            : "";
          const fix = risk.item?.fix_snippet
            ? `<pre class="fix-snippet">${escapeHtml(risk.item.fix_snippet)}</pre>`
            : "";
          return `<article class="risk ${meta.cls}" style="--delay:${index * 45}ms">
      <div class="risk-icon">${meta.icon}</div>
      <div class="risk-copy"><div><span class="risk-tag">${meta.label}</span><code>${escapeHtml(risk.code || "check")}</code></div>
      <h4>${escapeHtml(risk.message)}</h4>${source}<p><strong>${t("doctorAdvice")}</strong>${escapeHtml(risk.suggestion || "请结合芯片手册进行复核。")}</p>${fix}</div>
    </article>`;
        })
        .join("")
    : `<div class="all-clear"><span>✓</span><div><strong>这个分类下没有问题</strong><small>当前配置看起来很健康。</small></div></div>`;
}

function renderScanOverview() {
  const panel = $("scanOverview");
  if (!state.scan) {
    panel.classList.add("hidden");
    return;
  }
  panel.classList.remove("hidden");
  $("scanProjectTypes").textContent = state.scan.project_types.length
    ? state.scan.project_types.join(" · ")
    : "通用源码工程";
  $("scanRoot").textContent = state.scan.root;
  $("scanFileCount").textContent = state.scan.files_scanned;
  $("scanPinCount").textContent = state.scan.summary.pin_use_count;
  $("scanMatchCount").textContent = state.comparison?.matched_symbols ?? 0;
  $("scanSourceList").innerHTML = state.scan.pin_uses.length
    ? state.scan.pin_uses
        .map(
          (item) =>
            `<div class="scan-source-item"><code>${escapeHtml(item.symbol)}</code><strong>${escapeHtml(item.pin)}</strong><span>${escapeHtml(item.kind)} · ${escapeHtml(item.source)}${item.line ? `:${item.line}` : ""}</span></div>`,
        )
        .join("")
    : `<p class="no-match">没有扫描到明确的引脚定义</p>`;
}

function renderScore() {
  const errors = state.risks.filter((risk) => risk.level === "错误").length;
  const warnings = state.risks.filter((risk) => risk.level === "警告").length;
  const tips = state.risks.filter(
    (risk) => risk.level === "提示" && risk.code !== "no_major_risk",
  ).length;
  const score = Math.max(
    0,
    Math.round(
      100 -
        state.risks.reduce(
          (total, risk) =>
            total +
            Number(
              risk.weight ??
                (risk.level === "错误" ? 25 : risk.level === "警告" ? 10 : 2),
            ),
          0,
        ),
    ),
  );
  $("healthScore").textContent = score;
  $("scoreRing").style.setProperty("--score", `${score * 3.6}deg`);
  $("errorCount").textContent = errors;
  $("warningCount").textContent = warnings;
  $("tipCount").textContent = tips;
  renderFeasibility(errors);
  $("issueTotal").textContent = t("issueCount", { count: state.risks.length });
  if (errors) {
    $("healthTitle").textContent = t("needsFix");
    $("healthSummary").textContent = t("needsFixSummary", { count: errors });
  } else if (warnings) {
    $("healthTitle").textContent = t("canImprove");
    $("healthSummary").textContent = t("canImproveSummary", {
      count: warnings,
    });
  } else {
    $("healthTitle").textContent = t("healthy");
    $("healthSummary").textContent = t("healthySummary");
  }
}

function renderFeasibility(errors = 0) {
  const badge = $("feasibilityBadge");
  if (!badge) return;
  const solverOk =
    !state.solver || ["optimal", "manual"].includes(state.solver.status);
  const dataVerified = state.dataTrust?.verified !== false;
  const feasible = state.hasScanned && errors === 0 && solverOk && dataVerified;
  badge.classList.toggle("blocked", state.hasScanned && !feasible);
  badge.classList.toggle("pending", !state.hasScanned);
  badge.querySelector("span").textContent = state.hasScanned
    ? feasible
      ? "✓"
      : "!"
    : "…";
  badge.querySelector("b").textContent = t(
    state.hasScanned ? (feasible ? "feasible" : "needsRevision") : "feasible",
  );
  badge.querySelector("small").textContent = !state.hasScanned
    ? t("waitingAnalysis")
    : !dataVerified
      ? t("dataNeedsReview")
      : !solverOk
        ? t("solverIncomplete")
        : feasible
          ? t("allSignalsAssigned")
          : t("criticalFindings", { count: errors });
}

function selectPlatform(platform) {
  const matcher = platform === "esp32" ? /^esp32/ : /^stm32/;
  const chip = state.chips.find((item) => matcher.test(item.id));
  if (!chip) return;
  $("chipSelect").value = chip.id;
  document
    .querySelectorAll(".platform-card")
    .forEach((card) =>
      card.classList.toggle("active", card.dataset.platform === platform),
    );
  renderWiringDiagram();
}

function syncPlatformCards() {
  const chipId = $("chipSelect").value;
  document
    .querySelectorAll(".platform-card")
    .forEach((card) =>
      card.classList.toggle("active", chipId.startsWith(card.dataset.platform)),
    );
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
  button.querySelector("span:nth-child(2)").textContent = t("scanning");
  const started = performance.now();
  try {
    const requestPayload = isRecheck
      ? payload()
      : { ...payload(), allocation: undefined };
    const endpoint = requestPayload.project_path
      ? "/api/scan-project"
      : "/api/allocate";
    const data = await api(endpoint, {
      method: "POST",
      body: JSON.stringify(requestPayload),
    });
    state.allocation = data.allocation;
    state.risks = data.risks;
    state.alternatives = data.alternatives || [];
    state.solver = data.solver || null;
    state.dataTrust = data.data_trust || null;
    state.scan = data.scan || (isRecheck ? state.scan : null);
    state.comparison = data.comparison || (isRecheck ? state.comparison : null);
    if (data.chip?.id && state.chips.some((chip) => chip.id === data.chip.id))
      $("chipSelect").value = data.chip.id;
    state.hasScanned = true;
    renderAllocation();
    renderScore();
    renderRisks();
    renderScanOverview();
    renderAlternatives();
    $("emptyState").classList.add("hidden");
    $("resultContent").classList.remove("hidden");
    state.scanSeconds = Math.max(
      0.1,
      (performance.now() - started) / 1000,
    ).toFixed(1);
    $("scanTime").textContent = t("scanDone", {
      seconds: state.scanSeconds,
    });
    showToast(
      isRecheck ? t("recheckComplete") : t("scanComplete"),
      t("diagnosisInfo", { count: state.risks.length }),
    );
  } finally {
    button.classList.remove("loading");
    button.querySelector("span:nth-child(2)").textContent = t("startScan");
  }
}

async function recheck() {
  syncAllocationFromTable();
  await allocate(true);
}
async function saveProject() {
  syncAllocationFromTable();
  const data = await api("/api/save", {
    method: "POST",
    body: JSON.stringify(payload()),
  });
  showToast("项目已保存", data.path);
  await loadProjects();
}
async function exportFile(kind) {
  syncAllocationFromTable();
  const data = await api(`/api/export/${kind}`, {
    method: "POST",
    body: JSON.stringify(payload()),
  });
  showToast("文件已生成", data.path);
}

function downloadPlan() {
  const chip = state.chips.find((item) => item.id === $("chipSelect").value);
  const lines = [
    `# ${$("projectName").value.trim() || "EmbedPinDoctor plan"}`,
    "",
    `- Controller: ${chip?.name || $("chipSelect").value}`,
    `- Strategy: ${$("strategySelect").value}`,
    `- Findings: ${state.risks.length}`,
    "",
    "## Requirements",
    "",
    $("notes").value.trim() || "—",
    "",
    "## Pin allocation",
    "",
    "| Module | Signal | Controller pin | Function | Score |",
    "| --- | --- | --- | --- | ---: |",
    ...state.allocation.map(
      (item) =>
        `| ${item.module_name} | ${item.module_pin} | ${item.chip_pin} | ${item.function} | ${item.score ?? "—"} |`,
    ),
    "",
    "## Findings",
    "",
    ...state.risks.map(
      (risk) =>
        `- **${risk.level} · ${risk.code}** ${risk.message} ${risk.suggestion || ""}`,
    ),
  ];
  const blob = new Blob([lines.join("\n")], {
    type: "text/markdown;charset=utf-8",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${$("projectName").value.trim() || "hardware-plan"}.md`;
  link.click();
  URL.revokeObjectURL(link.href);
  showToast(t("download"), link.download);
}

async function applyProject(project, fallbackName = "") {
  $("projectName").value = project.project_name || fallbackName;
  $("notes").value = project.notes || "";
  $("projectPath").value = project.project_path || "";
  $("strategySelect").value = project.strategy || "recommended";
  state.locks = project.locked_pins || {};
  $("chipSelect").value = project.chip_id;
  document.querySelectorAll(".module-check").forEach((check) => {
    check.checked = (project.module_ids || []).includes(check.value);
  });
  updateSelectedCount();
  state.allocation = project.allocation || [];
  await recheck();
}

async function restoreProject(action) {
  const name = $("projectName").value.trim();
  const data = await api(`/api/project/${action}`, {
    method: "POST",
    body: JSON.stringify({ project_name: name }),
  });
  await applyProject(data.project, name);
  showToast(
    action === "undo" ? "已恢复上一版本" : "已重新应用版本",
    `可撤销 ${data.history.undo} 次 · 可重做 ${data.history.redo} 次`,
  );
}

async function loadProjects() {
  const data = await api("/api/projects");
  $("projectList").innerHTML = data.projects.length
    ? data.projects
        .map(
          (name) =>
            `<button class="project-item" data-name="${escapeHtml(name)}">${escapeHtml(name)} <span>→</span></button>`,
        )
        .join("")
    : `<p class="no-match">暂无保存记录</p>`;
  document
    .querySelectorAll(".project-item")
    .forEach((btn) =>
      btn.addEventListener("click", () => openProject(btn.dataset.name)),
    );
}

async function loadEcosystem() {
  const data = await api("/api/ecosystem");
  $("ecosystemList").innerHTML = data.packages.length
    ? data.packages
        .map(
          (item) => `<article class="ecosystem-item">
    <div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.type)} · v${escapeHtml(item.version)}</small></div>
    ${item.type === "plugin" ? `<button class="ecosystem-toggle" data-id="${escapeHtml(item.id)}" data-enabled="${item.enabled ? "true" : "false"}">${item.enabled ? "停用" : "启用"}</button>` : "<span></span>"}
    <button class="ecosystem-remove" data-id="${escapeHtml(item.id)}">卸载</button>
  </article>`,
        )
        .join("")
    : `<p class="no-match">暂无用户扩展包</p>`;
  document.querySelectorAll(".ecosystem-toggle").forEach((button) =>
    button.addEventListener("click", () =>
      api("/api/ecosystem/enable", {
        method: "POST",
        body: JSON.stringify({
          id: button.dataset.id,
          enabled: button.dataset.enabled !== "true",
        }),
      })
        .then(loadEcosystem)
        .catch(handleError),
    ),
  );
  document.querySelectorAll(".ecosystem-remove").forEach((button) =>
    button.addEventListener("click", () =>
      api("/api/ecosystem/uninstall", {
        method: "POST",
        body: JSON.stringify({ id: button.dataset.id }),
      })
        .then(() => {
          showToast("扩展包已卸载", button.dataset.id);
          return loadEcosystem();
        })
        .catch(handleError),
    ),
  );
}

async function loadExample(exampleId) {
  const example = window.WorkbenchExamples.get(exampleId);
  if (!example) return;
  $("projectName").value = example.project_name;
  $("notes").value = example.notes;
  $("chipSelect").value = example.chip_id;
  syncPlatformCards();
  document.querySelectorAll(".module-check").forEach((check) => {
    check.checked = example.module_ids.includes(check.value);
  });
  updateSelectedCount();
  document
    .querySelectorAll(".example-card")
    .forEach((card) =>
      card.classList.toggle("active", card.dataset.example === exampleId),
    );
  await allocate();
  showResultView("wiringSection");
  showToast(t("exampleLoaded"), example.project_name);
}

function showResultView(targetName) {
  window.WorkbenchViews.show(targetName);
}

async function installEcosystemPackage() {
  const packageDir = $("ecosystemPath").value.trim();
  if (!packageDir) throw new Error("请填写扩展包目录");
  const data = await api("/api/ecosystem/install", {
    method: "POST",
    body: JSON.stringify({ package_dir: packageDir }),
  });
  showToast(
    data.updated ? "扩展包已更新" : "扩展包已安装",
    `${data.package.name} v${data.package.version}`,
  );
  await Promise.all([loadEcosystem(), loadChips(), loadModules()]);
}

async function openProject(name) {
  const project = await api(`/api/project?name=${encodeURIComponent(name)}`);
  if (project._migration?.length)
    showToast("项目已自动升级", project._migration.join("、"));
  await applyProject(project, name);
}

function resetForm() {
  $("projectName").value = "sensor_board_v1";
  $("projectPath").value = "";
  $("notes").value = "";
  $("chipSearch").value = "";
  $("moduleSearch").value = "";
  $("strategySelect").value = "recommended";
  state.allocation = [];
  state.risks = [];
  state.alternatives = [];
  state.locks = {};
  state.hasScanned = false;
  state.filter = "all";
  state.scan = null;
  state.comparison = null;
  state.scanSeconds = null;
  document
    .querySelectorAll(".filter")
    .forEach((btn) =>
      btn.classList.toggle("active", btn.dataset.filter === "all"),
    );
  loadChips();
  loadModules();
  $("emptyState").classList.remove("hidden");
  $("resultContent").classList.add("hidden");
  $("scanOverview").classList.add("hidden");
  $("alternativeSection").classList.add("hidden");
  $("scanTime").textContent = "等待扫描";
}

let toastTimer;
function showToast(title, text = "") {
  clearTimeout(toastTimer);
  $("toastTitle").textContent = title;
  $("toastText").textContent = text;
  $("toast").classList.add("show");
  toastTimer = setTimeout(() => $("toast").classList.remove("show"), 3600);
}

function bindEvents() {
  let chipTimer;
  let moduleTimer;
  $("chipSearch").addEventListener("input", () => {
    clearTimeout(chipTimer);
    chipTimer = setTimeout(() => loadChips().catch(handleError), 180);
  });
  $("moduleSearch").addEventListener("input", () => {
    clearTimeout(moduleTimer);
    moduleTimer = setTimeout(() => loadModules().catch(handleError), 180);
  });
  $("chipSelect").addEventListener("change", () => {
    syncPlatformCards();
    renderWiringDiagram();
  });
  document.querySelectorAll(".platform-card").forEach((card) =>
    card.addEventListener("click", () => {
      selectPlatform(card.dataset.platform);
      allocate().catch(handleError);
    }),
  );
  $("allocateBtn").addEventListener("click", () =>
    allocate().catch(handleError),
  );
  $("recheckBtn").addEventListener("click", () => recheck().catch(handleError));
  $("saveBtn").addEventListener("click", () =>
    saveProject().catch(handleError),
  );
  $("undoBtn").addEventListener("click", () =>
    restoreProject("undo").catch(handleError),
  );
  $("redoBtn").addEventListener("click", () =>
    restoreProject("redo").catch(handleError),
  );
  $("languageSelect").addEventListener("change", (event) =>
    window.I18N.setLocale(event.target.value),
  );
  $("ecosystemInstallBtn").addEventListener("click", () =>
    installEcosystemPackage().catch(handleError),
  );
  $("resetBtn").addEventListener("click", resetForm);
  $("exportMdBtn").addEventListener("click", () =>
    exportFile("markdown").catch(handleError),
  );
  $("downloadBtn").addEventListener("click", downloadPlan);
  $("printBtn").addEventListener("click", () => window.print());
  $("wizardBtn").addEventListener("click", () => $("wizardDialog").showModal());
  $("evidenceBtn").addEventListener("click", showEvidence);
  $("createProjectBtn").addEventListener("click", createFromWizard);
  $("exportDiagramBtn").addEventListener("click", exportDiagram);
  $("signalMappingInput").value = mappingText();
  $("saveSignalMappingBtn").addEventListener("click", saveSignalMapping);
  $("closeAllocationEvidence").addEventListener("click", () =>
    $("allocationEvidence").classList.add("hidden"),
  );
  document
    .querySelectorAll(".example-card")
    .forEach((card) =>
      card.addEventListener("click", () =>
        loadExample(card.dataset.example).catch(handleError),
      ),
    );
  [
    ["exportPinsBtn", "pins"],
    ["exportArduinoBtn", "arduino"],
    ["exportStm32Btn", "stm32_hal"],
    ["exportEspBtn", "esp_idf"],
    ["exportKicadBtn", "kicad"],
  ].forEach(([id, kind]) =>
    $(id).addEventListener("click", () => exportFile(kind).catch(handleError)),
  );
  document.querySelectorAll(".filter").forEach((btn) =>
    btn.addEventListener("click", () => {
      state.filter = btn.dataset.filter;
      document
        .querySelectorAll(".filter")
        .forEach((item) => item.classList.toggle("active", item === btn));
      renderRisks();
    }),
  );
  document
    .querySelectorAll(".view-tab")
    .forEach((button) =>
      button.addEventListener("click", () =>
        showResultView(button.dataset.viewTarget),
      ),
    );
}

function handleError(error) {
  showToast("操作未完成", error.message);
}

async function init() {
  window.I18N.applyLanguage();
  if (demoMode) {
    document.body.classList.add("demo-mode");
    $("runtimeBadge").dataset.i18n = "demoMode";
    $("runtimeBadge").textContent = t("demoMode");
    [
      "undoBtn",
      "redoBtn",
      "saveBtn",
      "exportMdBtn",
      "ecosystemInstallBtn",
      "projectPath",
      "ecosystemPath",
    ].forEach((id) => {
      $(id).disabled = true;
    });
  }
  bindEvents();
  await Promise.all([
    loadChips(),
    loadModules(),
    loadProjects(),
    loadEcosystem(),
  ]);
  syncPlatformCards();
  api("/api/version")
    .then((data) => {
      state.version = data.version;
      $("versionLabel").textContent = t(
        demoMode ? "versionDemo" : "versionLocal",
        { version: data.version },
      );
    })
    .catch(() => {});
  await allocate();
}

document.addEventListener("languagechange", () => {
  if (state.modules.length) renderModules(new Set(selectedModuleIds()));
  if (state.hasScanned) {
    renderAllocation();
    renderScore();
    renderRisks();
    renderAlternatives();
  } else {
    updateSelectedCount();
  }
  if (demoMode) $("runtimeBadge").textContent = t("demoMode");
  if (state.scanSeconds) {
    $("scanTime").textContent = t("scanDone", { seconds: state.scanSeconds });
  }
  if (state.version) {
    $("versionLabel").textContent = t(
      demoMode ? "versionDemo" : "versionLocal",
      { version: state.version },
    );
  }
  $("toast").classList.remove("show");
});

init().catch(handleError);
