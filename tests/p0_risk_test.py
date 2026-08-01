from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.loader import load_chip
from core.checker import check_project


def _codes(risks):
    return {risk["code"] for risk in risks}


def main():
    chip = load_chip(PROJECT_ROOT / "data/chips/stm32f103c8t6.json")

    modules = [
        {"id": "bad_5v", "name": "5V 传感器", "voltage": "5V", "requirements": []},
        {"id": "i2c_sensor", "name": "I2C 传感器", "voltage": "3.3V", "needs_pullup": True, "requirements": []},
    ]

    allocation = [
        {"module_id": "a", "module_name": "模块 A", "module_pin": "SIG", "chip_pin": "PA0", "function": "GPIO", "note": "占用测试"},
        {"module_id": "b", "module_name": "模块 B", "module_pin": "SIG", "chip_pin": "PA0", "function": "PWM", "note": "重复占用测试"},
        {"module_id": "c", "module_name": "模块 C", "module_pin": "DBG", "chip_pin": "PA13", "function": "GPIO", "note": "调试脚测试"},
        {"module_id": "d", "module_name": "模块 D", "module_pin": "BOOT", "chip_pin": "PB2", "function": "GPIO", "note": "启动脚测试"},
        {"module_id": "e", "module_name": "模块 E", "module_pin": "MISS", "chip_pin": "未分配", "function": "ADC", "note": "未分配测试"},
    ]

    risks = check_project(chip, modules, allocation)
    codes = _codes(risks)
    expected = {"pin_duplicate", "debug_pin", "boot_pin", "unassigned", "voltage_mismatch", "pullup_required"}
    missing = expected - codes
    assert not missing, f"缺少风险检查: {sorted(missing)}"
    print("P0 risk test passed")
    print("risk_codes=" + ",".join(sorted(codes)))


if __name__ == "__main__":
    main()
