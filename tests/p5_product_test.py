from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.loader import load_chip, load_modules
from core.allocator import allocate_project
from core.checker import check_project
from integrations.risk_explainer import explain_risks
from export.markdown import render_markdown
from export.pins import render_pins_header
from export.templates import render_stm32_hal


def main():
    chip = load_chip(ROOT / "data/chips/stm32f103c8t6.json")
    modules = load_modules(ROOT / "data/modules", ["oled_i2c", "mpu6050", "button", "buzzer", "sd_card"])
    allocation = allocate_project(chip, modules)
    risks = explain_risks(check_project(chip, modules, allocation))
    markdown = render_markdown(chip, modules, allocation, risks, "stm32_real_case", "P5 真实案例")
    assert "STM32F103C8T6" in markdown
    assert "OLED I2C 屏幕" in markdown
    assert "风险报告" in markdown
    assert "#ifndef" in render_pins_header(chip, allocation)
    assert "GPIO_PORT" not in render_stm32_hal(chip, allocation)
    assert (ROOT / "start_embedpindoctor.py").exists()
    assert (ROOT / "docs/STM32真实案例.md").exists()
    assert (ROOT / "docs/芯片数据审核清单.md").exists()
    print("P5 product test passed")
    print(f"modules={len(modules)} allocation={len(allocation)} risks={len(risks)}")


if __name__ == "__main__":
    main()
