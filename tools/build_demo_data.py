"""Generate deterministic Pages demo data from the canonical hardware database."""

import json
from pathlib import Path

from app.project_service import ProjectService


ROOT = Path(__file__).resolve().parents[1]


def build_demo_data(output=None):
    service = ProjectService(ROOT / "data")
    examples = []
    for path in sorted((ROOT / "examples").glob("*.json")):
        project = json.loads(path.read_text(encoding="utf-8"))
        result = service.build_project({**project, "include_alternatives": True, "alternative_count": 2})
        examples.append({"project": project, "result": result})
    payload = {
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "chips": service.list_chips(),
        "modules": service.list_modules(),
        "examples": examples,
    }
    target = Path(output) if output else ROOT / "web" / "generated" / "demo-data.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    print(build_demo_data())
