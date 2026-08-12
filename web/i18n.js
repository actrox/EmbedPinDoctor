const messages = {
  zh: {
    language: "语言",
    brand: "引脚医生",
    undo: "撤销保存",
    redo: "重做保存",
    localOnly: "数据仅在本机处理",
    demoMode: "在线只读演示",
    save: "保存项目",
    exportReport: "导出报告 ↗",
    heroTitle: "给你的硬件项目做一次全面体检。",
    heroPrefix: "给你的硬件项目做一次",
    heroEmphasis: "全面体检。",
    heroCopy:
      "选择主控与外设，自动检查引脚冲突、电气兼容和启动风险。每个问题都附带清晰、可执行的修复建议。",
    controllers: "款主控",
    modules: "个模块",
    local: "本地",
    offline: "离线运行",
    scanConfig: "扫描配置",
    reset: "重置",
    projectName: "项目名称",
    platformQuickPick: "硬件平台快捷选择",
    requirements: "产品需求定义",
    requirementsPlaceholder:
      "描述产品、需要的传感器、通信方式、电源与调试要求…",
    feasible: "方案可行",
    needsRevision: "方案需调整",
    waitingAnalysis: "等待分析",
    allSignalsAssigned: "所有信号均已分配",
    criticalFindings: "存在 {count} 个严重问题",
    dataNeedsReview: "硬件数据尚待人工复核",
    solverIncomplete: "求解未完成，不能确认最优性",
    download: "下载方案",
    print: "打印方案",
    newProject: "新建向导",
    evidence: "数据证据",
    exportDiagram: "导出 SVG 架构图",
    diagramHint: "点击模块可高亮相关连线",
    wizardTitle: "新建硬件项目",
    evidenceTitle: "硬件数据证据",
    cancel: "取消",
    createProject: "创建并分析",
    existingProject: "现有工程目录",
    optional: "可选",
    projectPathHint:
      "填写后将只读扫描代码、CubeMX 与 KiCad 文件；留空则按配置规划新项目。",
    chip: "主控芯片",
    chipSearch: "搜索主控型号…",
    moduleSearch: "搜索传感器、通信或执行模块…",
    strategy: "分配策略",
    recommended: "最佳质量 · 优先低风险引脚",
    minChange: "最小变更 · 尽量保持现有接线",
    projectModules: "项目模块",
    notes: "添加项目备注",
    startScan: "开始扫描项目",
    scanHint: "扫描通常在 1 秒内完成，不会上传任何文件",
    savedProjects: "打开已保存项目",
    ecosystem: "扩展包管理",
    ecosystemHint:
      "安装经过清单、版本、Schema 与可选 SHA-256 校验的数据包、规则包或插件。",
    install: "校验并安装",
    results: "系统架构与诊断",
    architecture: "架构图",
    pinTable: "引脚表",
    riskDiagnosis: "风险诊断",
    architectureTitle: "系统架构图",
    architectureCopy: "主控、外设与已分配引脚的可视化连接",
    dataSignal: "数据信号",
    power: "电源",
    lowRisk: "低风险",
    waiting: "等待扫描",
    preparing: "正在准备诊断…",
    reading: "正在读取当前项目配置。",
    errors: "严重问题",
    warnings: "需要注意",
    tips: "优化建议",
    issues: "发现的问题",
    all: "全部",
    severe: "严重",
    caution: "注意",
    advice: "建议",
    plans: "可行方案",
    planHint: "选择方案后可继续锁定和复检",
    pinDetails: "引脚分配详情",
    lock: "锁定",
    moduleSignal: "模块 / 信号",
    controllerPin: "主控引脚",
    function: "功能",
    score: "评分",
    reason: "选择理由",
    exports: "开发文件导出",
    exportHint: "生成与你的开发环境匹配的引脚定义",
    footer: "引脚医生 · 自用硬件设计辅助工具",
    doctorAdvice: "医生建议",
    selected: "已选 {count}",
    connections: "{count} 条连接",
    issueCount: "{count} 项",
    planCount: "{count} 套",
    scanning: "正在扫描…",
    scanDone: "刚刚完成 · {seconds}s",
    healthy: "项目状态健康",
    healthySummary: "未发现明显的引脚或电气风险，可以继续下一步设计。",
    needsFix: "存在需要立即处理的问题",
    needsFixSummary: "检测到 {count} 个严重问题，建议修复后再进入打样。",
    canImprove: "整体良好，但仍可优化",
    canImproveSummary: "没有发现硬性冲突，有 {count} 项设计细节值得确认。",
    readOnly: "在线演示为只读模式，请下载后在本地使用完整功能。",
    scanComplete: "项目扫描完成",
    recheckComplete: "复检完成",
    diagnosisInfo: "发现 {count} 项诊断信息",
    versionLocal: "v{version} · 本地服务",
    versionDemo: "v{version} · 在线演示",
    recommendedPlan: "推荐",
    alternativePlan: "备选 {count}",
    currentPlan: "当前方案",
    applyPlan: "采用",
    pinScore: "引脚评分",
    noModules: "没有匹配的模块",
  },
  en: {
    language: "Language",
    brand: "Pin Doctor",
    undo: "Undo save",
    redo: "Redo save",
    localOnly: "Data stays on this device",
    demoMode: "Online read-only demo",
    save: "Save project",
    exportReport: "Export report ↗",
    heroTitle: "Give your hardware project a complete checkup.",
    heroPrefix: "Give your hardware a",
    heroEmphasis: "complete checkup.",
    heroCopy:
      "Select a controller and peripherals to check pin conflicts, electrical compatibility, and boot risks. Every finding includes a clear, actionable fix.",
    controllers: "controllers",
    modules: "modules",
    local: "Local",
    offline: "Runs offline",
    scanConfig: "Scan setup",
    reset: "Reset",
    projectName: "Project name",
    platformQuickPick: "Hardware platform",
    requirements: "Product requirements",
    requirementsPlaceholder:
      "Describe the product, sensors, connectivity, power, and debugging requirements…",
    feasible: "Feasible plan",
    needsRevision: "Revision required",
    waitingAnalysis: "Awaiting analysis",
    allSignalsAssigned: "All signals assigned",
    criticalFindings: "{count} critical findings",
    dataNeedsReview: "Hardware data awaits human review",
    solverIncomplete: "Solver incomplete; optimality is unknown",
    download: "Download plan",
    print: "Print plan",
    newProject: "New project",
    evidence: "Data evidence",
    exportDiagram: "Export SVG diagram",
    diagramHint: "Click a module to highlight its connections",
    wizardTitle: "Create hardware project",
    evidenceTitle: "Hardware data evidence",
    cancel: "Cancel",
    createProject: "Create & analyze",
    existingProject: "Existing project folder",
    optional: "Optional",
    projectPathHint:
      "Optionally scan code, CubeMX, and KiCad files in read-only mode; leave empty to plan a new project.",
    chip: "Controller",
    chipSearch: "Search controller models…",
    moduleSearch: "Search sensors, communication, or actuators…",
    strategy: "Allocation strategy",
    recommended: "Best quality · prefer low-risk pins",
    minChange: "Minimum change · preserve existing wiring",
    projectModules: "Project modules",
    notes: "Add project notes",
    startScan: "Scan project",
    scanHint: "Scans normally finish within one second and never upload files",
    savedProjects: "Open saved project",
    ecosystem: "Extension packages",
    ecosystemHint:
      "Install data, rule, or plugin packages after manifest, version, schema, and optional SHA-256 checks.",
    install: "Validate and install",
    results: "Architecture & diagnostics",
    architecture: "Architecture",
    pinTable: "Pin table",
    riskDiagnosis: "Risk review",
    architectureTitle: "System architecture",
    architectureCopy:
      "Visual connections between the controller, peripherals, and assigned pins",
    dataSignal: "Data signal",
    power: "Power",
    lowRisk: "Low risk",
    waiting: "Waiting to scan",
    preparing: "Preparing diagnostics…",
    reading: "Reading the current project configuration.",
    errors: "Critical",
    warnings: "Warnings",
    tips: "Suggestions",
    issues: "Findings",
    all: "All",
    severe: "Critical",
    caution: "Warning",
    advice: "Suggestion",
    plans: "Feasible plans",
    planHint: "Apply a plan, then lock pins or run another check",
    pinDetails: "Pin allocation details",
    lock: "Lock",
    moduleSignal: "Module / signal",
    controllerPin: "Controller pin",
    function: "Function",
    score: "Score",
    reason: "Selection reason",
    exports: "Developer exports",
    exportHint: "Generate pin definitions for your development environment",
    footer: "EmbedPinDoctor · Personal hardware design assistant",
    doctorAdvice: "Recommended fix",
    selected: "{count} selected",
    connections: "{count} connections",
    issueCount: "{count} findings",
    planCount: "{count} plans",
    scanning: "Scanning…",
    scanDone: "Completed · {seconds}s",
    healthy: "Project looks healthy",
    healthySummary:
      "No obvious pin or electrical risks were found. You can continue to the next design step.",
    needsFix: "Immediate action required",
    needsFixSummary:
      "Found {count} critical issues. Fix them before prototyping.",
    canImprove: "Healthy overall, with room to improve",
    canImproveSummary:
      "No hard conflicts found; review {count} design details.",
    readOnly:
      "The online demo is read-only. Download the project for full local functionality.",
    scanComplete: "Project scan complete",
    recheckComplete: "Recheck complete",
    diagnosisInfo: "Found {count} diagnostic findings",
    versionLocal: "v{version} · Local service",
    versionDemo: "v{version} · Online demo",
    recommendedPlan: "Recommended",
    alternativePlan: "Alternative {count}",
    currentPlan: "Current plan",
    applyPlan: "Apply",
    pinScore: "Pin score",
    noModules: "No matching modules",
  },
};

let currentLocale =
  localStorage.getItem("embedpindoctor.locale") ||
  (navigator.language.startsWith("zh") ? "zh" : "en");

function translate(key, values = {}) {
  let value = messages[currentLocale][key] ?? messages.zh[key] ?? key;
  Object.entries(values).forEach(([name, replacement]) => {
    value = value.replace(`{${name}}`, replacement);
  });
  return value;
}

function applyLanguage() {
  document.documentElement.lang = currentLocale === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = translate(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = translate(element.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.title = translate(element.dataset.i18nTitle);
    element.setAttribute("aria-label", element.title);
  });
  const select = document.getElementById("languageSelect");
  if (select) select.value = currentLocale;
  document.dispatchEvent(
    new CustomEvent("languagechange", { detail: { locale: currentLocale } }),
  );
}

function setLocale(locale) {
  if (!messages[locale]) return;
  currentLocale = locale;
  localStorage.setItem("embedpindoctor.locale", locale);
  applyLanguage();
}

window.I18N = {
  t: translate,
  setLocale,
  applyLanguage,
  get locale() {
    return currentLocale;
  },
};
