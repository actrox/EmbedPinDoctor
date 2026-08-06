from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.allocator import allocate_project
from core.loader import load_chip, load_modules
from integrations.project_scanner import ProjectScanError, compare_scan, scan_project


def _digest(root):
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    fixture = ROOT / "tests/fixtures/p1_scan_project"
    before = _digest(fixture)
    scan = scan_project(fixture)
    after = _digest(fixture)
    assert before == after, "扫描器不得修改项目文件"
    assert scan["read_only"] is True
    assert scan["suggested_chip_id"] == "esp32-wroom-32", scan
    assert {"platformio", "stm32cubemx", "kicad"}.issubset(set(scan["project_types"])), scan["project_types"]
    assert scan["files_scanned"] >= 5
    assert scan["summary"]["pin_use_count"] >= 7
    scl_uses = [item for item in scan["pin_uses"] if item["symbol"] == "OLED_I2C_SCL"]
    assert {item["pin"] for item in scl_uses} == {"GPIO18", "GPIO19"}
    assert all(item["source"] and item["line"] for item in scl_uses)

    chip = load_chip(ROOT / "data/chips/esp32-wroom-32.json")
    modules = load_modules(ROOT / "data/modules", ["oled_i2c", "sd_card"])
    allocation = allocate_project(chip, modules)
    comparison = compare_scan(scan, chip, allocation)
    codes = {risk["code"] for risk in comparison["risks"]}
    assert "scan_symbol_conflict" in codes
    assert "scan_unknown_pin" in codes  # PA5 came from a conflicting CubeMX artifact.
    assert any(risk["item"].get("source") for risk in comparison["risks"])
    assert any(risk["item"].get("fix_snippet") for risk in comparison["risks"] if risk["code"] == "doctor_scan_mismatch")

    try:
        scan_project(fixture / "missing")
        raise AssertionError("不存在的目录未被拒绝")
    except ProjectScanError:
        pass
    print("P1 project scan test passed")
    print(f"types={','.join(scan['project_types'])} pins={scan['summary']['pin_use_count']} risks={','.join(sorted(codes))}")


if __name__ == "__main__":
    main()
