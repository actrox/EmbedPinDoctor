from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.loader import load_chip, load_modules
from core.allocator import allocate_project
from core.checker import check_project
from integrations.risk_explainer import explain_risks
from collaboration.audit_log import append_event, read_events
from collaboration.locks import acquire_lock, release_lock
from collaboration.review import create_review, update_review
from quality.design_review import build_design_review, render_design_review_markdown
from quality.rule_pack import import_rule_pack, list_rule_packs
from release.packager import create_release_package
from backup.snapshot import create_backup, restore_backup


def main():
    chip = load_chip(PROJECT_ROOT / "data/chips/stm32f103c8t6.json")
    modules = load_modules(PROJECT_ROOT / "data/modules", ["oled_i2c", "button"])
    allocation = allocate_project(chip, modules)
    risks = explain_risks(check_project(chip, modules, allocation))
    review = build_design_review(chip, modules, allocation, risks)
    assert "score" in review and "电气兼容" in review["categories"]
    assert "硬件设计审查报告" in render_design_review_markdown(review)
    event = append_event(PROJECT_ROOT / "projects", "p4_demo", "tester", "save", {"items": len(allocation)})
    assert read_events(PROJECT_ROOT / "projects", "p4_demo")
    assert acquire_lock(PROJECT_ROOT / "projects", "p4_demo", "tester")["locked"]
    assert release_lock(PROJECT_ROOT / "projects", "p4_demo", "tester")["released"]
    review_doc = create_review(PROJECT_ROOT / "projects", "p4_demo", "tester", "P4 审批", [{"field": "pin"}])
    assert update_review(PROJECT_ROOT / "projects", review_doc["id"], "lead", "approved", "通过")["status"] == "approved"
    imported = import_rule_pack(PROJECT_ROOT / "rule_packs/demo_pack", PROJECT_ROOT / "rule_packs/imported")
    assert imported["rules"] and list_rule_packs(PROJECT_ROOT / "rule_packs/imported")
    release = create_release_package(PROJECT_ROOT, PROJECT_ROOT / "output/releases", "EmbedPinDoctorP4")
    assert (Path(release["path"]) / "release_manifest.json").exists()
    backup = create_backup(PROJECT_ROOT, PROJECT_ROOT / "output/backups")
    assert Path(backup["path"]).exists()
    assert restore_backup(backup["path"], PROJECT_ROOT)["restored"]
    print("P4 platform test passed")
    print(f"score={review['score']} release={release['path']} backup={backup['path']}")


if __name__ == "__main__":
    main()
