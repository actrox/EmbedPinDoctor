import json
import re
from pathlib import Path


VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
REQUIRED_PATHS = [
    "launcher.py", "VERSION", "README.md", "release_manifest.json",
    "app/web_app.py", "core/allocator.py", "ecosystem/package_manager.py", "web/index.html", "web/app.js",
    "data/chips", "data/modules",
]


def validate_release(path):
    root = Path(path)
    errors = []
    if not root.is_dir():
        return {"valid": False, "errors": ["发布目录不存在"]}
    for relative in REQUIRED_PATHS:
        if not (root / relative).exists():
            errors.append(f"缺少发布文件: {relative}")
    version = (root / "VERSION").read_text(encoding="utf-8").strip() if (root / "VERSION").exists() else ""
    if not VERSION_PATTERN.fullmatch(version):
        errors.append("VERSION 不是有效的语义版本")
    manifest_path = root / "release_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("version") != version:
                errors.append("发布清单版本与 VERSION 不一致")
            if manifest.get("entry") != "launcher.py":
                errors.append("发布清单入口不是 launcher.py")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"发布清单不可读: {exc}")
    return {"valid": not errors, "errors": errors, "version": version}
