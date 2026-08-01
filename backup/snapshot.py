import shutil
from datetime import datetime, timezone
from pathlib import Path


def create_backup(project_root, backup_dir):
    project_root = Path(project_root); backup_dir = Path(backup_dir); backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / datetime.now(timezone.utc).strftime("backup_%Y%m%d%H%M%S")
    shutil.copytree(project_root / "projects", target / "projects", dirs_exist_ok=True)
    shutil.copytree(project_root / "data", target / "data", dirs_exist_ok=True)
    return {"path": str(target)}


def restore_backup(backup_path, project_root):
    backup_path = Path(backup_path); project_root = Path(project_root)
    shutil.copytree(backup_path / "projects", project_root / "projects", dirs_exist_ok=True)
    shutil.copytree(backup_path / "data", project_root / "data", dirs_exist_ok=True)
    return {"restored": True, "path": str(backup_path)}
