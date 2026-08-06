# EmbedPinDoctor

EmbedPinDoctor（引脚医生）是一个本地运行的嵌入式硬件设计辅助工具。选择主控和项目模块后，它可以自动规划引脚、检查常见设计风险，并给出可执行的修改建议。

当前版本包含：

- Web 诊断工作台和命令行工具。
- 根据外设约束自动分配主控引脚，并提供备选方案接口。
- 检查重复占用、功能不匹配、调试脚、启动脚、电压、I2C 上拉和 SPI 片选等风险。
- 生成项目健康评分和分级修复建议。
- 保存项目，导出 Markdown、`pins.h`、Arduino、STM32 HAL、ESP-IDF、KiCad 和 PlatformIO 文件。
- 芯片、模块、规则包、插件、备份和诊断包扩展机制。

## 启动 Web 工作台

```bash
python start_embedpindoctor.py
```

浏览器打开 `http://127.0.0.1:8765/`。

如需检查已有工程，在“现有工程目录”中填写本机项目的绝对路径。工具会以只读方式识别 PlatformIO、Arduino、ESP-IDF、STM32CubeMX 和 KiCad 文件，并在诊断结果中标出来源文件与行号。留空时仍可用于规划新项目。

引脚分配支持“最佳质量”和“最小变更”两种策略。展开引脚详情后可以锁定必须保留的接线；诊断结果会提供推荐方案和真实备选方案，并说明每路引脚的选择理由。

项目保存采用原子写入并保留最多 30 个历史版本，可在顶部使用“撤销保存”和“重做保存”。旧项目会在首次打开时自动迁移到当前 schema。

“扩展包管理”支持安装 `data`、`rules` 和 `plugin` 三类本地生态包。每个包必须提供 `manifest.json`，可以声明 `min_app_version` 和覆盖全部文件的 SHA-256 校验表；系统默认拒绝版本降级。

## Windows 发布构建

安装 PyInstaller 后运行 `build_windows.bat`。生成的单文件位于 `dist\EmbedPinDoctor.exe`；运行数据写入 `%LOCALAPPDATA%\EmbedPinDoctor`。诊断包默认不包含项目文件。

## 命令行示例

```bash
python app/cli.py --chip stm32f103c8t6 --modules oled_i2c mpu6050 button buzzer sd_card --out output/demo_wiring.md
```

## 目录结构

```text
app/              Web 服务和命令行入口
web/              本地诊断工作台
core/             加载、引脚分配和风险检查逻辑
data/chips/       芯片 JSON 数据
data/modules/     模块 JSON 数据
quality/          设计审查和规则包
integrations/     KiCad、PlatformIO 等集成
export/           文档和代码模板导出
output/           生成结果
tests/            回归验证脚本
```

## 验证

```bash
python -m quality.data_audit
python tests/p1_project_scan_test.py
python tests/p2_recommendation_test.py
python run_tests.py
```

硬件数据采用版本化 JSON Schema，并明确区分机器校验与人工签字状态。当前仍是 Alpha 版本；诊断结果用于设计辅助，打样前仍应结合芯片数据手册、原理图和实物电气测试复核。
