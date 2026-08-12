import tempfile
import unittest
from pathlib import Path

from integrations.project_scanner import scan_project, compare_scan


class TestProjectScanner(unittest.TestCase):
    def test_platformio_esp32_and_alias_pin_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "platformio.ini").write_text(
                "[env:esp32]\nplatform=espressif32\nboard=esp32dev\nframework=arduino\n",
                encoding="utf-8",
            )
            (root / "main.cpp").write_text(
                "#define DISPLAY_SCL GPIO22\n#define DISPLAY_SDA GPIO21\n",
                encoding="utf-8",
            )
            scan = scan_project(root)
            self.assertEqual(scan["suggested_chip_id"], "esp32-wroom-32")
            self.assertIn("platformio", scan["project_types"])
            self.assertEqual(
                {item["symbol"] for item in scan["pin_uses"]},
                {"OLED_I2C_SCL", "OLED_I2C_SDA"},
            )

    def test_stm32_ioc_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "board.ioc").write_text(
                "Mcu.CPN=STM32F103C8T6\nPB6.Signal=I2C1_SCL\nPB7.GPIO_Label=OLED_SDA\n",
                encoding="utf-8",
            )
            scan = scan_project(root)
            self.assertEqual(scan["suggested_chip_id"], "stm32f103c8t6")
            self.assertIn("stm32cubemx", scan["project_types"])
            self.assertEqual(scan["summary"]["schematic_count"], 2)

    def test_compare_reports_match_rate(self):
        scan = {"pin_uses": [{"symbol": "OLED_I2C_SCL", "pin": "PB6", "source": "x.h", "line": 1, "kind": "code", "snippet": "#define DISPLAY_SCL PB6"}]}
        chip = {"name": "Test", "pins": [{"name": "PB6"}]}
        allocation = [{"module_id": "oled_i2c", "module_pin": "SCL", "chip_pin": "PB6"}]
        comparison = compare_scan(scan, chip, allocation)
        self.assertEqual(comparison["match_rate"], 100.0)

    def test_user_signal_mapping(self):
        scan = {"pin_uses": [{"symbol": "MY_CLOCK", "pin": "PB6", "source": "x.h", "line": 1, "kind": "code", "snippet": "#define MY_CLOCK PB6"}]}
        chip = {"name": "Test", "pins": [{"name": "PB6"}]}
        allocation = [{"module_id": "oled_i2c", "module_pin": "SCL", "chip_pin": "PB6"}]
        comparison = compare_scan(scan, chip, allocation, {"MY_CLOCK": "OLED_I2C_SCL"})
        self.assertEqual(comparison["match_rate"], 100.0)
        self.assertEqual(comparison["user_signal_mapping"]["MY_CLOCK"], "OLED_I2C_SCL")


if __name__ == "__main__":
    unittest.main()
