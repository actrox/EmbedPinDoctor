from collections import defaultdict

SHARED_FUNCTIONS = {"I2C1_SCL", "I2C1_SDA", "SPI1_SCK", "SPI1_MISO", "SPI1_MOSI"}


def _pin_map(chip):
    return {pin["name"]: pin for pin in chip["pins"]}


def _risk(level, code, message, suggestion, item=None, pin=None):
    return {"level": level, "code": code, "message": message, "suggestion": suggestion, "item": item or {}, "pin": pin}


def check_project(chip, modules, allocation):
    risks = []
    pins = _pin_map(chip)
    assigned = [item for item in allocation if item["chip_pin"] != "未分配"]
    grouped = defaultdict(list)
    for item in assigned:
        grouped[item["chip_pin"]].append(item)

    for pin_name, items in grouped.items():
        functions = {item["function"] for item in items}
        if len(items) > 1 and not functions.issubset(SHARED_FUNCTIONS):
            risks.append(_risk("错误", "pin_duplicate", f"{pin_name} 被多个非共享信号占用。", "为其中一个信号重新分配空闲引脚。", {"pin": pin_name}, pin_name))

    for item in allocation:
        if item["chip_pin"] == "未分配":
            risks.append(_risk("错误", "unassigned", f"{item['module_name']} 的 {item['module_pin']} 没有可用引脚。", "更换芯片、减少模块，或手动选择兼容引脚。", item))
            continue
        pin = pins.get(item["chip_pin"])
        if not pin:
            risks.append(_risk("错误", "unknown_pin", f"{item['chip_pin']} 不在当前芯片引脚库中。", "选择当前芯片存在的引脚。", item, item["chip_pin"]))
            continue
        tags = set(pin.get("tags", []))
        if "debug" in tags:
            risks.append(_risk("警告", "debug_pin", f"{item['chip_pin']} 是调试引脚，可能影响下载和调试。", "优先改用普通 GPIO，保留调试接口。", item, item["chip_pin"]))
        if "boot" in tags:
            risks.append(_risk("警告", "boot_pin", f"{item['chip_pin']} 是启动相关引脚，外接电路可能影响启动。", "确认上电默认电平，必要时更换普通 GPIO。", item, item["chip_pin"]))
        if item["function"] not in pin.get("functions", []):
            risks.append(_risk("错误", "function_mismatch", f"{item['chip_pin']} 不支持 {item['function']}。", "选择支持该外设功能的引脚。", item, item["chip_pin"]))

    for module in modules:
        module_voltage = module.get("voltage")
        if module_voltage and module_voltage != chip.get("voltage") and not module.get("voltage_tolerant", False):
            risks.append(_risk("警告", "voltage_mismatch", f"{module['name']} 工作电压为 {module_voltage}，芯片 IO 电压为 {chip.get('voltage')}。", "确认电平转换、电源和输入范围，不要直接假设兼容。", {"module": module["name"]}))
        if module.get("needs_pullup"):
            risks.append(_risk("提示", "pullup_required", f"{module['name']} 使用 I2C，请确认 SDA/SCL 已有合适上拉电阻。", "检查模块板载电阻，并根据总线长度和速率计算等效上拉。", {"module": module["name"]}))

    spi_modules = [m for m in modules if any(req["function"].startswith("SPI") for req in m["requirements"])]
    if len(spi_modules) > 1:
        risks.append(_risk("提示", "spi_cs", "多个 SPI 模块共用总线时，每个模块都需要独立片选 CS 引脚。", "为每个 SPI 从设备预留独立 GPIO 作为 CS。"))

    if not risks:
        risks.append(_risk("提示", "no_major_risk", "当前接线方案未发现必须修改的问题。", "仍需结合原理图、电源和芯片手册进行最终确认。"))
    return risks
