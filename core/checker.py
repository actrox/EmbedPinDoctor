import re
from collections import defaultdict

_BUS_FUNCTION = re.compile(r'^(I2C|SPI|UART|USART)\d*_(SCL|SDA|SCK|MISO|MOSI)$')


def _shared_functions(chip):
    """从芯片引脚数据动态推导可共享的总线信号集合。"""
    result = set()
    for pin in chip.get("pins", []):
        for func in pin.get("functions", []):
            if _BUS_FUNCTION.match(func):
                result.add(func)
    return result


def _pin_map(chip):
    return {pin["name"]: pin for pin in chip["pins"]}


def _risk(level, code, message, suggestion, item=None, pin=None, confidence="high"):
    base_weight = {"错误": 25, "警告": 10, "提示": 2}.get(level, 2)
    confidence_factor = {"high": 1.0, "medium": 0.75, "low": 0.5}.get(confidence, 0.5)
    return {
        "level": level, "code": code, "message": message,
        "suggestion": suggestion, "item": item or {}, "pin": pin,
        "confidence": confidence,
        "weight": round(base_weight * confidence_factor, 2),
    }


def _requirement_map(modules):
    result = {}
    for module in modules:
        for requirement in module.get("requirements", []):
            result[(module["id"], requirement["module_pin"])] = (module, requirement)
    return result


def check_project(chip, modules, allocation):
    risks = []
    pins = _pin_map(chip)
    requirements = _requirement_map(modules)
    shared_funcs = _shared_functions(chip)
    assigned = [item for item in allocation if item["chip_pin"] != "未分配"]
    grouped = defaultdict(list)
    for item in assigned:
        grouped[item["chip_pin"]].append(item)

    if not chip.get("verified", False):
        risks.append(_risk(
            "提示", "data_unverified",
            f"{chip['name']} 引脚数据尚未完成人工签字复核（当前可信度：{chip.get('confidence', 'low')}）。",
            f"打样前请对照 {chip.get('source', '官方数据手册')} 复核相关引脚，并在数据文件中记录审核人和日期。",
            {"chip": chip["id"], "data_status": chip.get("data_status")}, confidence="high",
        ))

    for pin_name, items in grouped.items():
        functions = {item["function"] for item in items}
        if len(items) > 1 and not functions.issubset(shared_funcs):
            risks.append(_risk("错误", "pin_duplicate", f"{pin_name} 被多个非共享信号占用。", "为其中一个信号重新分配空闲引脚。", {"pin": pin_name}, pin_name))

    for item in allocation:
        if item["chip_pin"] == "未分配":
            code = "locked_pin_conflict" if item.get("locked") else "unassigned"
            message = f"{item['module_name']} 的 {item['module_pin']} 锁定条件无法满足。" if item.get("locked") else f"{item['module_name']} 的 {item['module_pin']} 没有可用引脚。"
            risks.append(_risk("错误", code, message, "检查锁定引脚的功能、方向和占用情况，或解除锁定后重新求解。" if item.get("locked") else "更换芯片、减少模块、放宽锁定条件，或手动选择兼容引脚。", item))
            continue
        pin = pins.get(item["chip_pin"])
        if not pin:
            risks.append(_risk("错误", "unknown_pin", f"{item['chip_pin']} 不在当前芯片引脚库中。", "选择当前芯片存在的引脚。", item, item["chip_pin"]))
            continue
        tags = set(pin.get("tags", []))
        module, requirement = requirements.get((item.get("module_id"), item.get("module_pin")), ({}, {}))
        direction = item.get("direction") or requirement.get("direction", "bidirectional")

        if direction in {"output", "bidirectional"} and "input_only" in tags:
            risks.append(_risk("错误", "output_on_input_only", f"{item['chip_pin']} 是输入专用引脚，不能驱动 {item['module_name']} 的 {item['module_pin']}。", "改用支持输出的 GPIO。", item, item["chip_pin"]))
        if "debug" in tags:
            risks.append(_risk("警告", "debug_pin", f"{item['chip_pin']} 是调试引脚，可能影响下载和调试。", "优先改用普通 GPIO，保留调试接口。", item, item["chip_pin"]))
        if "boot" in tags:
            risks.append(_risk("警告", "boot_pin", f"{item['chip_pin']} 是启动配置相关引脚，外接电路可能影响启动。", "核对上电默认电平和外部上下拉，必要时更换普通 GPIO。", item, item["chip_pin"]))
        if item["function"] not in pin.get("functions", []):
            risks.append(_risk("错误", "function_mismatch", f"{item['chip_pin']} 不支持 {item['function']}。", "选择支持该外设功能的引脚。", item, item["chip_pin"]))
        if requirement.get("requires_five_v_tolerant") and "five_v_tolerant" not in tags:
            risks.append(_risk("错误", "five_v_tolerance_required", f"{item['chip_pin']} 未标记为 5V 容忍，但该信号要求 5V 容忍输入。", "增加电平转换，或改用明确标记为 5V 容忍的引脚。", item, item["chip_pin"]))
        if requirement.get("requires_open_drain") and not chip.get("supports_open_drain", False):
            risks.append(_risk("错误", "open_drain_unsupported", f"{chip['name']} 数据未声明支持开漏输出，无法安全驱动 {item['function']}。", "确认芯片开漏能力或增加外部开漏缓冲器。", item, item["chip_pin"], confidence="medium"))

        drive_current = requirement.get("drive_current_ma")
        current_limit = pin.get("max_output_current_ma", chip.get("default_max_output_current_ma"))
        if direction in {"output", "bidirectional"} and drive_current is not None and current_limit is not None and drive_current > current_limit:
            risks.append(_risk("错误", "drive_current_exceeded", f"{item['module_name']} 预计需要 {drive_current}mA，超过 {item['chip_pin']} 的建议输出能力 {current_limit}mA。", "使用三极管、MOSFET 或专用驱动器，避免由 GPIO 直接供电。", item, item["chip_pin"]))

        logic_voltage = module.get("logic_voltage")
        max_input = pin.get("absolute_max_input_voltage", chip.get("absolute_max_input_voltage"))
        if direction in {"input", "bidirectional"} and logic_voltage and max_input and logic_voltage > max_input and "five_v_tolerant" not in tags:
            risks.append(_risk("错误", "input_overvoltage", f"{item['module_name']} 的 {item['module_pin']} 可能向 {item['chip_pin']} 输入 {logic_voltage}V，超过允许值 {max_input}V。", "增加电平转换或分压，并核对输入阈值和瞬态电压。", item, item["chip_pin"]))

    for module in modules:
        module_voltage = module.get("voltage")
        if module_voltage and module_voltage != chip.get("voltage") and not module.get("voltage_tolerant", False):
            risks.append(_risk("警告", "voltage_mismatch", f"{module['name']} 工作电压为 {module_voltage}，芯片 IO 电压为 {chip.get('voltage')}。", "确认模块逻辑阈值、电平转换、电源和输入范围，不要仅凭供电电压判断兼容。", {"module": module["name"]}, confidence="medium"))
        if module.get("needs_pullup"):
            pullup_voltage = module.get("pullup_voltage", module.get("logic_voltage"))
            level_note = f"，上拉电压应不高于 {chip.get('absolute_max_input_voltage')}V" if pullup_voltage else ""
            risks.append(_risk("提示", "pullup_required", f"{module['name']} 使用 I2C，请确认 SDA/SCL 已有合适上拉电阻。", f"检查模块板载电阻，并根据总线长度和速率计算等效上拉{level_note}。", {"module": module["name"]}))

    spi_modules = [module for module in modules if any(req["function"].startswith("SPI") for req in module["requirements"])]
    if len(spi_modules) > 1:
        risks.append(_risk("提示", "spi_cs", "多个 SPI 模块共用总线时，每个模块都需要独立片选 CS 引脚。", "为每个 SPI 从设备预留独立 GPIO 作为 CS。"))

    i2c_addresses = defaultdict(list)
    for module in modules:
        if module.get("i2c_address") is not None:
            i2c_addresses[(module.get("i2c_bus", "I2C1"), str(module["i2c_address"]).lower())].append(module)
    for (bus, address), address_modules in i2c_addresses.items():
        if len(address_modules) > 1:
            names = "、".join(module["name"] for module in address_modules)
            risks.append(_risk("错误", "i2c_address_conflict", f"{names} 在 {bus} 上使用相同地址 {address}。", "修改其中一个器件的地址选择脚、使用 I2C 复用器，或移动到另一条总线。", {"bus": bus, "address": address, "modules": [module["id"] for module in address_modules]}))

    spi_groups = defaultdict(list)
    for module in spi_modules:
        spi_groups[module.get("spi_bus", "SPI1")].append(module)
    for bus, bus_modules in spi_groups.items():
        modes = {module.get("spi_mode") for module in bus_modules if module.get("spi_mode") is not None}
        if len(modes) > 1:
            risks.append(_risk("警告", "spi_mode_mixed", f"{bus} 上的设备需要不同 SPI 模式：{', '.join(map(str, sorted(modes)))}。", "每次切换片选设备时同步重设 CPOL/CPHA，并确认驱动不会并发访问总线。", {"bus": bus, "modes": sorted(modes)}, confidence="medium"))
        frequencies = [module.get("spi_max_hz") for module in bus_modules if module.get("spi_max_hz")]
        if frequencies and len(set(frequencies)) > 1:
            risks.append(_risk("提示", "spi_frequency_limit", f"{bus} 共用设备的最高频率不同，整条总线的安全公共频率为 {min(frequencies)}Hz。", "按设备分别配置频率，或将初始化默认值限制为最慢设备的上限。", {"bus": bus, "safe_hz": min(frequencies)}))

    for module in modules:
        if module.get("uart_requires_flow_control"):
            functions = {requirement["function"] for requirement in module["requirements"]}
            if not {"UART_CTS", "UART_RTS"}.issubset(functions):
                risks.append(_risk("警告", "uart_flow_control_missing", f"{module['name']} 声明需要硬件流控，但未同时分配 CTS/RTS。", "为模块补充 UART_CTS 和 UART_RTS 需求，或确认固件与模块均关闭硬件流控。", {"module": module["id"]}))

    timer_frequencies = defaultdict(list)
    for item in assigned:
        module, requirement = requirements.get((item.get("module_id"), item.get("module_pin")), ({}, {}))
        pin = pins.get(item["chip_pin"], {})
        timer = pin.get("timer")
        frequency = requirement.get("pwm_frequency_hz")
        if item.get("function") == "PWM" and timer and frequency:
            timer_frequencies[timer].append((frequency, item))
    for timer, entries in timer_frequencies.items():
        frequencies = {frequency for frequency, _ in entries}
        if len(frequencies) > 1:
            risks.append(_risk("错误", "pwm_timer_frequency_conflict", f"{timer} 上的 PWM 信号要求不同频率：{', '.join(map(str, sorted(frequencies)))}Hz。", "将信号分配到不同定时器，或统一同一定时器通道的周期配置。", {"timer": timer, "frequencies": sorted(frequencies)}))

    if not risks:
        risks.append(_risk("提示", "no_major_risk", "当前接线方案未发现必须修改的问题。", "仍需结合原理图、电源和芯片手册进行最终确认。"))
    return risks
