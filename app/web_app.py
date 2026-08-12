from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import logging
import mimetypes
import os
import re
import secrets
import sys
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(PROJECT_ROOT))

from core.loader import load_chip, load_module, load_modules
from core.allocator import allocate_project, allocate_alternatives
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
from integrations.project_scanner import scan_project, compare_scan
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
from core.project_store import ProjectStore
from ecosystem.package_manager import PackageManager
from core.pin_diagram import generate_chip_svg
from integrations.ioc_import import import_ioc
from app.project_service import ProjectService

USER_ROOT = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EmbedPinDoctor") if getattr(sys, "frozen", False) else PROJECT_ROOT
BUILTIN_DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR = BUILTIN_DATA_DIR
USER_DATA_DIR = USER_ROOT / "user_data"
PROJECTS_DIR = USER_ROOT / "projects"
OUTPUT_DIR = USER_ROOT / "output"
WEB_DIR = PROJECT_ROOT / "web"
PROJECT_STORE = ProjectStore(PROJECTS_DIR)
logger = logging.getLogger(__name__)
APP_VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip() if (PROJECT_ROOT / "VERSION").exists() else "0.0.0"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
SESSION_TOKEN = os.environ.get("EMBEDPIN_SESSION_TOKEN") or secrets.token_urlsafe(24)
INSTALLED_PLUGIN_DIR = USER_ROOT / "user_plugins"
INSTALLED_RULE_DIR = USER_ROOT / "user_rule_packs"
ECOSYSTEM = PackageManager(USER_ROOT / ".ecosystem", USER_DATA_DIR, INSTALLED_RULE_DIR, INSTALLED_PLUGIN_DIR, APP_VERSION)
PROJECT_SERVICE = ProjectService(DATA_DIR, USER_DATA_DIR)


def list_plugins(states=None):
    plugins = discover_plugins(PROJECT_ROOT / "plugins", states)
    if INSTALLED_PLUGIN_DIR.resolve() != (PROJECT_ROOT / "plugins").resolve():
        known = {item["id"] for item in plugins}
        plugins.extend(item for item in discover_plugins(INSTALLED_PLUGIN_DIR, states) if item["id"] not in known)
    return plugins


def _data_files(kind):
    files = {path.name: path for path in (DATA_DIR / kind).glob("*.json")}
    files.update({path.name: path for path in (USER_DATA_DIR / kind).glob("*.json")})
    return [files[name] for name in sorted(files)]


def _data_file(kind, data_id):
    user_path = USER_DATA_DIR / kind / f"{data_id}.json"
    return user_path if user_path.exists() else DATA_DIR / kind / f"{data_id}.json"


def _safe_name(name):
    cleaned = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", name).strip("_")
    return cleaned or "untitled_project"


def list_chips(query=""):
    return PROJECT_SERVICE.list_chips(query)


def list_modules(query=""):
    return PROJECT_SERVICE.list_modules(query)


class InputValidationError(ValueError):
    def __init__(self, field, message):
        super().__init__(f"参数错误 [{field}]: {message}")
        self.field = field


def _require(payload, field, types=None, allow_empty=False):
    if field not in payload:
        raise InputValidationError(field, "缺少必填字段")
    value = payload[field]
    if types is not None and value is not None and not isinstance(value, types):
        raise InputValidationError(field, f"应为 {types}，实际 {type(value).__name__}")
    if not allow_empty and value in (None, "", [], {}):
        raise InputValidationError(field, "不能为空")
    return value


def build_project(payload):
    try:
        result = PROJECT_SERVICE.build_project(payload)
    except ValueError as exc:
        raise InputValidationError("project", str(exc)) from exc
    return result["chip"], result["modules"], result["allocation"], result["risks"], result["solver"]


def save_project(payload):
    _require(payload, "project_name", str, allow_empty=False)
    return PROJECT_STORE.save(payload)


def export_project(payload, kind):
    chip, modules, allocation, risks, _solver = build_project(payload)
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
    GET_ROUTES = {
        "/api/chips": "_get_chips",
        "/api/modules": "_get_modules",
        "/api/projects": "_get_projects",
        "/api/project": "_get_project",
        "/api/project/history": "_get_project_history",
        "/api/version": "_get_version",
        "/api/ecosystem": "_get_ecosystem",
        "/api/examples": "_get_examples",
        "/api/diagram/svg": "_get_diagram_svg",
    }
    POST_ROUTES = {
        "/api/allocate": "_post_allocate",
        "/api/scan-project": "_post_scan_project",
        "/api/save": "_post_save",
        "/api/project/undo": "_post_undo_redo",
        "/api/project/redo": "_post_undo_redo",
        "/api/export/markdown": "_post_export_markdown",
        "/api/export/pins": "_post_export_pins",
        "/api/export/platformio": "_post_export_platformio",
        "/api/export/ioc": "_post_export_ioc",
        "/api/export/svg": "_post_export_svg",
        "/api/custom/chip": "_post_custom_chip",
        "/api/custom/module": "_post_custom_module",
        "/api/update/package": "_post_update_package",
        "/api/reverse/code": "_post_reverse_code",
        "/api/version/compare": "_post_version_compare",
        "/api/kicad/import": "_post_kicad_import",
        "/api/ioc/import": "_post_ioc_import",
        "/api/plugins": "_post_plugins",
        "/api/ecosystem/install": "_post_ecosystem_install",
        "/api/ecosystem/uninstall": "_post_ecosystem_uninstall",
        "/api/ecosystem/enable": "_post_ecosystem_enable",
        "/api/events": "_post_events",
        "/api/lock/acquire": "_post_lock_acquire",
        "/api/lock/release": "_post_lock_release",
        "/api/review/create": "_post_review_create",
        "/api/review/update": "_post_review_update",
        "/api/design/review": "_post_design_review",
        "/api/design/review/export": "_post_design_review_export",
        "/api/rules/list": "_post_rules_list",
        "/api/rules/import": "_post_rules_import",
        "/api/release/build": "_post_release_build",
        "/api/backup/create": "_post_backup_create",
        "/api/backup/restore": "_post_backup_restore",
        "/api/diagnostics/create": "_post_diagnostics_create",
        "/api/release/build_local": "_post_release_build_local",
    }

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _safe_error(self, exc):
        if isinstance(exc, (InputValidationError, ValueError, KeyError, json.JSONDecodeError)):
            return str(exc)
        return "内部处理失败，请查看本地日志"

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
        if length > MAX_REQUEST_BYTES:
            raise InputValidationError("request", f"请求体不能超过 {MAX_REQUEST_BYTES // 1024 // 1024}MB")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        handler_name = self.GET_ROUTES.get(parsed.path)
        if handler_name:
            try:
                getattr(self, handler_name)(parse_qs(parsed.query))
            except InputValidationError as exc:
                self._send_json({"error": str(exc), "code": "input_error", "field": exc.field}, 400)
            except Exception as exc:
                logger.exception("GET %s failed", parsed.path)
                self._send_json({"error": self._safe_error(exc)}, 400)
        else:
            self._serve_static(parsed.path)

    def _serve_static(self, path):
        target = WEB_DIR / "index.html" if path == "/" else WEB_DIR / path.lstrip("/")
        resolved = target.resolve()
        if not resolved.is_relative_to(WEB_DIR.resolve()):
            self._send_json({"error": "静态文件路径无效"}, 404)
        else:
            self._serve_file(resolved)

    def _serve_file(self, resolved):
        try:
            self._send_file(resolved)
        except Exception as exc:
            logger.exception("GET static failed")
            self._send_json({"error": str(exc)}, 400)

    def do_POST(self):
        try:
            payload = self._read_payload()
            handler_name = self.POST_ROUTES.get(self.path)
            if handler_name:
                getattr(self, handler_name)(payload)
            elif self.path.startswith("/api/export/"):
                kind = self.path.rsplit("/", 1)[-1]
                path = export_project(payload, kind)
                self._send_json({"exported": True, "path": str(path)})
            else:
                self._send_json({"error": "未知接口"}, 404)
        except InputValidationError as exc:
            self._send_json({"error": str(exc), "code": "input_error", "field": exc.field}, 400)
        except Exception as exc:
            logger.exception("POST %s failed", self.path)
            self._send_json({"error": self._safe_error(exc)}, 400)

    def log_message(self, fmt, *args):
        return

    # --- GET handlers ---

    def _get_chips(self, query):
        self._send_json({"chips": list_chips(query.get("q", [""])[0])})

    def _get_modules(self, query):
        self._send_json({"modules": list_modules(query.get("q", [""])[0])})

    def _get_projects(self, _query):
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        projects = [p.stem for p in sorted(PROJECTS_DIR.glob("*.json"))]
        self._send_json({"projects": projects})

    def _get_project(self, query):
        name = _safe_name(query.get("name", [""])[0])
        project, migrations = PROJECT_STORE.load(name)
        project["_migration"] = migrations
        project["_history"] = PROJECT_STORE.history(name)
        self._send_json(project)

    def _get_project_history(self, query):
        name = _safe_name(query.get("name", [""])[0])
        self._send_json(PROJECT_STORE.history(name))

    def _get_version(self, _query):
        version_path = PROJECT_ROOT / "VERSION"
        self._send_json({"version": version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "unknown"})

    def _get_ecosystem(self, _query):
        packages = ECOSYSTEM.list_packages()
        states = {item["id"]: item.get("enabled", True) for item in packages if item["type"] == "plugin"}
        self._send_json({"packages": packages, "plugins": list_plugins(states)})

    def _get_examples(self, _query):
        examples_dir = PROJECT_ROOT / "examples"
        items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(examples_dir.glob("*.json"))] if examples_dir.exists() else []
        self._send_json({"examples": items})

    def _get_diagram_svg(self, query):
        chip_id = query.get("chip_id", [""])[0]
        if not chip_id:
            raise InputValidationError("chip_id", "缺少必填参数")
        chip = load_chip(_data_file("chips", chip_id))
        svg = generate_chip_svg(chip)
        body = svg.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- POST handlers ---

    def _post_allocate(self, payload):
        result = PROJECT_SERVICE.build_project(payload)
        chip, modules, allocation, risks, solver = result["chip"], result["modules"], result["allocation"], result["risks"], result["solver"]
        risks = explain_risks(risks) if payload.get("explain_risks", True) else risks
        self._send_json({**result, "risks": risks})

    def _post_scan_project(self, payload):
        scan = scan_project(payload["project_path"])
        requested_chip_id = payload.get("chip_id")
        if scan.get("suggested_chip_id") and payload.get("use_detected_chip", True):
            payload["chip_id"] = scan["suggested_chip_id"]
        chip, modules, allocation, risks, solver = build_project(payload)
        comparison = compare_scan(scan, chip, allocation, payload.get("signal_mapping"))
        combined_risks = explain_risks(risks + comparison["risks"])
        alternatives = allocate_alternatives(chip, modules, int(payload.get("alternative_count", 3)), payload.get("locked_pins"), payload.get("preferred_allocation"), payload.get("strategy", "recommended")) if payload.get("include_alternatives", False) else []
        self._send_json({"chip": chip, "modules": modules, "allocation": allocation, "risks": combined_risks, "scan": scan, "comparison": comparison, "alternatives": alternatives, "solver": solver, "data_trust": {"verified": chip.get("verified", False), "status": chip.get("data_status"), "source": chip.get("datasheet_url")}, "chip_detection": {"requested": requested_chip_id, "detected": scan.get("suggested_chip_id"), "used": chip["id"]}})

    def _post_save(self, payload):
        path, migrations = save_project(payload)
        self._send_json({"saved": True, "path": str(path), "migrations": migrations, "history": PROJECT_STORE.history(payload.get("project_name", "untitled_project"))})

    def _post_undo_redo(self, payload):
        name = payload.get("project_name", "untitled_project")
        action = PROJECT_STORE.undo if self.path.endswith("undo") else PROJECT_STORE.redo
        project, migrations = action(name)
        self._send_json({"project": project, "migrations": migrations, "history": PROJECT_STORE.history(name)})

    def _post_export_markdown(self, payload):
        path = export_project(payload, "markdown")
        self._send_json({"exported": True, "path": str(path)})

    def _post_export_pins(self, payload):
        path = export_project(payload, "pins")
        self._send_json({"exported": True, "path": str(path)})

    def _post_export_platformio(self, payload):
        chip, modules, allocation, risks, _solver = build_project(payload)
        project_name = _safe_name(payload.get("project_name", "platformio_project"))
        result = generate_platformio_project(OUTPUT_DIR / f"{project_name}_platformio", chip, allocation)
        self._send_json({"generated": True, **result})

    def _post_export_ioc(self, payload):
        chip, modules, allocation, risks, _solver = build_project(payload)
        project_name = _safe_name(payload.get("project_name", "ioc_hint"))
        path = OUTPUT_DIR / f"{project_name}.ioc_hint.txt"
        path.write_text(render_ioc_hint(chip, allocation), encoding="utf-8")
        self._send_json({"exported": True, "path": str(path)})

    def _post_custom_chip(self, payload):
        data = payload.get("data", payload)
        target = USER_DATA_DIR / "chips" / f"{_safe_name(data.get('id', 'custom_chip'))}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._send_json({"saved": True, "path": str(target)})

    def _post_custom_module(self, payload):
        data = payload.get("data", payload)
        target = USER_DATA_DIR / "modules" / f"{_safe_name(data.get('id', 'custom_module'))}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._send_json({"saved": True, "path": str(target)})

    def _post_update_package(self, payload):
        self._send_json(import_data_package(payload["package_dir"], USER_DATA_DIR))

    def _post_reverse_code(self, payload):
        _require(payload, "path", str)
        self._send_json({"pins": reverse_pins_from_code(payload["path"])})

    def _post_version_compare(self, payload):
        changes = compare_allocations(payload.get("old_allocation", []), payload.get("new_allocation", []))
        self._send_json({"changes": changes})

    def _post_kicad_import(self, payload):
        _require(payload, "path", str)
        self._send_json({"labels": import_kicad_labels(payload["path"])})

    def _post_ioc_import(self, payload):
        _require(payload, "path", str)
        self._send_json(import_ioc(payload["path"]))

    def _post_export_svg(self, payload):
        chip, modules, allocation, risks, _solver = build_project(payload)
        if payload.get("explain_risks", True):
            risks = explain_risks(risks)
        svg = generate_chip_svg(chip, allocation, risks)
        project_name = _safe_name(payload.get("project_name", "pin_diagram"))
        path = OUTPUT_DIR / f"{project_name}_pins.svg"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")
        self._send_json({"exported": True, "path": str(path)})

    def _post_plugins(self, payload):
        packages = ECOSYSTEM.list_packages()
        states = {item["id"]: item.get("enabled", True) for item in packages if item["type"] == "plugin"}
        self._send_json({"plugins": list_plugins(states)})

    def _post_ecosystem_install(self, payload):
        self._send_json(ECOSYSTEM.install(payload["package_dir"], bool(payload.get("allow_downgrade", False))))

    def _post_ecosystem_uninstall(self, payload):
        self._send_json(ECOSYSTEM.uninstall(payload["id"]))

    def _post_ecosystem_enable(self, payload):
        self._send_json({"package": ECOSYSTEM.set_enabled(payload["id"], bool(payload.get("enabled", True)))})

    def _post_events(self, payload):
        self._send_json({"events": read_events(PROJECTS_DIR, payload.get("project_name", "default"))})

    def _post_lock_acquire(self, payload):
        self._send_json(acquire_lock(PROJECTS_DIR, payload.get("project_name", "default"), payload.get("actor", "anonymous")))

    def _post_lock_release(self, payload):
        self._send_json(release_lock(PROJECTS_DIR, payload.get("project_name", "default"), payload.get("actor", "anonymous")))

    def _post_review_create(self, payload):
        self._send_json(create_review(PROJECTS_DIR, payload.get("project_name", "default"), payload.get("author", "anonymous"), payload.get("summary", ""), payload.get("changes", [])))

    def _post_review_update(self, payload):
        self._send_json(update_review(PROJECTS_DIR, payload["review_id"], payload.get("actor", "anonymous"), payload.get("status"), payload.get("comment")))

    def _post_design_review(self, payload):
        chip, modules, allocation, risks, _solver = build_project(payload)
        self._send_json(build_design_review(chip, modules, allocation, explain_risks(risks)))

    def _post_design_review_export(self, payload):
        chip, modules, allocation, risks, _solver = build_project(payload)
        review = build_design_review(chip, modules, allocation, explain_risks(risks))
        path = OUTPUT_DIR / f"{_safe_name(payload.get('project_name', 'review'))}_design_review.md"
        path.write_text(render_design_review_markdown(review), encoding="utf-8")
        self._send_json({"exported": True, "path": str(path)})

    def _post_rules_list(self, payload):
        self._send_json({"rules": list_rule_packs(PROJECT_ROOT / 'rule_packs')})

    def _post_rules_import(self, payload):
        self._send_json(import_rule_pack(payload["package_dir"], PROJECT_ROOT / 'rule_packs'))

    def _post_release_build(self, payload):
        self._send_json(create_release_package(PROJECT_ROOT, OUTPUT_DIR / 'releases', payload.get('name', 'EmbedPinDoctor')))

    def _post_backup_create(self, payload):
        self._send_json(create_backup(PROJECT_ROOT, OUTPUT_DIR / 'backups'))

    def _post_backup_restore(self, payload):
        self._send_json(restore_backup(payload["backup_path"], PROJECT_ROOT))

    def _post_diagnostics_create(self, payload):
        self._send_json(create_diagnostics(PROJECT_ROOT, OUTPUT_DIR / "diagnostics", bool(payload.get("include_project_data", False))))

    def _post_release_build_local(self, payload):
        self._send_json(build_release())


def run(host="127.0.0.1", port=8765):
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("EMBEDPIN_ALLOW_REMOTE") != "1":
        raise RuntimeError("拒绝外部监听；如确有需要，请显式设置 EMBEDPIN_ALLOW_REMOTE=1 并自行配置网络访问控制")
    server = ThreadingHTTPServer((host, port), EmbedPinDoctorHandler)
    print(f"EmbedPinDoctor P1 Web MVP: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run(os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8765")))
