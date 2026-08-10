#!/usr/bin/env python3
"""芯片数据生成工具：模板生成、最终化、去重。"""
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


TAG_HINT = {
    "input_only": "仅输入，不能做输出",
    "debug": "SWD/JTAG 调试脚",
    "boot": "启动配置脚，外接电路会影响启动",
    "default_high": "上电默认高电平",
    "five_v_tolerant": "5V 容忍输入",
    "nfc": "NFC 天线脚，默认不做 GPIO",
    "boot2": "QSPI FLASH 专用",
}


PIN_FAMILIES = {
    "stm32l4xx": {
        "ports": [
            ("PA", 0, 15),
            ("PB", 0, 15),
            ("PC", 13, 15),
            ("PH", 0, 1),
        ],
    },
    "stm32f0xx": {
        "ports": [
            ("PA", 0, 15),
            ("PB", 0, 15),
            ("PF", 0, 1),
        ],
    },
    "atmega328p": {
        "arduino_d": (0, 13),
        "arduino_a": (0, 5),
    },
    "atmega2560": {
        "arduino_d": (0, 53),
        "arduino_a": (0, 15),
    },
    "esp32-c3": {
        "gpio": (0, 21),
    },
    "gd32f103": {
        "ports": [
            ("PA", 0, 15),
            ("PB", 0, 15),
            ("PC", 13, 15),
        ],
    },
}


GENERIC_QFP_VALID = {48, 64, 100, 144}


def _expand_pin_names(family_key: str) -> List[str]:
    family_key_lower = family_key.lower()

    if family_key_lower in PIN_FAMILIES:
        spec = PIN_FAMILIES[family_key_lower]
        pins: List[str] = []
        if "ports" in spec:
            for port, start, end in spec["ports"]:
                for i in range(start, end + 1):
                    pins.append(f"{port}{i}")
        if "arduino_d" in spec:
            start, end = spec["arduino_d"]
            for i in range(start, end + 1):
                pins.append(f"D{i}")
        if "arduino_a" in spec:
            start, end = spec["arduino_a"]
            for i in range(start, end + 1):
                pins.append(f"A{i}")
        if "gpio" in spec:
            start, end = spec["gpio"]
            for i in range(start, end + 1):
                pins.append(f"GPIO{i}")
        return pins

    m = re.match(r"^generic_qfp_(\d+)$", family_key_lower)
    if m:
        n = int(m.group(1))
        if n not in GENERIC_QFP_VALID:
            raise ValueError(
                f"generic_qfp_N 仅支持 N ∈ {sorted(GENERIC_QFP_VALID)}，收到 {n}"
            )
        return [f"PIN{i}" for i in range(1, n + 1)]

    raise ValueError(
        f"不支持的芯片家族: {family_key}。使用 'families' 命令查看支持的列表。"
    )


def _family_hint(family_key: str) -> str:
    family_key_lower = family_key.lower()
    if family_key_lower in PIN_FAMILIES:
        examples = {
            "stm32l4xx": "STM32L432KCU6、STM32L476RG 等",
            "stm32f0xx": "STM32F030K6T6、STM32F072C8T6 等",
            "atmega328p": "ATmega328P（Arduino UNO 命名）",
            "atmega2560": "ATmega2560（Arduino MEGA 命名）",
            "esp32-c3": "ESP32-C3-WROOM-02、ESP32-C3-MINI-1 等",
            "gd32f103": "GD32F103C8T6、GD32F103RCT6 等",
        }
        return examples.get(family_key_lower, family_key)
    m = re.match(r"^generic_qfp_(\d+)$", family_key_lower)
    if m:
        return f"通用 QFP{m.group(1)} 封装占位引脚"
    return family_key


def generate_chip_template(chip_family: str, output_path: str) -> str:
    pin_names = _expand_pin_names(chip_family)
    hint_text = _family_hint(chip_family)

    pins = []
    for name in pin_names:
        pins.append({
            "_hint": "通用脚示例：functions 可包含 GPIO/ADC/PWM/EXTI + 外设信号名（USART1_TX/I2C1_SCL 等）",
            "name": name,
            "functions": ["GPIO", "EXTI"],
            "timer": None,
            "adc_channel": None,
            "tags": [],
            "note": "",
        })

    template = {
        "_instructions": "请按模板填写，以 _ 开头的字段会被 finalize 自动剥离。_tag_hint 解释 tag 用法。",
        "_tag_hint": TAG_HINT,
        "schema_version": 1,
        "id": f"<芯片小写 ID，如 {chip_family.lower().replace('xx', 'xxx')}>",
        "name": f"<芯片官方型号全称，例如 {hint_text}>",
        "voltage": "3.3V",
        "io_voltage": 3.3,
        "absolute_max_input_voltage": 3.6,
        "default_max_output_current_ma": 8,
        "supports_open_drain": True,
        "pins": pins,
        "data_status": "review_required",
        "verified": False,
        "confidence": "medium",
        "source": "<请填入数据手册和表格编号>",
        "datasheet_url": "<请填入官方 PDF 链接>",
        "machine_checked_at": "<脚本会自动填 YYYY-MM-DD>",
        "verified_at": None,
        "verified_by": None,
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out.resolve())


def _strip_underscore_fields(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_underscore_fields(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_underscore_fields(item) for item in obj]
    return obj


def _validate_final(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for key in ("schema_version", "id", "name"):
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"根字段 {key} 必须非空")
    pins = data.get("pins")
    if not isinstance(pins, list):
        errors.append("pins 必须是数组")
        return errors
    for i, pin in enumerate(pins):
        if not isinstance(pin, dict):
            errors.append(f"pins[{i}] 必须是对象")
            continue
        name = pin.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"pins[{i}].name 必须是非空字符串")
        functions = pin.get("functions")
        if not isinstance(functions, list) or not functions:
            errors.append(f"pins[{i}].functions 必须是非空数组")
    return errors


def finalize_chip_template(template_path: str, output_path: str) -> Tuple[str, List[str]]:
    src = Path(template_path)
    if not src.exists():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    raw = json.loads(src.read_text(encoding="utf-8"))
    data = _strip_underscore_fields(raw)

    today_str = date.today().isoformat()
    placeholder = "<脚本会自动填 YYYY-MM-DD>"
    if data.get("machine_checked_at") in (None, "", placeholder):
        data["machine_checked_at"] = today_str

    errors = _validate_final(data)
    if errors:
        error_msg = "\n  - ".join(["校验失败："] + errors)
        raise ValueError(error_msg)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out.resolve()), errors


def _dedup_list(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def dedup_functions(chip_path: str, output_path: Optional[str] = None) -> Tuple[str, int]:
    src = Path(chip_path)
    if not src.exists():
        raise FileNotFoundError(f"芯片文件不存在: {chip_path}")

    data = json.loads(src.read_text(encoding="utf-8"))
    pins = data.get("pins")
    if not isinstance(pins, list):
        raise ValueError("芯片文件中 pins 字段不是数组")

    total_removed = 0
    for pin in pins:
        if not isinstance(pin, dict):
            continue
        functions = pin.get("functions")
        if isinstance(functions, list):
            orig_len = len(functions)
            deduped = _dedup_list(functions)
            if len(deduped) != orig_len:
                total_removed += orig_len - len(deduped)
                pin["functions"] = deduped

    target = Path(output_path) if output_path else src
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target.resolve()), total_removed


def list_families() -> List[str]:
    families = sorted(PIN_FAMILIES.keys(), key=str.lower)
    generic = [f"generic_qfp_{n}" for n in sorted(GENERIC_QFP_VALID)]
    return families + generic


def _print_help() -> None:
    print("用法:")
    print("  python tools/chip_data_generator.py template <family> <output.json>")
    print("  python tools/chip_data_generator.py finalize <template.json> <output.json>")
    print("  python tools/chip_data_generator.py dedup <chip.json> [output.json]")
    print("  python tools/chip_data_generator.py families")
    print()
    print("family 名大小写不敏感；支持 generic_qfp_48/64/100/144。")


def main(argv: Optional[List[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        _print_help()
        return 1

    cmd = args[0].lower()
    if cmd == "families":
        for name in list_families():
            print(name)
        return 0

    if cmd == "template":
        if len(args) < 3:
            print("错误: template 需要 <family> 和 <output.json>", file=sys.stderr)
            _print_help()
            return 2
        family = args[1]
        output = args[2]
        try:
            written = generate_chip_template(family, output)
        except ValueError as e:
            print(f"错误: {e}", file=sys.stderr)
            return 3
        print(f"模板已生成: {written}")
        return 0

    if cmd == "finalize":
        if len(args) < 3:
            print("错误: finalize 需要 <template.json> 和 <output.json>", file=sys.stderr)
            _print_help()
            return 2
        template = args[1]
        output = args[2]
        try:
            written, errors = finalize_chip_template(template, output)
        except FileNotFoundError as e:
            print(f"错误: {e}", file=sys.stderr)
            return 4
        except ValueError as e:
            print(f"{e}", file=sys.stderr)
            return 5
        print(f"已最终化: {written}")
        return 0

    if cmd == "dedup":
        if len(args) < 2:
            print("错误: dedup 需要 <chip.json>", file=sys.stderr)
            _print_help()
            return 2
        chip_file = args[1]
        output_file = args[2] if len(args) >= 3 else None
        try:
            written, removed = dedup_functions(chip_file, output_file)
        except FileNotFoundError as e:
            print(f"错误: {e}", file=sys.stderr)
            return 4
        except ValueError as e:
            print(f"错误: {e}", file=sys.stderr)
            return 5
        print(f"已写入: {written}；清理重复 functions 共 {removed} 项")
        return 0

    print(f"未知命令: {cmd}", file=sys.stderr)
    _print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
