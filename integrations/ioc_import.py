"""
STM32CubeMX .ioc 文件导入模块。

解析 STM32CubeMX 生成的 .ioc 配置文件（Windows INI 格式），
反推芯片引脚分配情况，生成可被 EmbedPinDoctor 直接消费的数据结构。
"""

import configparser
import re
from pathlib import Path


_PIN_SIGNAL_RE = re.compile(r"^P([A-Z])(\d+)\.Signal$")
_PIN_LABEL_RE = re.compile(r"^P([A-Z])(\d+)\.LABEL$")
_PIN_GPIO_RE = re.compile(r"^P([A-Z])(\d+)\.GPIOParameters$")
_PIN_MODE_RE = re.compile(r"^P([A-Z])(\d+)\.Mode$")


def _parse_pin_key(key):
    """
    解析形如 "PA9.Signal" 的键，返回 (引脚名, 属性名) 或 None。

    例: "PA9.Signal" -> ("PA9", "Signal")
        "PB10.LABEL" -> ("PB10", "LABEL")
    """
    dot = key.rfind(".")
    if dot < 0:
        return None
    pin_part = key[:dot]
    attr_part = key[dot + 1:]
    if re.match(r"^P[A-Z]\d+$", pin_part):
        return pin_part, attr_part
    return None


def _infer_mode_from_signal(signal):
    """
    根据外设信号名粗略推断工作模式。
    返回模式字符串（Analog/Asynchronous/SPI/I2C/TIM/GPIO 等）。
    """
    s = (signal or "").upper()
    if not s or s == "GPIO":
        return "GPIO"
    if s.startswith("ADC") or s.startswith("DAC"):
        return "Analog"
    if "USART" in s or "UART" in s or "LPUART" in s:
        if "TX" in s or "RX" in s or "CK" in s:
            return "Asynchronous"
        return "USART"
    if "SPI" in s or "I2S" in s:
        return "SPI"
    if "I2C" in s:
        return "I2C"
    if "CAN" in s:
        return "CAN"
    if "USB" in s:
        return "USB"
    if "SDIO" in s or "SDMMC" in s:
        return "SDMMC"
    if "ETH" in s:
        return "Ethernet"
    if "TIM" in s or "PWM" in s or "LPTIM" in s:
        return "TIM"
    if "SWD" in s or "JTAG" in s or "SWO" in s:
        return "Debug"
    if "RTC" in s:
        return "RTC"
    return "Alternate"


def _extract_module_pin(function, signal):
    """
    根据 function 或 signal 推断模块端引脚名（TX/RX/SCL/SDA/MOSI 等）。
    """
    s = (function or signal or "").upper()
    for suffix in ("TX", "RX", "SCL", "SDA", "SCK", "MOSI", "MISO",
                   "NSS", "CS", "CK", "CTS", "RTS", "DTR", "DSR",
                   "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7",
                   "IN0", "IN1", "IN2", "IN3", "IN4", "IN5", "IN6", "IN7",
                   "IN8", "IN9", "IN10", "IN11", "IN12", "IN13", "IN14", "IN15",
                   "CH1", "CH2", "CH3", "CH4", "SWDIO", "SWCLK", "SWO",
                   "WDATA", "RDATA", "CMD", "CLK", "IO0", "IO1", "IO2", "IO3"):
        if s.endswith("_" + suffix) or s == suffix:
            return suffix
    if s.startswith("GPIO"):
        return "GPIO"
    if s.startswith("ADC") or s.startswith("DAC"):
        return "AIN"
    return "SIG"


def import_ioc(ioc_path):
    """
    解析 STM32CubeMX 的 .ioc 文件，反推引脚分配。

    参数:
        ioc_path: .ioc 文件路径（str 或 Path）

    返回:
        dict: {
            "chip_name": "STM32F103C8Tx",
            "pin_signals": {
                "PA0": {"signal": "ADC1_IN0", "label": "ADC_VOLTAGE", "mode": "Analog"},
                ...
            },
            "suggested_allocation": [
                {"chip_pin": "PA9", "function": "USART1_TX", "module_pin": "TX",
                 "module_id": "imported", "module_name": "从 IOC 导入"},
                ...
            ],
            "raw_sections": {...}
        }
    """
    path = Path(ioc_path)

    config = configparser.ConfigParser(strict=False)
    config.optionxform = str
    raw_content = None
    for enc in ("utf-8", "utf-8-sig", "latin-1", "gbk"):
        try:
            raw_content = path.read_text(encoding=enc)
            config.read_string(raw_content)
            break
        except (UnicodeDecodeError, configparser.Error):
            continue
    else:
        raw_content = path.read_text(encoding="utf-8", errors="replace")
        try:
            config.read_string(raw_content)
        except configparser.Error:
            pass

    raw_sections = {}
    for section in config.sections():
        raw_sections[section] = dict(config.items(section))

    def _find_section(*names):
        sections_lower = {s.lower(): s for s in config.sections()}
        for name in names:
            if name.lower() in sections_lower:
                return dict(config.items(sections_lower[name.lower()]))
        return {}

    chip_name = ""
    mcu = _find_section("MCU", "Mcu")
    if mcu:
        keys = list(mcu.keys())
        keys_lower = {k.lower(): k for k in keys}

        def _get(*names):
            for n in names:
                if n.lower() in keys_lower:
                    return mcu.get(keys_lower[n.lower()], "")
            return ""

        chip_name = (
            _get("ProductId")
            or _get("McuName")
            or _get("Mcu")
            or _get("DeviceName")
            or ""
        )
    if not chip_name:
        stem = path.stem
        chip_name = stem if stem else "Unknown"

    pin_signals = {}
    all_items = []
    for section in config.sections():
        for key, value in config.items(section):
            all_items.append((section, key, value))

    for section, key, value in all_items:
        parsed = _parse_pin_key(key)
        if parsed is None:
            continue
        pin_name, attr = parsed

        if pin_name not in pin_signals:
            pin_signals[pin_name] = {"signal": "", "label": "", "mode": ""}

        attr_upper = attr.upper()
        if attr_upper == "SIGNAL":
            pin_signals[pin_name]["signal"] = value.strip()
        elif attr_upper == "LABEL":
            pin_signals[pin_name]["label"] = value.strip()
        elif attr_upper == "MODE":
            pin_signals[pin_name]["mode"] = value.strip()
        elif attr_upper == "GPIOPARAMETERS" and not pin_signals[pin_name]["signal"]:
            gpio_val = value.strip()
            if gpio_val:
                pin_signals[pin_name]["signal"] = "GPIO"

    for pin_name, info in pin_signals.items():
        if not info.get("mode"):
            info["mode"] = _infer_mode_from_signal(info.get("signal", ""))

    suggested_allocation = []
    for pin_name, info in sorted(pin_signals.items()):
        signal = (info.get("signal") or "").strip()
        label = (info.get("label") or "").strip()
        if not signal and not label:
            continue

        function = signal if signal else "GPIO"
        module_pin = _extract_module_pin(function, signal)

        mod_name = "从 IOC 导入"
        mod_id = "imported"
        if label:
            mod_name = label
            mod_id = f"ioc_{label.lower().replace(' ', '_')}"

        suggested_allocation.append({
            "chip_pin": pin_name,
            "function": function,
            "module_pin": module_pin,
            "module_id": mod_id,
            "module_name": mod_name,
        })

    return {
        "chip_name": chip_name,
        "pin_signals": pin_signals,
        "suggested_allocation": suggested_allocation,
        "raw_sections": raw_sections,
    }
