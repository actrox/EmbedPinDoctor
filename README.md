# EmbedPinDoctor

[![Version](https://img.shields.io/badge/version-0.1.0--alpha.8-blue)](VERSION)
[![Python](https://img.shields.io/badge/python-3.11%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

EmbedPinDoctor（引脚医生）是一个本地运行的嵌入式硬件设计辅助工具。选择主控和项目模块后，它可以自动规划引脚、检查常见设计风险，并给出可执行的修改建议。

当前版本 `0.1.0-alpha.8` 已完成 P0-P4 所有里程碑，包含完整的引脚规划、风险诊断、工程扫描、推荐闭环、发布管理和生态扩展能力。

## 功能特性

### 核心诊断（P0 可信诊断）
- 版本化 JSON Schema 描述芯片和模块数据，支持整包导入校验
- 数据审计命令区分机器校验与人工签字状态
- 有界回溯引脚分配算法，保证确定性并优先寻找完整可行方案
- 输入专用脚、输入过压、GPIO 过流、5V 容忍和开漏能力检查
- 风险评分加入置信度权重，未人工签字的数据明确提示

### 工程扫描（P1 只读扫描）
- 支持 PlatformIO、Arduino、ESP-IDF、STM32CubeMX（.ioc）和 KiCad 工程只读识别
- 引脚引用记录来源文件、行号、原始片段和置信度
- 三方差异诊断：扫描结果 vs 手工接线 vs 医生推荐方案
- Web 工作台展示扫描摘要、来源列表和可复制修复片段

### 推荐闭环（P2 增强修复）
- 引脚锁定功能，保留必须的接线
- "最佳质量"和"最小变更"两种分配策略
- 多路引脚选择理由说明
- 多方案枚举和方案差异对比
- I2C 地址、SPI 模式与频率、UART 硬件流控、PWM 定时器频率专项检查

### 发布与日常可用性（P3）
- 项目 Schema v1 → v2 自动迁移
- 原子写入项目文件，保留最多 30 个历史版本
- 撤销保存 / 重做保存
- 启动器动态端口与健康检查
- 轮转日志与未捕获异常记录
- 单文件运行时数据写入 `%LOCALAPPDATA%\EmbedPinDoctor`
- Windows 单文件 PyInstaller 构建与发布校验
- Python 3.11 / 3.12 CI 验证

### 数据与插件生态（P4）
- 生态包三类：`data`（芯片/模块数据）、`rules`（规则包）、`plugin`（插件）
- 每个包提供 `manifest.json`，支持语义版本、`min_app_version` 和 SHA-256 校验表
- 事务式安装 / 覆盖备份 / 安全卸载 / 降级保护
- 插件 capability 白名单与错误隔离
- 内置插件与用户插件合并发现
- Web 工作台内置"扩展包管理"入口

### 用户界面与入口
- Web 诊断工作台（本地 HTTP 服务）
- 命令行工具（`app/cli.py`）
- Windows 一键启动脚本
- 健康评分与分级修复建议

## 快速开始

### 启动 Web 工作台

```bash
python start_embedpindoctor.py
```

浏览器自动打开 `http://127.0.0.1:8765/`。

如需检查已有工程，在"现有工程目录"中填写本机项目的绝对路径。工具会以只读方式识别 PlatformIO、Arduino、ESP-IDF、STM32CubeMX 和 KiCad 文件，并在诊断结果中标出来源文件与行号。留空时仍可用于规划新项目。

### 命令行示例

```bash
# STM32 + 多模块诊断，导出 Markdown
python app/cli.py --chip stm32f103c8t6 --modules oled_i2c mpu6050 button buzzer sd_card --out output/demo_wiring.md

# 数据审计（检查内置芯片/模块数据完整性）
python -m quality.data_audit

# 核心算法回归测试
python -m unittest tests.test_core -v
```

## 内置芯片与模块

### 支持的主控芯片
- **STM32F103C8T6**（Cortex-M3，LQFP48）
- **STM32F401CCU6**（Cortex-M4，UFQFPN48）
- **ESP32-WROOM-32**（Xtensa LX6 双核，Wi-Fi + BT）
- **ESP32-S3-WROOM-1**（Xtensa LX7 双核，Wi-Fi + BLE）
- **RP2040**（Cortex-M0+ 双核，树莓派）
- **nRF52840**（Cortex-M4，BLE 5.0）

### 内置模块库
| 模块 | 类型 | 主要接口 |
|------|------|----------|
| OLED SSD1306 | 显示 | I2C |
| MPU-6050 | 六轴 IMU | I2C |
| 按钮（低电平有效） | 输入 | GPIO |
| 无源蜂鸣器 | 输出 | PWM |
| SD 卡模块 | 存储 | SPI |
| WS2812 灯带 | LED | PWM（单线） |
| 旋转编码器 | 输入 | GPIO x2 + SW |
| 继电器模块 | 输出 | GPIO（光耦） |
| TB6612 电机驱动 | 驱动 | PWM x2 + IN4 |
| LoRaWAN UART 模组 | 通信 | UART |
| 模拟传感器 | 输入 | ADC |
| DHT22 温湿度传感器 | 传感器 | GPIO（单总线） |
| DS18B20 温度传感器 | 传感器 | GPIO（1-Wire） |
| CAN 收发器 | 通信 | CAN |
| RS485 模块 | 通信 | UART + GPIO |
| NEO-6M GPS | 定位 | UART |
| ESP32-CAM 摄像头 | 视觉 | UART |
| 自定义测试模块 | 示例 | 混合 |

## 导出格式

- Markdown 接线文档
- `pins.h` C/C++ 引脚宏定义
- Arduino 初始化代码
- STM32 HAL 初始化代码片段
- ESP-IDF 配置片段
- KiCad 标签 / 网表提示
- PlatformIO 项目骨架提示
- STM32CubeMX `.ioc` 提示片段

## 目录结构

```text
EmbedPinDoctor/
├── app/                    # Web 服务（web_app.py）和 CLI 入口（cli.py）
├── web/                    # 前端诊断工作台（index.html / app.js / styles.css）
├── core/                   # 核心引擎：加载、分配、检查、项目存储、Schema
│   ├── loader.py           # 芯片/模块数据加载器
│   ├── allocator.py        # 有界回溯引脚分配器
│   ├── checker.py          # 风险检查引擎
│   ├── project_store.py    # 原子存储 + 历史版本（撤销/重做）
│   └── schema.py           # JSON Schema 与数据版本管理
├── data/                   # 内置数据库
│   ├── chips/              # 芯片 JSON 定义
│   ├── modules/            # 模块 JSON 定义
│   └── schemas/            # chip.schema.json / module.schema.json
├── quality/                # 数据质量、设计审查、规则包
│   ├── data_audit.py       # 数据审计命令（python -m quality.data_audit）
│   ├── design_review.py    # 设计审查评分
│   └── rule_pack.py        # 规则包加载引擎
├── rule_packs/             # 规则包（内置 demo_pack + 用户导入）
├── integrations/           # 外部工程集成
│   ├── project_scanner.py  # 只读工程扫描（PlatformIO/Arduino/ESP-IDF/.ioc/KiCad）
│   ├── kicad_import.py     # KiCad 标签导入
│   ├── platformio.py       # PlatformIO ini 解析
│   ├── ioc_export.py       # STM32CubeMX .ioc 导出提示
│   ├── code_reverse.py     # C/C++ 引脚引用反查
│   ├── package_update.py   # 数据增量包导入
│   └── risk_explainer.py   # 风险解释器（通俗语言 + 修复片段）
├── export/                 # 文档与代码模板导出
│   ├── markdown.py         # Markdown 接线文档
│   ├── pins.py             # pins.h / Arduino / HAL / ESP-IDF
│   └── templates.py        # 模板字符串管理
├── versioning/             # 版本管理
│   ├── compare.py          # 方案差异比较
│   └── project_migration.py # 旧项目 Schema 自动迁移
├── ecosystem/              # 生态包管理
│   └── package_manager.py  # 事务式安装 / SHA-256 校验 / 降级保护
├── plugins/                # 插件系统
│   ├── registry.py         # 插件注册表、capability 白名单、错误隔离
│   └── demo_export_plugin/ # 示例导出插件
├── packages/               # 本地扩展包示例
│   └── demo_update_pack/   # 数据更新包示例
├── collaboration/          # 协作特性（锁、审计、审查）
├── diagnostics/            # 诊断包收集器
├── backup/                 # 项目 / 数据备份与恢复
├── release/                # 发布构建与校验
│   ├── build_release.py    # 发布打包
│   ├── validate_release.py # 发布完整性校验
│   ├── packager.py         # PyInstaller 封装逻辑
│   └── EmbedPinDoctor.spec # PyInstaller spec
├── utils/                  # 通用工具（日志配置等）
├── docs/                   # 验收报告、使用手册、审核清单
├── examples/               # 示例项目 JSON（ESP32/RP2040/STM32）
├── projects/               # 用户项目存储（原子写入 + 历史版本）
├── output/                 # 生成结果输出目录（运行时产生）
├── launcher.py             # 动态端口 + 健康检查启动器
├── start_embedpindoctor.py # 用户友好入口（自动打开浏览器）
├── build_windows.bat       # Windows PyInstaller 一键构建
├── requirements.txt        # 可选依赖（核心零依赖）
├── VERSION                 # 语义版本号
├── CHANGELOG.md            # 版本变更日志
└── README.md               # 本文件
```

## 数据审计

```bash
python -m quality.data_audit
```

## Windows 发布构建

```bash
pip install pyinstaller
build_windows.bat
```

生成的单文件位于 `dist\EmbedPinDoctor.exe`；运行数据写入 `%LOCALAPPDATA%\EmbedPinDoctor`。诊断包默认不包含项目文件。

## 扩展开发

### 新增芯片 / 模块
参考 `data/chips/stm32f103c8t6.json` 和 `data/modules/oled_i2c.json`，使用 `data/schemas/` 下的 Schema 校验后放入对应目录，或打包为生态包安装。

### 新增规则包
参考 `rule_packs/demo_pack/`，提供 `manifest.json` 与 `rules/*.json`。

### 新增插件
参考 `plugins/demo_export_plugin/`，声明 `plugin.json` 和 capability 白名单。

## 注意事项

- 当前仍为 **Alpha** 版本，诊断结果仅用于设计辅助。
- 打样前请结合芯片数据手册、原理图和实物电气测试复核。
- 项目存储默认保留 30 个历史版本，位于 `projects/.history/`（被 `.gitignore` 忽略）。

## 版本与变更历史

详见 [CHANGELOG.md](CHANGELOG.md) 和 [VERSION](VERSION)。

---

**EmbedPinDoctor** · 本地运行 · 零核心依赖 · 从引脚规划到设计审查的嵌入式硬件设计辅助工具
