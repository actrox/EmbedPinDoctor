import json
import shutil
from pathlib import Path

from core.schema import SchemaValidationError, validate_chip, validate_module


def import_data_package(package_dir, data_dir):
    package_dir = Path(package_dir)
    data_dir = Path(data_dir)
    manifest = package_dir / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(f"缺少数据包清单: {manifest}")
    info = json.loads(manifest.read_text(encoding="utf-8"))
    imported = {"chips": [], "modules": []}
    validated = []
    for kind in ["chips", "modules"]:
        source_dir = package_dir / kind
        target_dir = data_dir / kind
        if not source_dir.exists():
            continue
        for source in sorted(source_dir.glob("*.json")):
            data = json.loads(source.read_text(encoding="utf-8"))
            try:
                validate_chip(data) if kind == "chips" else validate_module(data)
            except SchemaValidationError as exc:
                raise ValueError(f"数据包校验失败 {source}: {exc}") from exc
            if source.stem != data["id"]:
                raise ValueError(f"数据文件名必须与 id 一致: {source.name} != {data['id']}.json")
            validated.append((kind, source, target_dir / source.name, data["id"]))
    # Validate the entire package before writing any target file.
    for kind, source, target, data_id in validated:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        imported[kind].append(data_id)
    return {"package": info, "imported": imported}
