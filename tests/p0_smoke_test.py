from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.loader import load_chip, load_modules
from core.allocator import allocate_project
from core.checker import check_project
from export.markdown import render_markdown


def main():
    chip = load_chip(PROJECT_ROOT / "data/chips/stm32f103c8t6.json")
    modules = load_modules(PROJECT_ROOT / "data/modules", ["oled_i2c", "mpu6050", "button", "buzzer", "sd_card"])
    allocation = allocate_project(chip, modules)
    risks = check_project(chip, modules, allocation)
    markdown = render_markdown(chip, modules, allocation, risks)

    assert chip["id"] == "stm32f103c8t6"
    assert len(modules) == 5
    assert len(allocation) >= 10
    assert "## 接线表" in markdown
    assert "## 风险报告" in markdown
    assert any(risk["level"] in {"警告", "提示"} for risk in risks)
    print("P0 smoke test passed")
    print(f"allocation={len(allocation)} risks={len(risks)}")


if __name__ == "__main__":
    main()
