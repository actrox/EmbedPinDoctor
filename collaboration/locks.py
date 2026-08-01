import json
from datetime import datetime, timezone
from pathlib import Path


def acquire_lock(lock_dir, project_name, actor):
    lock_dir = Path(lock_dir); lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / f"{project_name}.lock.json"
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current.get("actor") != actor:
            return {"locked": False, "current": current}
    data = {"project": project_name, "actor": actor, "time": datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"locked": True, "current": data}


def release_lock(lock_dir, project_name, actor):
    path = Path(lock_dir) / f"{project_name}.lock.json"
    if not path.exists():
        return {"released": True}
    current = json.loads(path.read_text(encoding="utf-8"))
    if current.get("actor") != actor:
        return {"released": False, "current": current}
    path.unlink()
    return {"released": True}
