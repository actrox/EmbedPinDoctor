# EmbedPinDoctor

EmbedPinDoctor 是一个面向嵌入式开发的引脚规划和风险检查原型工具。

当前版本完成 P0 命令行原型：

- 读取芯片 JSON 数据。
- 读取模块 JSON 数据。
- 根据模块接口需求自动分配引脚。
- 检查重复占用、调试脚、启动脚、电压不匹配、I2C 上拉提醒、SPI 片选等风险。
- 导出 Markdown 接线文档和风险报告。

## 快速运行

```bash
python app/cli.py --chip stm32f103c8t6 --modules oled_i2c mpu6050 button buzzer sd_card --out output/demo_wiring.md
```

## 目录结构

```text
app/              命令行入口
core/             核心数据模型、加载、分配、检查逻辑
data/chips/       芯片 JSON 数据
data/modules/     模块 JSON 数据
export/           Markdown 导出逻辑
output/           生成结果
tests/            P0 验证脚本
```
