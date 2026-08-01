import json
import shutil
from pathlib import Path


def import_rule_pack(package_dir, rule_dir):
    package_dir = Path(package_dir); rule_dir = Path(rule_dir); rule_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    imported = []
    for path in sorted((package_dir / "rules").glob("*.json")):
        target = rule_dir / path.name
        shutil.copyfile(path, target)
        imported.append(path.stem)
    return {"package": manifest, "rules": imported}


def list_rule_packs(rule_dir):
    rule_dir = Path(rule_dir)
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(rule_dir.glob("*.json"))] if rule_dir.exists() else []
