def _macro_name(value):
    return value.upper().replace(" ", "_").replace("-", "_").replace("/", "_")


def _stm32_pin_parts(pin_name):
    if len(pin_name) < 3 or not pin_name.startswith("P"):
        return None, None
    return "GPIO" + pin_name[1], "GPIO_PIN_" + pin_name[2:]


def render_pins_header(chip, allocation):
    lines = []
    guard = "EMBED_PIN_DOCTOR_PINS_H"
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append("")
    lines.append(f"// 芯片：{chip['name']}")
    lines.append("// 本文件由 EmbedPinDoctor 自动生成，请在修改接线后重新导出。")
    lines.append("")

    for item in allocation:
        if item["chip_pin"] == "未分配":
            continue
        prefix = _macro_name(f"{item['module_id']}_{item['module_pin']}")
        port, pin = _stm32_pin_parts(item["chip_pin"])
        if port and pin:
            lines.append(f"#define {prefix}_PORT {port}")
            lines.append(f"#define {prefix}_PIN {pin}")
        else:
            lines.append(f"#define {prefix}_PIN {item['chip_pin']}")
        lines.append("")

    lines.append(f"#endif // {guard}")
    return "\n".join(lines) + "\n"
