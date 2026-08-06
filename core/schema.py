"""Dependency-free runtime validation for hardware data files.

The JSON Schema documents in ``data/schemas`` are the public contract.  This
module enforces the same critical invariants without adding a runtime package.
"""

SCHEMA_VERSION = 1
VALID_DATA_STATUSES = {"prototype", "review_required", "verified", "deprecated"}
VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_DIRECTIONS = {"input", "output", "bidirectional"}


class SchemaValidationError(ValueError):
    pass


def _fail(kind, path, message):
    raise SchemaValidationError(f"{kind} 数据 {path}: {message}")


def _require_text(data, key, kind, path):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        _fail(kind, path, f"{key} 必须是非空字符串")


def _require_bool(data, key, kind, path):
    if not isinstance(data.get(key), bool):
        _fail(kind, path, f"{key} 必须是布尔值")


def _require_number(data, key, kind, path, minimum=None):
    value = data.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        _fail(kind, path, f"{key} 必须是数字")
    if minimum is not None and value < minimum:
        _fail(kind, path, f"{key} 不能小于 {minimum}")


def validate_chip(chip):
    if not isinstance(chip, dict):
        _fail("芯片", "$", "根节点必须是对象")
    for key in ("id", "name", "voltage", "source", "datasheet_url"):
        _require_text(chip, key, "芯片", "$")
    if chip.get("schema_version") != SCHEMA_VERSION:
        _fail("芯片", "$", f"schema_version 必须为 {SCHEMA_VERSION}")
    if chip.get("data_status") not in VALID_DATA_STATUSES:
        _fail("芯片", "$", f"data_status 必须是 {sorted(VALID_DATA_STATUSES)} 之一")
    if chip.get("confidence") not in VALID_CONFIDENCE:
        _fail("芯片", "$", f"confidence 必须是 {sorted(VALID_CONFIDENCE)} 之一")
    _require_bool(chip, "verified", "芯片", "$")
    _require_number(chip, "io_voltage", "芯片", "$", 0)
    _require_number(chip, "absolute_max_input_voltage", "芯片", "$", 0)
    _require_number(chip, "default_max_output_current_ma", "芯片", "$", 0)
    _require_bool(chip, "supports_open_drain", "芯片", "$")
    pins = chip.get("pins")
    if not isinstance(pins, list) or not pins:
        _fail("芯片", "$.pins", "必须是非空数组")
    seen = set()
    for index, pin in enumerate(pins):
        path = f"$.pins[{index}]"
        if not isinstance(pin, dict):
            _fail("芯片", path, "必须是对象")
        _require_text(pin, "name", "芯片", path)
        if pin["name"] in seen:
            _fail("芯片", path, f"引脚名称重复: {pin['name']}")
        seen.add(pin["name"])
        functions = pin.get("functions")
        if not isinstance(functions, list) or not functions or not all(isinstance(item, str) and item for item in functions):
            _fail("芯片", path, "functions 必须是非空字符串数组")
        if len(set(functions)) != len(functions):
            _fail("芯片", path, "functions 不允许重复")
        tags = pin.get("tags")
        if not isinstance(tags, list) or not all(isinstance(item, str) and item for item in tags):
            _fail("芯片", path, "tags 必须是字符串数组")
        if "input_only" in tags and "GPIO" in functions and pin.get("output_capable", False):
            _fail("芯片", path, "input_only 与 output_capable=true 冲突")
    if chip["verified"] and chip["data_status"] != "verified":
        _fail("芯片", "$", "verified=true 时 data_status 必须为 verified")
    if chip["verified"] and not chip.get("verified_at"):
        _fail("芯片", "$", "verified=true 时必须填写 verified_at")
    return chip


def validate_module(module):
    if not isinstance(module, dict):
        _fail("模块", "$", "根节点必须是对象")
    for key in ("id", "name", "voltage", "source"):
        _require_text(module, key, "模块", "$")
    if module.get("schema_version") != SCHEMA_VERSION:
        _fail("模块", "$", f"schema_version 必须为 {SCHEMA_VERSION}")
    _require_number(module, "logic_voltage", "模块", "$", 0)
    if "i2c_address" in module and not isinstance(module["i2c_address"], (int, str)):
        _fail("模块", "$", "i2c_address 必须是整数或十六进制字符串")
    if "spi_mode" in module and module["spi_mode"] not in {0, 1, 2, 3}:
        _fail("模块", "$", "spi_mode 必须是 0、1、2 或 3")
    if "spi_max_hz" in module:
        _require_number(module, "spi_max_hz", "模块", "$", 1)
    if "uart_requires_flow_control" in module and not isinstance(module["uart_requires_flow_control"], bool):
        _fail("模块", "$", "uart_requires_flow_control 必须是布尔值")
    requirements = module.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        _fail("模块", "$.requirements", "必须是非空数组")
    seen = set()
    for index, requirement in enumerate(requirements):
        path = f"$.requirements[{index}]"
        if not isinstance(requirement, dict):
            _fail("模块", path, "必须是对象")
        for key in ("module_pin", "function", "direction"):
            _require_text(requirement, key, "模块", path)
        if requirement["module_pin"] in seen:
            _fail("模块", path, f"模块引脚重复: {requirement['module_pin']}")
        seen.add(requirement["module_pin"])
        if requirement["direction"] not in VALID_DIRECTIONS:
            _fail("模块", path, f"direction 必须是 {sorted(VALID_DIRECTIONS)} 之一")
        preferred = requirement.get("preferred_functions", [])
        if not isinstance(preferred, list) or not all(isinstance(item, str) and item for item in preferred):
            _fail("模块", path, "preferred_functions 必须是字符串数组")
        if requirement.get("share_bus") and not requirement.get("bus_key"):
            _fail("模块", path, "share_bus=true 时必须填写 bus_key")
        if "drive_current_ma" in requirement:
            _require_number(requirement, "drive_current_ma", "模块", path, 0)
        if "pwm_frequency_hz" in requirement:
            _require_number(requirement, "pwm_frequency_hz", "模块", path, 1)
    return module
