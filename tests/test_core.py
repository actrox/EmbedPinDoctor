import copy
import json
import os
import unittest

from core.allocator import allocate_project, allocation_score, allocate_alternatives
from core.checker import check_project

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_json(*parts):
    with open(os.path.join(PROJECT_ROOT, *parts), encoding="utf-8") as f:
        return json.load(f)


def _load_fixtures():
    chip = _load_json("data", "chips", "stm32f103c8t6.json")
    oled = _load_json("data", "modules", "oled_i2c.json")
    button = _load_json("data", "modules", "button.json")
    buzzer = _load_json("data", "modules", "buzzer.json")
    return chip, oled, button, buzzer


def _make_item(module_id, module_name, module_pin, chip_pin, function,
               direction="bidirectional", score=100):
    return {
        "module_id": module_id,
        "module_name": module_name,
        "module_pin": module_pin,
        "chip_pin": chip_pin,
        "function": function,
        "direction": direction,
        "score": score,
        "note": "",
        "locked": False,
        "kept_existing": False,
        "reasons": [],
    }


class TestAllocator(unittest.TestCase):
    def test_basic_allocation(self):
        chip, oled, button, buzzer = _load_fixtures()
        allocation = allocate_project(chip, [oled, button, buzzer])
        self.assertEqual(len(allocation), 4)
        for item in allocation:
            self.assertNotEqual(item["chip_pin"], "未分配")

    def test_locked_pin(self):
        chip, oled, button, buzzer = _load_fixtures()
        locked = {"oled_i2c:SCL": "PB6"}
        allocation = allocate_project(chip, [oled, button, buzzer], locked_pins=locked)
        scl = next(
            item for item in allocation
            if item["module_id"] == "oled_i2c" and item["module_pin"] == "SCL"
        )
        self.assertEqual(scl["chip_pin"], "PB6")
        self.assertTrue(scl["locked"])

    def test_min_change_strategy(self):
        chip, oled, button, buzzer = _load_fixtures()
        modules = [oled, button, buzzer]
        recommended = allocate_project(chip, modules, strategy="recommended")
        kept_recommended = sum(1 for item in recommended if item.get("kept_existing"))
        min_change = allocate_project(
            chip, modules, preferred_allocation=recommended, strategy="min_change"
        )
        kept_min_change = sum(1 for item in min_change if item.get("kept_existing"))
        self.assertGreater(kept_min_change, kept_recommended)

    def test_alternatives(self):
        chip, oled, button, buzzer = _load_fixtures()
        plans = allocate_alternatives(chip, [oled, button, buzzer], count=3)
        self.assertGreater(len(plans), 1)
        signatures = set()
        for plan in plans:
            sig = tuple(
                (item["module_id"], item["module_pin"], item["chip_pin"])
                for item in plan["allocation"]
            )
            signatures.add(sig)
        self.assertGreater(len(signatures), 1)

    def test_allocation_score(self):
        chip, oled, button, buzzer = _load_fixtures()
        allocation = allocate_project(chip, [oled, button, buzzer])
        score = allocation_score(allocation)
        self.assertIsInstance(score, (int, float))
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 130)

    def test_deterministic(self):
        chip, oled, button, buzzer = _load_fixtures()
        modules = [oled, button, buzzer]
        first = allocate_project(chip, modules)
        second = allocate_project(chip, modules)
        self.assertEqual(first, second)


class TestChecker(unittest.TestCase):
    def test_no_risk_for_clean_project(self):
        chip, oled, button, buzzer = _load_fixtures()
        modules = [oled, button, buzzer]
        allocation = allocate_project(chip, modules)
        risks = check_project(chip, modules, allocation)
        error_risks = [r for r in risks if r["level"] == "错误"]
        self.assertEqual(error_risks, [])

    def test_pin_duplicate(self):
        chip, oled, button, buzzer = _load_fixtures()
        allocation = [
            _make_item("button", "普通按键", "KEY", "PA0", "GPIO", "input"),
            _make_item("buzzer", "蜂鸣器", "SIG", "PA0", "PWM", "output"),
        ]
        risks = check_project(chip, [button, buzzer], allocation)
        codes = [r["code"] for r in risks]
        self.assertIn("pin_duplicate", codes)

    def test_shared_bus_allowed(self):
        chip, oled, button, buzzer = _load_fixtures()
        allocation = [
            _make_item("oled_i2c", "OLED I2C 屏幕", "SCL", "PB6", "I2C1_SCL", "output"),
            _make_item("oled_i2c2", "OLED I2C 屏幕 2", "SCL", "PB6", "I2C1_SCL", "output"),
        ]
        risks = check_project(chip, [oled], allocation)
        codes = [r["code"] for r in risks]
        self.assertNotIn("pin_duplicate", codes)

    def test_data_unverified(self):
        chip, oled, button, buzzer = _load_fixtures()
        modules = [oled, button, buzzer]
        allocation = allocate_project(chip, modules)
        risks = check_project(chip, modules, allocation)
        codes = [r["code"] for r in risks]
        self.assertIn("data_unverified", codes)
        unverified = next(r for r in risks if r["code"] == "data_unverified")
        self.assertEqual(unverified["level"], "提示")

    def test_i2c_address_conflict(self):
        chip, oled, button, buzzer = _load_fixtures()
        oled2 = copy.deepcopy(oled)
        oled2["id"] = "oled_i2c2"
        oled2["name"] = "OLED I2C 屏幕 2"
        risks = check_project(chip, [oled, oled2], [])
        codes = [r["code"] for r in risks]
        self.assertIn("i2c_address_conflict", codes)

    def test_dynamic_shared_functions(self):
        chip, oled, button, buzzer = _load_fixtures()
        allocation = [
            _make_item("sensor1", "传感器1", "SCL", "PB10", "I2C2_SCL", "output"),
            _make_item("sensor2", "传感器2", "SCL", "PB10", "I2C2_SCL", "output"),
        ]
        risks = check_project(chip, [], allocation)
        codes = [r["code"] for r in risks]
        self.assertNotIn("pin_duplicate", codes)

    def test_pwm_timer_frequency_conflict(self):
        chip, oled, button, buzzer = _load_fixtures()
        pwm1 = {
            "id": "pwm1",
            "name": "PWM 模块1",
            "voltage": "3.3V",
            "logic_voltage": 3.3,
            "requirements": [
                {
                    "module_pin": "OUT",
                    "function": "PWM",
                    "direction": "output",
                    "pwm_frequency_hz": 1000,
                }
            ],
        }
        pwm2 = {
            "id": "pwm2",
            "name": "PWM 模块2",
            "voltage": "3.3V",
            "logic_voltage": 3.3,
            "requirements": [
                {
                    "module_pin": "OUT",
                    "function": "PWM",
                    "direction": "output",
                    "pwm_frequency_hz": 2000,
                }
            ],
        }
        allocation = [
            _make_item("pwm1", "PWM 模块1", "OUT", "PA0", "PWM", "output"),
            _make_item("pwm2", "PWM 模块2", "OUT", "PA1", "PWM", "output"),
        ]
        risks = check_project(chip, [pwm1, pwm2], allocation)
        codes = [r["code"] for r in risks]
        self.assertIn("pwm_timer_frequency_conflict", codes)


if __name__ == "__main__":
    unittest.main()
