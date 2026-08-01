def render_ioc_hint(chip, allocation):
    lines = [f"# STM32CubeMX IOC 辅助片段 - {chip['name']}"]
    for item in allocation:
        if item["chip_pin"].startswith("P"):
            lines.append(f"{item['chip_pin']}.Signal={item['function']}")
            lines.append(f"{item['chip_pin']}.Label={item['module_id']}_{item['module_pin']}")
    return "\n".join(lines) + "\n"
