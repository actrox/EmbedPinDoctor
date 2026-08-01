import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def create_release_package(project_root, output_dir, name="EmbedPinDoctor"):
    project_root = Path(project_root); output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    release_dir = output_dir / f"{name}_{stamp}"
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)
    for folder in ["app", "core", "data", "export", "integrations", "versioning", "plugins", "web", "quality", "collaboration"]:
        src = project_root / folder
        if src.exists():
            shutil.copytree(src, release_dir / folder)
    for file_name in ["README.md", "策划方案.md"]:
        src = project_root / file_name
        if src.exists():
            shutil.copyfile(src, release_dir / file_name)
    manifest = {"name": name, "created_at": datetime.now(timezone.utc).isoformat(), "entry": "app/web_app.py"}
    (release_dir / "release_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(release_dir), "manifest": manifest}
