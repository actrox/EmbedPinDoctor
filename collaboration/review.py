import json
from datetime import datetime, timezone
from pathlib import Path


def create_review(review_dir, project_name, author, summary, changes):
    review_dir = Path(review_dir); review_dir.mkdir(parents=True, exist_ok=True)
    review_id = f"{project_name}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    data = {"id": review_id, "project": project_name, "author": author, "summary": summary, "changes": changes, "status": "pending", "comments": []}
    (review_dir / f"{review_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def update_review(review_dir, review_id, actor, status=None, comment=None):
    path = Path(review_dir) / f"{review_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if status:
        data["status"] = status
    if comment:
        data["comments"].append({"actor": actor, "comment": comment, "time": datetime.now(timezone.utc).isoformat()})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
