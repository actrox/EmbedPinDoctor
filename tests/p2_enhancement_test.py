from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.loader import load_chip, load_modules
from core.allocator import allocate_project
from core.checker import check_project
from export.templates import render_arduino, render_stm32_hal, render_esp_idf, render_kicad_labels


def main():
    chips = list((PROJECT_ROOT / "data/chips").glob("*.json"))
    modules = list((PROJECT_ROOT / "data/modules").glob("*.json"))
    assert len(chips) >= 3, "P2 需要至少 3 个芯片数据"
    assert len(modules) >= 10, "P2 需要至少 10 个模块数据"
    chip = load_chip(PROJECT_ROOT / "data/chips/esp32-wroom-32.json")
    selected = load_modules(PROJECT_ROOT / "data/modules", ["oled_i2c", "rotary_encoder", "motor_tb6612", "analog_sensor"])
    allocation = allocate_project(chip, selected)
    risks = check_project(chip, selected, allocation)
    assert all("score" in item for item in allocation), "分配结果应包含评分"
    assert all("suggestion" in risk for risk in risks), "风险项应包含建议"
    assert "#define" in render_arduino(chip, allocation)
    assert "GPIO" in render_esp_idf(chip, allocation)
    assert "KiCad" in render_kicad_labels(chip, allocation)
    render_stm32_hal(load_chip(PROJECT_ROOT / "data/chips/stm32f103c8t6.json"), allocation)
    print("P2 enhancement test passed")
    print(f"chips={len(chips)} modules={len(modules)} allocation={len(allocation)} risks={len(risks)}")


if __name__ == "__main__":
    main()
