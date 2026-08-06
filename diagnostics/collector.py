import json
import platform
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def create_diagnostics(project_root, output_dir, include_project_data=False):
    project_root = Path(project_root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    zip_path = output_dir / f"diagnostics_{stamp}.zip"
    info = {
        "version": (project_root / "VERSION").read_text(encoding="utf-8").strip() if (project_root / "VERSION").exists() else "unknown",
        "python": platform.python_version(),
        "system": platform.platform(),
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("system_info.json", json.dumps(info, ensure_ascii=False, indent=2))
        for rel in ["logs/app.log", "README.md", "VERSION", "CHANGELOG.md"]:
            path = project_root / rel
            if path.exists():
                zf.write(path, rel)
        if include_project_data:
            base = project_root / "projects"
            if base.exists():
                for path in base.glob("*.json"):
                    zf.write(path, str(path.relative_to(project_root)))
    return {"path": str(zip_path), "size": zip_path.stat().st_size, "includes_project_data": include_project_data}
