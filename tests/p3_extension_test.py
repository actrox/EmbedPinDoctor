from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.loader import load_chip, load_modules
from core.allocator import allocate_project
from core.checker import check_project
from integrations.risk_explainer import explain_risks
from integrations.code_reverse import reverse_pins_from_code
from integrations.platformio import generate_platformio_project
from integrations.ioc_export import render_ioc_hint
from integrations.kicad_import import import_kicad_labels
from integrations.package_update import import_data_package
from versioning.compare import compare_allocations
from plugins.registry import discover_plugins


def main():
    chip = load_chip(PROJECT_ROOT / "data/chips/stm32f103c8t6.json")
    modules = load_modules(PROJECT_ROOT / "data/modules", ["oled_i2c", "button"])
    allocation = allocate_project(chip, modules)
    risks = explain_risks(check_project(chip, modules, allocation))
    assert all("explanation" in r for r in risks)
    code_file = PROJECT_ROOT / "output/reverse_sample.h"
    code_file.write_text("#define LED_PORT GPIOB\n#define LED_PIN GPIO_PIN_5\n#define SENSOR_GPIO GPIO_NUM_21\n", encoding="utf-8")
    assert len(reverse_pins_from_code(code_file)) >= 2
    result = generate_platformio_project(PROJECT_ROOT / "output/p3_platformio_test", chip, allocation)
    assert (Path(result["path"]) / "platformio.ini").exists()
    assert "Signal" in render_ioc_hint(chip, allocation)
    kicad_file = PROJECT_ROOT / "output/kicad_labels_sample.txt"
    kicad_file.write_text("OLED_SCL PB6 I2C1_SCL\n", encoding="utf-8")
    assert import_kicad_labels(kicad_file)[0]["label"] == "OLED_SCL"
    changed = compare_allocations(allocation, [{**allocation[0], "chip_pin": "PB5"}] + allocation[1:])
    assert changed
    update = import_data_package(PROJECT_ROOT / "packages/demo_update_pack", PROJECT_ROOT / "data")
    assert "relay_module" in update["imported"]["modules"]
    assert discover_plugins(PROJECT_ROOT / "plugins")
    print("P3 extension test passed")
    print(f"risks={len(risks)} changes={len(changed)} platformio={result['path']}")


if __name__ == "__main__":
    main()
