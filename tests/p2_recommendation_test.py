from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.allocator import allocate_alternatives, allocate_project
from core.checker import check_project


def _chip():
    return {
        "id": "solver", "name": "Solver MCU", "voltage": "3.3V", "verified": True,
        "absolute_max_input_voltage": 3.6, "default_max_output_current_ma": 8,
        "supports_open_drain": True,
        "pins": [
            {"name": "P1", "functions": ["GPIO", "PWM", "I2C1_SCL", "I2C1_SDA", "SPI1_SCK"], "tags": [], "timer": "TIM1"},
            {"name": "P2", "functions": ["GPIO", "PWM", "I2C1_SCL", "I2C1_SDA", "SPI1_SCK"], "tags": [], "timer": "TIM1"},
            {"name": "P3", "functions": ["GPIO", "PWM", "I2C1_SCL", "I2C1_SDA", "SPI1_SCK"], "tags": [], "timer": "TIM2"},
            {"name": "P4", "functions": ["GPIO", "PWM", "I2C1_SCL", "I2C1_SDA", "SPI1_SCK"], "tags": [], "timer": "TIM2"},
        ],
    }


def _gpio_module(module_id):
    return {"id": module_id, "name": module_id.upper(), "voltage": "3.3V", "logic_voltage": 3.3, "requirements": [{"module_pin": "SIG", "function": "GPIO", "direction": "output"}]}


def main():
    chip = _chip()
    modules = [_gpio_module("a"), _gpio_module("b")]
    primary = allocate_project(chip, modules)
    assert [item["chip_pin"] for item in primary] == ["P1", "P2"]
    assert all(item["reasons"] for item in primary)

    locked = allocate_project(chip, modules, {"a:SIG": "P3"})
    assert locked[0]["chip_pin"] == "P3" and locked[0]["locked"]
    invalid = allocate_project(chip, modules, {"a:SIG": "MISSING"})
    assert invalid[0]["chip_pin"] == "未分配" and invalid[0]["locked"]
    assert "locked_pin_conflict" in {risk["code"] for risk in check_project(chip, modules, invalid)}

    preferred = [{"module_id": "a", "module_pin": "SIG", "chip_pin": "P2"}, {"module_id": "b", "module_pin": "SIG", "chip_pin": "P1"}]
    stable = allocate_project(chip, modules, preferred_allocation=preferred, strategy="min_change")
    assert [item["chip_pin"] for item in stable] == ["P2", "P1"]
    assert all(item["kept_existing"] for item in stable)

    alternatives = allocate_alternatives(chip, modules, 3)
    assert len(alternatives) == 3, alternatives
    signatures = {tuple(item["chip_pin"] for item in plan["allocation"]) for plan in alternatives}
    assert len(signatures) == 3
    assert alternatives[1]["change_count"] > 0

    bus_modules = [
        {"id": "i2c_a", "name": "I2C A", "voltage": "3.3V", "logic_voltage": 3.3, "i2c_address": "0x3c", "requirements": [{"module_pin": "SCL", "function": "I2C1_SCL", "direction": "output"}]},
        {"id": "i2c_b", "name": "I2C B", "voltage": "3.3V", "logic_voltage": 3.3, "i2c_address": "0x3C", "requirements": [{"module_pin": "SDA", "function": "I2C1_SDA", "direction": "bidirectional"}]},
        {"id": "spi_a", "name": "SPI A", "voltage": "3.3V", "logic_voltage": 3.3, "spi_mode": 0, "spi_max_hz": 1000000, "requirements": [{"module_pin": "SCK", "function": "SPI1_SCK", "direction": "output"}]},
        {"id": "spi_b", "name": "SPI B", "voltage": "3.3V", "logic_voltage": 3.3, "spi_mode": 3, "spi_max_hz": 500000, "requirements": [{"module_pin": "SCK", "function": "SPI1_SCK", "direction": "output"}]},
        {"id": "uart", "name": "UART Flow", "voltage": "3.3V", "logic_voltage": 3.3, "uart_requires_flow_control": True, "requirements": [{"module_pin": "TX", "function": "GPIO", "direction": "input"}]},
        {"id": "pwm_a", "name": "PWM A", "voltage": "3.3V", "logic_voltage": 3.3, "requirements": [{"module_pin": "PWM", "function": "PWM", "direction": "output", "pwm_frequency_hz": 1000}]},
        {"id": "pwm_b", "name": "PWM B", "voltage": "3.3V", "logic_voltage": 3.3, "requirements": [{"module_pin": "PWM", "function": "PWM", "direction": "output", "pwm_frequency_hz": 2000}]},
    ]
    allocation = [
        {"module_id": "i2c_a", "module_name": "I2C A", "module_pin": "SCL", "chip_pin": "P1", "function": "I2C1_SCL", "direction": "output"},
        {"module_id": "i2c_b", "module_name": "I2C B", "module_pin": "SDA", "chip_pin": "P2", "function": "I2C1_SDA", "direction": "bidirectional"},
        {"module_id": "spi_a", "module_name": "SPI A", "module_pin": "SCK", "chip_pin": "P1", "function": "SPI1_SCK", "direction": "output"},
        {"module_id": "spi_b", "module_name": "SPI B", "module_pin": "SCK", "chip_pin": "P2", "function": "SPI1_SCK", "direction": "output"},
        {"module_id": "uart", "module_name": "UART Flow", "module_pin": "TX", "chip_pin": "P3", "function": "GPIO", "direction": "input"},
        {"module_id": "pwm_a", "module_name": "PWM A", "module_pin": "PWM", "chip_pin": "P1", "function": "PWM", "direction": "output"},
        {"module_id": "pwm_b", "module_name": "PWM B", "module_pin": "PWM", "chip_pin": "P2", "function": "PWM", "direction": "output"},
    ]
    codes = {risk["code"] for risk in check_project(chip, bus_modules, allocation)}
    expected = {"i2c_address_conflict", "spi_mode_mixed", "spi_frequency_limit", "uart_flow_control_missing", "pwm_timer_frequency_conflict"}
    assert expected.issubset(codes), codes
    print("P2 recommendation test passed")
    print(f"alternatives={len(alternatives)} risks={','.join(sorted(expected))}")


if __name__ == "__main__":
    main()
