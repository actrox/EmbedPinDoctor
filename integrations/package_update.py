import json
import shutil
from pathlib import Path


def import_data_package(package_dir, data_dir):
    package_dir = Path(package_dir)
    data_dir = Path(data_dir)
    manifest = package_dir / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(f"缺少数据包清单: {manifest}")
    info = json.loads(manifest.read_text(encoding="utf-8"))
    imported = {"chips": [], "modules": []}
    for kind in ["chips", "modules"]:
        source_dir = package_dir / kind
        target_dir = data_dir / kind
        target_dir.mkdir(parents=True, exist_ok=True)
        if not source_dir.exists():
            continue
        for source in sorted(source_dir.glob("*.json")):
            data = json.loads(source.read_text(encoding="utf-8"))
            if "id" not in data or "name" not in data:
                raise ValueError(f"数据文件缺少 id/name: {source}")
            target = target_dir / source.name
            shutil.copyfile(source, target)
            imported[kind].append(data["id"])
    return {"package": info, "imported": imported}
