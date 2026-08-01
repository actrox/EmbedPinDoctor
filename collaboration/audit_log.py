import json
from datetime import datetime, timezone
from pathlib import Path


def append_event(log_dir, project_name, actor, action, detail=None):
    log_dir = Path(log_dir); log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{project_name}.events.jsonl"
    event = {"time": datetime.now(timezone.utc).isoformat(), "project": project_name, "actor": actor, "action": action, "detail": detail or {}}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_events(log_dir, project_name):
    path = Path(log_dir) / f"{project_name}.events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
