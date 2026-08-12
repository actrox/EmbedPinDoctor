"""Read-only embedded project discovery and pin extraction."""

from collections import defaultdict
from pathlib import Path
import configparser
import os
import re
import xml.etree.ElementTree as ET

MAX_FILES = 2000
MAX_FILE_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {".git", ".svn", ".hg", "node_modules", ".pio", "build", "dist", "output", "__pycache__", ".venv", "venv"}
TEXT_EXTENSIONS = {".h", ".hpp", ".c", ".cc", ".cpp", ".ino", ".ioc", ".ini", ".txt", ".net", ".kicad_sch"}

DIRECT_PIN_PATTERN = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+(GPIO_NUM_\d+|GPIO\d+|GP\d+|P[A-Z]\d+)\b")
NUMERIC_PIN_PATTERN = re.compile(r"^\s*(?:#\s*define\s+|(?:static\s+)?(?:const|constexpr)\s+(?:u?int\d*_t|int)\s+)([A-Za-z_]\w*(?:PIN|GPIO)\w*)\s*(?:=\s*)?(\d+)\s*;?")
PORT_PATTERN = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)_PORT\s+GPIO([A-Z])\b")
STM_PIN_PATTERN = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)_PIN\s+GPIO_PIN_(\d+)\b")
IOC_PATTERN = re.compile(r"^\s*(P[A-Z]\d+)\.(?:Signal|GPIO_Label|Label)\s*=\s*(.+?)\s*$")
KICAD_TEXT_PATTERN = re.compile(r"^\s*([A-Za-z_]\w*)\s+(GPIO\d+|GP\d+|P[A-Z]\d+)\b")
SIGNAL_ALIASES = {
    "OLED_CLK": "OLED_I2C_SCL", "DISPLAY_SCL": "OLED_I2C_SCL", "I2C_SCK": "OLED_I2C_SCL",
    "OLED_DATA": "OLED_I2C_SDA", "DISPLAY_SDA": "OLED_I2C_SDA", "I2C_DATA": "OLED_I2C_SDA",
    "LED_PIN": "WS2812_DIN", "NEOPIXEL_PIN": "WS2812_DIN",
}


class ProjectScanError(ValueError):
    pass


def _normal_symbol(value):
    normalized = re.sub(r"[^A-Z0-9]+", "_", str(value).upper()).strip("_")
    return SIGNAL_ALIASES.get(normalized, normalized)


def _canonical_pin(value, chip_hint=None):
    value = str(value).strip().upper()
    if value.startswith("GPIO_NUM_"):
        return "GPIO" + value.removeprefix("GPIO_NUM_")
    if value.isdigit():
        if chip_hint == "rp2040":
            return "GP" + value
        if chip_hint == "esp32-wroom-32":
            return "GPIO" + value
    return value


def _pin_use(symbol, pin, path, line, kind, snippet, confidence="high"):
    return {
        "symbol": _normal_symbol(symbol), "pin": pin, "source": str(path),
        "line": line, "kind": kind, "snippet": snippet.strip(), "confidence": confidence,
    }


def _read_lines(path):
    if path.stat().st_size > MAX_FILE_BYTES:
        return None
    return path.read_text(encoding="utf-8", errors="ignore").splitlines()


def _parse_code(path, chip_hint):
    lines = _read_lines(path)
    if lines is None:
        return [], [{"code": "file_too_large", "source": str(path), "message": "文件超过 2MB，已跳过"}]
    uses = []
    ports = {}
    stm_pins = []
    for line_no, line in enumerate(lines, 1):
        if match := PORT_PATTERN.match(line):
            ports[match.group(1)] = (match.group(2), line_no, line)
        if match := STM_PIN_PATTERN.match(line):
            stm_pins.append((match.group(1), match.group(2), line_no, line))
        if match := DIRECT_PIN_PATTERN.match(line):
            uses.append(_pin_use(match.group(1), _canonical_pin(match.group(2), chip_hint), path, line_no, "code", line))
        elif match := NUMERIC_PIN_PATTERN.match(line):
            uses.append(_pin_use(match.group(1), _canonical_pin(match.group(2), chip_hint), path, line_no, "code", line, "medium"))
    for base, number, line_no, line in stm_pins:
        if base in ports:
            port, _, _ = ports[base]
            uses.append(_pin_use(base, f"P{port}{number}", path, line_no, "code", line))
    return uses, []


def _parse_ioc(path):
    uses = []
    lines = _read_lines(path) or []
    for line_no, line in enumerate(lines, 1):
        match = IOC_PATTERN.match(line)
        if not match:
            continue
        pin, value = match.groups()
        if line.split("=", 1)[0].endswith(("GPIO_Label", "Label")):
            symbol = value
        else:
            symbol = value.replace("_", "_")
        uses.append(_pin_use(symbol, pin, path, line_no, "ioc", line))
    return uses


def _parse_kicad_text(path):
    uses = []
    lines = _read_lines(path) or []
    for line_no, line in enumerate(lines, 1):
        if match := KICAD_TEXT_PATTERN.match(line):
            uses.append(_pin_use(match.group(1), match.group(2), path, line_no, "kicad", line))
    return uses


def _parse_kicad_net(path):
    uses = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return uses
    for net in root.findall(".//net"):
        label = net.get("name") or f"NET_{net.get('code', 'UNKNOWN')}"
        for node in net.findall("node"):
            pin_function = node.get("pinfunction", "")
            if re.fullmatch(r"GPIO\d+|GP\d+|P[A-Z]\d+", pin_function, re.IGNORECASE):
                uses.append(_pin_use(label, pin_function.upper(), path, None, "kicad", ET.tostring(node, encoding="unicode"), "medium"))
    return uses


def _detect_platformio(path):
    result = {"type": "platformio", "source": str(path)}
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
        sections = [section for section in parser.sections() if section.startswith("env:")]
        if sections:
            section = sections[0]
            result.update(board=parser.get(section, "board", fallback=""), platform=parser.get(section, "platform", fallback=""), framework=parser.get(section, "framework", fallback=""))
    except configparser.Error:
        result["warning"] = "platformio.ini 无法完整解析"
    return result


def _discover_files(root):
    files = []
    skipped = []
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS and not (Path(current) / name).is_symlink())
        for name in sorted(names):
            path = Path(current) / name
            if path.is_symlink():
                continue
            if path.suffix.lower() in TEXT_EXTENSIONS or name in {"platformio.ini", "sdkconfig", "CMakeLists.txt"}:
                files.append(path)
                if len(files) >= MAX_FILES:
                    skipped.append({"code": "file_limit", "source": str(root), "message": f"达到 {MAX_FILES} 个文件上限"})
                    return files, skipped
    return files, skipped


def _infer_chip(detections, files):
    text = " ".join(str(item).lower() for item in detections) + " " + " ".join(path.name.lower() for path in files)
    if "esp32" in text or "espressif32" in text:
        return "esp32-wroom-32"
    if "rp2040" in text or "pico" in text:
        return "rp2040"
    if "stm32f103" in text or any(path.suffix.lower() == ".ioc" for path in files):
        return "stm32f103c8t6"
    return None


def _first_matching_value(path, key):
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        return None
    return None


def scan_project(project_path):
    root = Path(project_path).expanduser().resolve()
    if not root.exists():
        raise ProjectScanError(f"项目目录不存在: {root}")
    if not root.is_dir():
        raise ProjectScanError(f"扫描目标必须是目录: {root}")

    files, warnings = _discover_files(root)
    detections = []
    if (root / "platformio.ini") in files:
        detections.append(_detect_platformio(root / "platformio.ini"))
    if any(path.suffix.lower() == ".ino" for path in files):
        detections.append({"type": "arduino", "source": str(root)})
    for path in files:
        if path.name == "sdkconfig":
            detections.append({"type": "esp-idf", "source": str(path), "target": _first_matching_value(path, "CONFIG_IDF_TARGET") or ""})
        if path.name == "CMakeLists.txt":
            try:
                if "idf_component_register" in path.read_text(encoding="utf-8", errors="ignore"):
                    detections.append({"type": "esp-idf", "source": str(path)})
            except OSError:
                warnings.append({"code": "file_unreadable", "source": str(path), "message": "文件无法读取，已跳过"})
    for path in files:
        if path.suffix.lower() == ".ioc":
            detections.append({"type": "stm32cubemx", "source": str(path), "mcu": _first_matching_value(path, "Mcu.CPN") or _first_matching_value(path, "Mcu.Name") or ""})
        if path.suffix.lower() in {".kicad_sch", ".net"} or "kicad" in path.name.lower():
            detections.append({"type": "kicad", "source": str(path)})

    chip_hint = _infer_chip(detections, files)
    uses = []
    for path in files:
        suffix = path.suffix.lower()
        if suffix in {".h", ".hpp", ".c", ".cc", ".cpp", ".ino"}:
            parsed, parse_warnings = _parse_code(path, chip_hint)
            uses.extend(parsed); warnings.extend(parse_warnings)
        elif suffix == ".ioc":
            uses.extend(_parse_ioc(path))
        elif suffix == ".net":
            uses.extend(_parse_kicad_net(path))
        elif suffix == ".txt" and "kicad" in path.name.lower():
            uses.extend(_parse_kicad_text(path))

    unique = {}
    for use in uses:
        key = (use["symbol"], use["pin"], use["source"], use["line"], use["kind"])
        unique[key] = use
    uses = sorted(unique.values(), key=lambda item: (item["source"], item["line"] or 0, item["symbol"]))
    return {
        "root": str(root), "read_only": True, "files_scanned": len(files),
        "project_types": sorted({item["type"] for item in detections}),
        "detections": detections, "suggested_chip_id": chip_hint,
        "pin_uses": uses, "warnings": warnings,
        "summary": {
            "pin_use_count": len(uses),
            "code_count": sum(item["kind"] == "code" for item in uses),
            "schematic_count": sum(item["kind"] in {"ioc", "kicad"} for item in uses),
        },
    }


def compare_scan(scan, chip, allocation, signal_mapping=None):
    risks = []
    valid_pins = {pin["name"] for pin in chip["pins"]}
    by_symbol = defaultdict(list)
    by_pin = defaultdict(list)
    signal_mapping = { _normal_symbol(key): _normal_symbol(value) for key, value in (signal_mapping or {}).items() }
    for original in scan["pin_uses"]:
        use = dict(original)
        use["symbol"] = signal_mapping.get(use["symbol"], use["symbol"])
        by_symbol[use["symbol"]].append(use)
        by_pin[use["pin"]].append(use)
        if use["pin"] not in valid_pins:
            risks.append(_scan_risk("警告", "scan_unknown_pin", f"扫描到的 {use['pin']} 不在所选 {chip['name']} 引脚库中。", "确认主控选择和代码中的引脚命名。", use))

    for symbol, uses in by_symbol.items():
        pins = {use["pin"] for use in uses}
        if len(pins) > 1:
            risks.append(_scan_risk("错误", "scan_symbol_conflict", f"{symbol} 在项目中对应多个引脚：{', '.join(sorted(pins))}。", "统一代码、CubeMX 和原理图中的引脚定义。", uses[0], related=uses))
    for pin, uses in by_pin.items():
        symbols = {use["symbol"] for use in uses}
        if len(symbols) > 1:
            risks.append(_scan_risk("警告", "scan_pin_reused", f"{pin} 在扫描结果中被多个名称引用：{', '.join(sorted(symbols))}。", "确认这些名称是否表示同一信号；否则重新分配引脚。", uses[0], related=uses, confidence="medium"))

    doctor = {}
    for item in allocation:
        if item["chip_pin"] == "未分配":
            continue
        symbol = _normal_symbol(f"{item['module_id']}_{item['module_pin']}")
        doctor[symbol] = item
        if symbol in by_symbol:
            scanned_pins = {use["pin"] for use in by_symbol[symbol]}
            if item["chip_pin"] not in scanned_pins:
                use = by_symbol[symbol][0]
                snippet = f"#define {symbol} {item['chip_pin']}"
                risks.append(_scan_risk("警告", "doctor_scan_mismatch", f"医生建议 {symbol} 使用 {item['chip_pin']}，项目当前使用 {', '.join(sorted(scanned_pins))}。", f"如采用医生方案，可更新为：{snippet}", use, related=by_symbol[symbol], fix_snippet=snippet))

    matched = len(set(doctor) & set(by_symbol))
    return {
        "risks": risks, "matched_symbols": matched,
        "doctor_symbols": len(doctor), "scanned_symbols": len(by_symbol),
        "unmatched_scan_symbols": sorted(set(by_symbol) - set(doctor)),
        "unmatched_doctor_symbols": sorted(set(doctor) - set(by_symbol)),
        "match_rate": round(matched / max(1, len(doctor)) * 100, 1),
        "signal_aliases_applied": SIGNAL_ALIASES,
        "user_signal_mapping": signal_mapping,
    }


def _scan_risk(level, code, message, suggestion, source, related=None, confidence="high", fix_snippet=None):
    weight = {"错误": 25, "警告": 10, "提示": 2}[level] * {"high": 1.0, "medium": 0.75, "low": 0.5}[confidence]
    item = {"source": source.get("source"), "line": source.get("line"), "symbol": source.get("symbol"), "snippet": source.get("snippet")}
    if related:
        item["related"] = [{"source": use.get("source"), "line": use.get("line"), "pin": use.get("pin"), "kind": use.get("kind")} for use in related]
    if fix_snippet:
        item["fix_snippet"] = fix_snippet
    return {"level": level, "code": code, "message": message, "suggestion": suggestion, "item": item, "pin": source.get("pin"), "confidence": confidence, "weight": round(weight, 2)}
