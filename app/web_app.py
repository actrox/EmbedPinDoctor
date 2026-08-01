from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import mimetypes
import re
import sys
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.loader import load_chip, load_modules
from core.allocator import allocate_project
from core.checker import check_project
from export.markdown import render_markdown
from export.pins import render_pins_header
from export.templates import render_arduino, render_stm32_hal, render_esp_idf, render_kicad_labels
from integrations.package_update import import_data_package
from integrations.risk_explainer import explain_risks
from integrations.code_reverse import reverse_pins_from_code
from integrations.platformio import generate_platformio_project
from integrations.ioc_export import render_ioc_hint
from integrations.kicad_import import import_kicad_labels
from versioning.compare import compare_allocations
from plugins.registry import discover_plugins
from collaboration.audit_log import append_event, read_events
from collaboration.locks import acquire_lock, release_lock
from collaboration.review import create_review, update_review
from quality.design_review import build_design_review, render_design_review_markdown
from quality.rule_pack import import_rule_pack, list_rule_packs
from release.packager import create_release_package
from backup.snapshot import create_backup, restore_backup
from diagnostics.collector import create_diagnostics
from release.build_release import build_release

DATA_DIR = PROJECT_ROOT / "data"
PROJECTS_DIR = PROJECT_ROOT / "projects"
OUTPUT_DIR = PROJECT_ROOT / "output"
WEB_DIR = PROJECT_ROOT / "web"


def _safe_name(name):
    cleaned = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", name).strip("_")
    return cleaned or "untitled_project"


def list_chips(query=""):
    query = query.lower().strip()
    chips = []
    for path in sorted((DATA_DIR / "chips").glob("*.json")):
        chip = load_chip(path)
        item = {"id": chip["id"], "name": chip["name"], "voltage": chip.get("voltage", "未知")}
        if not query or query in item["id"].lower() or query in item["name"].lower():
            chips.append(item)
    return chips


def list_modules(query=""):
    query = query.lower().strip()
    modules = []
    for path in sorted((DATA_DIR / "modules").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        item = {
            "id": data["id"],
            "name": data["name"],
            "voltage": data.get("voltage", "未知"),
            "description": data.get("description", ""),
        }
        haystack = f"{item["id"]} {item["name"]} {item["description"]}".lower()
        if not query or query in haystack:
            modules.append(item)
    return modules


def build_project(payload):
    chip_id = payload.get("chip_id") or payload.get("chip")
    module_ids = payload.get("module_ids") or payload.get("modules") or []
    allocation_override = payload.get("allocation")
    if not chip_id:
        raise ValueError("缺少 chip_id")
    if not module_ids:
        raise ValueError("至少选择一个模块")

    chip = load_chip(DATA_DIR / "chips" / f"{chip_id}.json")
    modules = load_modules(DATA_DIR / "modules", module_ids)
    allocation = allocation_override or allocate_project(chip, modules)
    risks = check_project(chip, modules, allocation)
    return chip, modules, allocation, risks


def save_project(payload):
    project_name = _safe_name(payload.get("project_name", "untitled_project"))
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    path = PROJECTS_DIR / f"{project_name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def export_project(payload, kind):
    chip, modules, allocation, risks = build_project(payload)
    project_name = _safe_name(payload.get("project_name", "demo"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if kind == "markdown":
        text = render_markdown(chip, modules, allocation, risks, payload.get("project_name", project_name), payload.get("notes", ""))
        path = OUTPUT_DIR / f"{project_name}_wiring.md"
    elif kind == "arduino":
        text = render_arduino(chip, allocation)
        path = OUTPUT_DIR / f"{project_name}_arduino.h"
    elif kind == "stm32_hal":
        text = render_stm32_hal(chip, allocation)
        path = OUTPUT_DIR / f"{project_name}_stm32_hal.h"
    elif kind == "esp_idf":
        text = render_esp_idf(chip, allocation)
        path = OUTPUT_DIR / f"{project_name}_esp_idf.h"
    elif kind == "kicad":
        text = render_kicad_labels(chip, allocation)
        path = OUTPUT_DIR / f"{project_name}_kicad_labels.txt"
    elif kind == "pins":
        text = render_pins_header(chip, allocation)
        path = OUTPUT_DIR / f"{project_name}_pins.h"
    else:
        raise ValueError(f"未知导出类型: {kind}")
    path.write_text(text, encoding="utf-8")
    return path


class EmbedPinDoctorHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        if not path.exists() or not path.is_file():
            self._send_json({"error": "文件不存在"}, 404)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_payload(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/chips":
                self._send_json({"chips": list_chips(parse_qs(parsed.query).get("q", [""])[0])})
            elif parsed.path == "/api/modules":
                self._send_json({"modules": list_modules(parse_qs(parsed.query).get("q", [""])[0])})
            elif parsed.path == "/api/projects":
                PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
                projects = [p.stem for p in sorted(PROJECTS_DIR.glob("*.json"))]
                self._send_json({"projects": projects})
            elif parsed.path == "/api/project":
                name = _safe_name(parse_qs(parsed.query).get("name", [""])[0])
                path = PROJECTS_DIR / f"{name}.json"
                self._send_json(json.loads(path.read_text(encoding="utf-8")))
            elif parsed.path == "/api/version":
                version_path = PROJECT_ROOT / "VERSION"
                self._send_json({"version": version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "unknown"})
            elif parsed.path == "/api/examples":
                examples_dir = PROJECT_ROOT / "examples"
                items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(examples_dir.glob("*.json"))] if examples_dir.exists() else []
                self._send_json({"examples": items})
            else:
                target = WEB_DIR / "index.html" if parsed.path == "/" else WEB_DIR / parsed.path.lstrip("/")
                self._send_file(target)
        except Exception as exc:
            self._send_json({"error": str(exc)}, 400)

    def do_POST(self):
        try:
            payload = self._read_payload()
            if self.path == "/api/allocate":
                chip, modules, allocation, risks = build_project(payload)
                risks = explain_risks(risks) if payload.get("explain_risks", True) else risks
                self._send_json({"chip": chip, "modules": modules, "allocation": allocation, "risks": risks})
            elif self.path == "/api/save":
                path = save_project(payload)
                self._send_json({"saved": True, "path": str(path)})
            elif self.path == "/api/export/markdown":
                path = export_project(payload, "markdown")
                self._send_json({"exported": True, "path": str(path)})
            elif self.path == "/api/export/pins":
                path = export_project(payload, "pins")
                self._send_json({"exported": True, "path": str(path)})
            elif self.path == "/api/export/platformio":
                chip, modules, allocation, risks = build_project(payload)
                project_name = _safe_name(payload.get("project_name", "platformio_project"))
                result = generate_platformio_project(OUTPUT_DIR / f"{project_name}_platformio", chip, allocation)
                self._send_json({"generated": True, **result})
            elif self.path == "/api/export/ioc":
                chip, modules, allocation, risks = build_project(payload)
                project_name = _safe_name(payload.get("project_name", "ioc_hint"))
                path = OUTPUT_DIR / f"{project_name}.ioc_hint.txt"
                path.write_text(render_ioc_hint(chip, allocation), encoding="utf-8")
                self._send_json({"exported": True, "path": str(path)})
            elif self.path.startswith("/api/export/"):
                kind = self.path.rsplit("/", 1)[-1]
                path = export_project(payload, kind)
                self._send_json({"exported": True, "path": str(path)})
            elif self.path == "/api/custom/chip":
                data = payload.get("data", payload)
                target = DATA_DIR / "chips" / f"{_safe_name(data.get('id', 'custom_chip'))}.json"
                target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                self._send_json({"saved": True, "path": str(target)})
            elif self.path == "/api/custom/module":
                data = payload.get("data", payload)
                target = DATA_DIR / "modules" / f"{_safe_name(data.get('id', 'custom_module'))}.json"
                target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                self._send_json({"saved": True, "path": str(target)})
            elif self.path == "/api/update/package":
                result = import_data_package(payload["package_dir"], DATA_DIR)
                self._send_json(result)
            elif self.path == "/api/reverse/code":
                pins = reverse_pins_from_code(payload["path"])
                self._send_json({"pins": pins})
            elif self.path == "/api/version/compare":
                changes = compare_allocations(payload.get("old_allocation", []), payload.get("new_allocation", []))
                self._send_json({"changes": changes})
            elif self.path == "/api/kicad/import":
                labels = import_kicad_labels(payload["path"])
                self._send_json({"labels": labels})
            elif self.path == "/api/plugins":
                plugins = discover_plugins(PROJECT_ROOT / "plugins")
                self._send_json({"plugins": plugins})
            elif self.path == "/api/events":
                project = payload.get("project_name", "default")
                self._send_json({"events": read_events(PROJECTS_DIR, project)})
            elif self.path == "/api/lock/acquire":
                self._send_json(acquire_lock(PROJECTS_DIR, payload.get("project_name", "default"), payload.get("actor", "anonymous")))
            elif self.path == "/api/lock/release":
                self._send_json(release_lock(PROJECTS_DIR, payload.get("project_name", "default"), payload.get("actor", "anonymous")))
            elif self.path == "/api/review/create":
                self._send_json(create_review(PROJECTS_DIR, payload.get("project_name", "default"), payload.get("author", "anonymous"), payload.get("summary", ""), payload.get("changes", [])))
            elif self.path == "/api/review/update":
                self._send_json(update_review(PROJECTS_DIR, payload["review_id"], payload.get("actor", "anonymous"), payload.get("status"), payload.get("comment")))
            elif self.path == "/api/design/review":
                chip, modules, allocation, risks = build_project(payload)
                review = build_design_review(chip, modules, allocation, explain_risks(risks))
                self._send_json(review)
            elif self.path == "/api/design/review/export":
                chip, modules, allocation, risks = build_project(payload)
                review = build_design_review(chip, modules, allocation, explain_risks(risks))
                path = OUTPUT_DIR / f"{_safe_name(payload.get('project_name', 'review'))}_design_review.md"
                path.write_text(render_design_review_markdown(review), encoding="utf-8")
                self._send_json({"exported": True, "path": str(path)})
            elif self.path == "/api/rules/list":
                self._send_json({"rules": list_rule_packs(PROJECT_ROOT / 'rule_packs')})
            elif self.path == "/api/rules/import":
                self._send_json(import_rule_pack(payload["package_dir"], PROJECT_ROOT / 'rule_packs'))
            elif self.path == "/api/release/build":
                self._send_json(create_release_package(PROJECT_ROOT, OUTPUT_DIR / 'releases', payload.get('name', 'EmbedPinDoctor')))
            elif self.path == "/api/backup/create":
                self._send_json(create_backup(PROJECT_ROOT, OUTPUT_DIR / 'backups'))
            elif self.path == "/api/backup/restore":
                self._send_json(restore_backup(payload["backup_path"], PROJECT_ROOT))
            elif self.path == "/api/diagnostics/create":
                self._send_json(create_diagnostics(PROJECT_ROOT, OUTPUT_DIR / "diagnostics"))
            elif self.path == "/api/release/build_local":
                self._send_json(build_release())
            else:
                self._send_json({"error": "未知接口"}, 404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, 400)

    def log_message(self, fmt, *args):
        return


def run(host="127.0.0.1", port=8765):
    server = ThreadingHTTPServer((host, port), EmbedPinDoctorHandler)
    print(f"EmbedPinDoctor P1 Web MVP: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
