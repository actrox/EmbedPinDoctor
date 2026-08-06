from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.allocator import allocate_project
from core.checker import check_project
from core.loader import DataLoadError, load_chip
from quality.data_audit import audit_data


def _chip(pins):
    return {
        "id": "test", "name": "Test MCU", "voltage": "3.3V",
        "io_voltage": 3.3, "absolute_max_input_voltage": 3.6,
        "default_max_output_current_ma": 8, "supports_open_drain": True,
        "verified": True, "pins": pins,
    }


def main():
    # Versioned schema rejects incomplete data instead of silently filling it.
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "bad.json"
        path.write_text(json.dumps({"id": "bad", "name": "Bad", "voltage": "3.3V", "pins": []}), encoding="utf-8")
        try:
            load_chip(path)
            raise AssertionError("不完整芯片数据未被拒绝")
        except DataLoadError:
            pass

    audit = audit_data(ROOT / "data")
    assert audit["ok"], audit["errors"]
    assert audit["chip_count"] == 3 and audit["module_count"] >= 12
    assert audit["verified_chip_count"] == 0, "不得把机器检查伪装成人工签字"

    # This layout requires backtracking: F3 reserves P3, F1 must move from P1
    # to P2 so F2 can use P1.
    search_chip = _chip([
        {"name": "P1", "functions": ["F1", "F2"], "tags": []},
        {"name": "P2", "functions": ["F1"], "tags": []},
        {"name": "P3", "functions": ["F2", "F3"], "tags": []},
    ])
    search_modules = [
        {"id": "a", "name": "A", "requirements": [{"module_pin": "A", "function": "F1", "direction": "output"}]},
        {"id": "b", "name": "B", "requirements": [{"module_pin": "B", "function": "F2", "direction": "output"}]},
        {"id": "c", "name": "C", "requirements": [{"module_pin": "C", "function": "F3", "direction": "output"}]},
    ]
    first = allocate_project(search_chip, search_modules)
    second = allocate_project(search_chip, search_modules)
    assert first == second, "相同输入必须产生确定性结果"
    assert all(item["chip_pin"] != "未分配" for item in first), first
    assert {item["module_id"]: item["chip_pin"] for item in first} == {"a": "P2", "b": "P1", "c": "P3"}

    input_only_chip = _chip([
        {"name": "IN", "functions": ["GPIO"], "tags": ["input_only"]},
        {"name": "OUT", "functions": ["GPIO"], "tags": []},
    ])
    output_module = {"id": "led", "name": "LED", "logic_voltage": 3.3, "requirements": [{"module_pin": "DIN", "function": "GPIO", "direction": "output"}]}
    result = allocate_project(input_only_chip, [output_module])
    assert result[0]["chip_pin"] == "OUT", result

    electrical_modules = [
        {"id": "sensor", "name": "5V Sensor", "voltage": "5V", "logic_voltage": 5.0, "requirements": [{"module_pin": "OUT", "function": "GPIO", "direction": "input"}]},
        {"id": "load", "name": "Heavy Load", "voltage": "3.3V", "logic_voltage": 3.3, "requirements": [{"module_pin": "IN", "function": "GPIO", "direction": "output", "drive_current_ma": 20}]},
    ]
    electrical_allocation = [
        {"module_id": "sensor", "module_name": "5V Sensor", "module_pin": "OUT", "chip_pin": "OUT", "function": "GPIO", "direction": "input"},
        {"module_id": "load", "module_name": "Heavy Load", "module_pin": "IN", "chip_pin": "IN", "function": "GPIO", "direction": "output"},
    ]
    codes = {risk["code"] for risk in check_project(input_only_chip, electrical_modules, electrical_allocation)}
    assert {"input_overvoltage", "drive_current_exceeded", "output_on_input_only"}.issubset(codes), codes
    print("P0 trust test passed")
    print(f"audit_chips={audit['chip_count']} audit_modules={audit['module_count']} risks={','.join(sorted(codes))}")


if __name__ == "__main__":
    main()
