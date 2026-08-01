def _macro(value):
    return value.upper().replace(" ", "_").replace("-", "_").replace("/", "_")


def render_arduino(chip, allocation):
    lines = ["// EmbedPinDoctor 生成的 Arduino 引脚定义", f"// 芯片：{chip['name']}", ""]
    for item in allocation:
        if item["chip_pin"] != "未分配":
            lines.append(f"#define {_macro(item['module_id'] + '_' + item['module_pin'])} {item['chip_pin']}")
    return "\n".join(lines) + "\n"


def render_stm32_hal(chip, allocation):
    lines = ["/* EmbedPinDoctor 生成的 STM32 HAL 引脚定义 */", f"/* 芯片：{chip['name']} */", ""]
    for item in allocation:
        pin = item["chip_pin"]
        if pin.startswith("P") and len(pin) >= 3:
            lines.append(f"#define {_macro(item['module_id'] + '_' + item['module_pin'])}_PORT GPIO{pin[1]}")
            lines.append(f"#define {_macro(item['module_id'] + '_' + item['module_pin'])}_PIN GPIO_PIN_{pin[2:]}")
    return "\n".join(lines) + "\n"


def render_esp_idf(chip, allocation):
    lines = ["// EmbedPinDoctor 生成的 ESP-IDF GPIO 定义", f"// 芯片：{chip['name']}", "", "#include <driver/gpio.h>", ""]
    for item in allocation:
        pin = item["chip_pin"].replace("GPIO", "")
        if pin.isdigit():
            lines.append(f"#define {_macro(item['module_id'] + '_' + item['module_pin'])}_GPIO GPIO_NUM_{pin}")
    return "\n".join(lines) + "\n"


def render_kicad_labels(chip, allocation):
    lines = [f"# EmbedPinDoctor KiCad 标签导出 - {chip['name']}", "# 名称\t芯片引脚\t功能"]
    for item in allocation:
        if item["chip_pin"] != "未分配":
            name = _macro(item["module_id"] + "_" + item["module_pin"])
            lines.append(f"{name}\t{item['chip_pin']}\t{item['function']}")
    return "\n".join(lines) + "\n"
