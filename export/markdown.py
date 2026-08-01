def render_markdown(chip, modules, allocation, risks, project_name="未命名项目", notes=""):
    lines = []
    lines.append(f"# {chip['name']} 接线规划报告")
    lines.append("")
    lines.append(f"- 项目名称：{project_name}")
    if notes:
        lines.append(f"- 项目备注：{notes}")
    lines.append("")
    lines.append("## 项目信息")
    lines.append("")
    lines.append(f"- 芯片：{chip['name']}")
    lines.append(f"- IO 电压：{chip.get('voltage', '未知')}")
    lines.append(f"- 模块数量：{len(modules)}")
    lines.append("")
    lines.append("## 模块清单")
    lines.append("")
    for module in modules:
        lines.append(f"- {module['name']}：{module.get('description', '')}")
    lines.append("")
    lines.append("## 接线表")
    lines.append("")
    lines.append("| 模块 | 模块引脚 | 芯片引脚 | 功能 | 说明 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in allocation:
        lines.append(f"| {item['module_name']} | {item['module_pin']} | {item['chip_pin']} | {item['function']} | {item.get('note', '')} |")
    lines.append("")
    lines.append("## 风险报告")
    lines.append("")
    for risk in risks:
        lines.append(f"- [{risk['level']}] {risk['message']}")
        if risk.get("suggestion"):
            lines.append(f"  - 建议：{risk['suggestion']}")
    lines.append("")
    lines.append("## 后续建议")
    lines.append("")
    lines.append("1. 画原理图前，确认所有启动脚和调试脚没有被高风险外设占用。")
    lines.append("2. 对 I2C 总线确认上拉电阻，对 SD 卡等模块确认 3.3V 电平兼容。")
    lines.append("3. 固件项目中保持接线表和引脚定义文件同步更新。")
    return "\n".join(lines) + "\n"
