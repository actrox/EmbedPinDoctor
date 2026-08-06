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
python run_tests.py
```

> 当前仍是 Alpha 版本。诊断结果用于设计辅助，打样前仍应结合芯片数据手册、原理图和实物电气测试复核。
