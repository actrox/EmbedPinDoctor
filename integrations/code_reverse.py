import re
from pathlib import Path

DEFINE_PATTERN = re.compile(r"#define\s+([A-Za-z0-9_]+)\s+(GPIO_PIN_\d+|GPIO_NUM_\d+|P[A-Z]\d+|GPIO\d+|GP\d+)")
PORT_PATTERN = re.compile(r"#define\s+([A-Za-z0-9_]+)_PORT\s+(GPIO[A-Z])")
PIN_PATTERN = re.compile(r"#define\s+([A-Za-z0-9_]+)_PIN\s+GPIO_PIN_(\d+)")


def reverse_pins_from_code(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    results = []
    ports = {m.group(1): m.group(2) for m in PORT_PATTERN.finditer(text)}
    for m in PIN_PATTERN.finditer(text):
        base = m.group(1)
        if base in ports:
            results.append({"symbol": base, "pin": ports[base].replace("GPIO", "P") + m.group(2), "source": str(path)})
    for m in DEFINE_PATTERN.finditer(text):
        symbol, value = m.group(1), m.group(2)
        if value.startswith("GPIO_NUM_"):
            value = "GPIO" + value.replace("GPIO_NUM_", "")
        results.append({"symbol": symbol, "pin": value, "source": str(path)})
    return results
