from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(PROJECT_ROOT))

from core.loader import load_chip, load_module, load_modules
from core.allocator import allocate_project, allocate_alternatives
from core.checker import check_project
from core.pin_diagram import generate_chip_svg
from export.markdown import render_markdown
from export.pins import render_pins_header
from export.templates import render_arduino, render_stm32_hal, render_esp_idf, render_kicad_labels
from integrations.package_update import import_data_package
from integrations.risk_explainer import explain_risks
from integrations.code_reverse import reverse_pins_from_code
from integrations.platformio import generate_platformio_project
from integrations.ioc_export import render_ioc_hint
from integrations.ioc_import import import_ioc
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
import logging
import os
import json

from app.schemas import (
    AllocateRequest, AllocateResponse, AllocationItem,
    ExportRequest, ProjectNameRequest, SaveProjectRequest,
    ScanProjectRequest, SimpleIdRequest, PackageDirRequest,
    PathRequest, RestoreRequest, DiagnosticsRequest,
    LockRequest, ReviewCreateRequest, ReviewUpdateRequest,
    DesignReviewRequest, ReleaseBuildRequest,
    RuleImportRequest, EcosystemEnableRequest,
    EventReadRequest, KiCadImportRequest, VersionCompareRequest,
    CustomSaveRequest,
)
from app.project_service import ProjectService

logger = logging.getLogger(__name__)

USER_ROOT = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EmbedPinDoctor") if getattr(sys, "frozen", False) else PROJECT_ROOT
BUILTIN_DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR = BUILTIN_DATA_DIR
USER_DATA_DIR = USER_ROOT / "user_data"
PROJECTS_DIR = USER_ROOT / "projects"
OUTPUT_DIR = USER_ROOT / "output"
WEB_DIR = PROJECT_ROOT / "web"
PROJECT_STORE = ProjectStore(PROJECTS_DIR)
APP_VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip() if (PROJECT_ROOT / "VERSION").exists() else "0.0.0"
INSTALLED_PLUGIN_DIR = USER_ROOT / "user_plugins"
INSTALLED_RULE_DIR = USER_ROOT / "user_rule_packs"
ECOSYSTEM = PackageManager(USER_ROOT / ".ecosystem", USER_DATA_DIR, INSTALLED_RULE_DIR, INSTALLED_PLUGIN_DIR, APP_VERSION)
PROJECT_SERVICE = ProjectService(DATA_DIR, USER_DATA_DIR)

import re as _re

def _safe_name(name):
    cleaned = _re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", name).strip("_")
    return cleaned or "untitled_project"

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

def list_chips(query=""):
    return PROJECT_SERVICE.list_chips(query)

def list_modules(query=""):
    return PROJECT_SERVICE.list_modules(query)

def build_project(payload_dict):
    result = PROJECT_SERVICE.build_project(payload_dict)
    return result["chip"], result["modules"], result["allocation"], result["risks"]

def export_project(payload_dict, kind):
    chip, modules, allocation, risks = build_project(payload_dict)
    project_name = _safe_name(payload_dict.get("project_name", "demo"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if kind == "markdown":
        text = render_markdown(chip, modules, allocation, risks, payload_dict.get("project_name", project_name), payload_dict.get("notes", ""))
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

app = FastAPI(title="EmbedPinDoctor API", version=APP_VERSION)

# ---------- GET ----------
@app.get("/api/chips")
def api_chips(q: str = ""):
    try:
        return {"chips": list_chips(q)}
    except Exception as e:
        logger.exception("chips failed")
        raise HTTPException(400, detail=str(e))

@app.get("/api/modules")
def api_modules(q: str = ""):
    try:
        return {"modules": list_modules(q)}
    except Exception as e:
        logger.exception("modules failed")
        raise HTTPException(400, detail=str(e))

@app.get("/api/projects")
def api_projects():
    try:
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        return {"projects": [p.stem for p in sorted(PROJECTS_DIR.glob("*.json"))]}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.get("/api/project")
def api_project(name: str = ""):
    try:
        safe = _safe_name(name)
        project, migrations = PROJECT_STORE.load(safe)
        project["_migration"] = migrations
        project["_history"] = PROJECT_STORE.history(safe)
        return project
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.get("/api/project/history")
def api_project_history(name: str = ""):
    try:
        return PROJECT_STORE.history(_safe_name(name))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.get("/api/version")
def api_version():
    return {"version": APP_VERSION}

@app.get("/api/ecosystem")
def api_ecosystem():
    try:
        packages = ECOSYSTEM.list_packages()
        states = {item["id"]: item.get("enabled", True) for item in packages if item["type"] == "plugin"}
        return {"packages": packages, "plugins": list_plugins(states)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.get("/api/examples")
def api_examples():
    try:
        examples_dir = PROJECT_ROOT / "examples"
        items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(examples_dir.glob("*.json"))] if examples_dir.exists() else []
        return {"examples": items}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.get("/api/diagram/svg")
def api_diagram_svg(chip_id: str = Query(...)):
    try:
        chip = load_chip(_data_file("chips", chip_id))
        svg = generate_chip_svg(chip)
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# ---------- POST ----------
@app.post("/api/allocate")
def api_allocate(req: AllocateRequest):
    try:
        d = req.model_dump()
        result = PROJECT_SERVICE.build_project(d)
        chip, modules, allocation, risks = result["chip"], result["modules"], result["allocation"], result["risks"]
        if req.explain_risks:
            risks = explain_risks(risks)
        return {**result, "risks": risks}
    except Exception as e:
        logger.exception("allocate failed")
        raise HTTPException(400, detail=str(e))

@app.post("/api/scan-project")
def api_scan_project(req: ScanProjectRequest):
    try:
        d = req.model_dump()
        scan = scan_project(req.project_path)
        requested_chip_id = d.get("chip_id")
        if scan.get("suggested_chip_id") and req.use_detected_chip:
            d["chip_id"] = scan["suggested_chip_id"]
        result = PROJECT_SERVICE.build_project(d)
        chip, modules, allocation, risks = result["chip"], result["modules"], result["allocation"], result["risks"]
        comparison = compare_scan(scan, chip, allocation, d.get("signal_mapping"))
        combined_risks = explain_risks(risks + comparison["risks"])
        return {**result, "risks": combined_risks, "scan": scan, "comparison": comparison,
                "chip_detection": {"requested": requested_chip_id,
                                   "detected": scan.get("suggested_chip_id"),
                                   "used": chip["id"]}}
    except Exception as e:
        logger.exception("scan failed")
        raise HTTPException(400, detail=str(e))

@app.post("/api/save")
def api_save(req: SaveProjectRequest):
    try:
        path, migrations = PROJECT_STORE.save(req.model_dump())
        return {"saved": True, "path": str(path), "migrations": migrations,
                "history": PROJECT_STORE.history(req.project_name)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/project/undo")
def api_project_undo(req: ProjectNameRequest):
    try:
        project, migrations = PROJECT_STORE.undo(req.project_name)
        return {"project": project, "migrations": migrations,
                "history": PROJECT_STORE.history(req.project_name)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/project/redo")
def api_project_redo(req: ProjectNameRequest):
    try:
        project, migrations = PROJECT_STORE.redo(req.project_name)
        return {"project": project, "migrations": migrations,
                "history": PROJECT_STORE.history(req.project_name)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/export/markdown")
def api_export_markdown(req: ExportRequest):
    try:
        p = export_project(req.model_dump(), "markdown")
        return {"exported": True, "path": str(p)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/export/pins")
def api_export_pins(req: ExportRequest):
    try:
        p = export_project(req.model_dump(), "pins")
        return {"exported": True, "path": str(p)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/export/platformio")
def api_export_platformio(req: ExportRequest):
    try:
        d = req.model_dump()
        chip, modules, allocation, risks = build_project(d)
        project_name = _safe_name(req.project_name or "platformio_project")
        result = generate_platformio_project(OUTPUT_DIR / f"{project_name}_platformio", chip, allocation)
        return {"generated": True, **result}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/export/ioc")
def api_export_ioc(req: ExportRequest):
    try:
        d = req.model_dump()
        chip, modules, allocation, risks = build_project(d)
        project_name = _safe_name(req.project_name or "ioc_hint")
        path = OUTPUT_DIR / f"{project_name}.ioc_hint.txt"
        path.write_text(render_ioc_hint(chip, allocation), encoding="utf-8")
        return {"exported": True, "path": str(path)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/export/{kind}")
def api_export_generic(kind: str, req: ExportRequest):
    try:
        p = export_project(req.model_dump(), kind)
        return {"exported": True, "path": str(p)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/custom/chip")
def api_custom_chip(req: CustomSaveRequest):
    try:
        data = req.data if req.data is not None else req.model_dump(exclude_unset=True)
        target = USER_DATA_DIR / "chips" / f"{_safe_name(data.get('id', 'custom_chip'))}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"saved": True, "path": str(target)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/custom/module")
def api_custom_module(req: CustomSaveRequest):
    try:
        data = req.data if req.data is not None else req.model_dump(exclude_unset=True)
        target = USER_DATA_DIR / "modules" / f"{_safe_name(data.get('id', 'custom_module'))}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"saved": True, "path": str(target)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/update/package")
def api_update_package(req: PackageDirRequest):
    try:
        return import_data_package(req.package_dir, USER_DATA_DIR)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/reverse/code")
def api_reverse_code(req: PathRequest):
    try:
        return {"pins": reverse_pins_from_code(req.path)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/version/compare")
def api_version_compare(req: VersionCompareRequest):
    try:
        changes = compare_allocations(
            [i.model_dump() for i in req.old_allocation],
            [i.model_dump() for i in req.new_allocation])
        return {"changes": changes}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/kicad/import")
def api_kicad_import(req: KiCadImportRequest):
    try:
        return {"labels": import_kicad_labels(req.path)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/ioc/import")
def api_ioc_import(req: KiCadImportRequest):
    try:
        return import_ioc(req.path)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/export/svg")
def api_export_svg(req: ExportRequest):
    try:
        d = req.model_dump()
        chip, modules, allocation, risks = build_project(d)
        if req.explain_risks:
            risks = explain_risks(risks)
        svg = generate_chip_svg(chip, allocation, risks)
        project_name = _safe_name(req.project_name or "pin_diagram")
        path = OUTPUT_DIR / f"{project_name}_pins.svg"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")
        return {"exported": True, "path": str(path)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/plugins")
def api_plugins():
    try:
        packages = ECOSYSTEM.list_packages()
        states = {item["id"]: item.get("enabled", True) for item in packages if item["type"] == "plugin"}
        return {"plugins": list_plugins(states)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/ecosystem/install")
def api_ecosystem_install(req: PackageDirRequest):
    try:
        return ECOSYSTEM.install(req.package_dir, req.allow_downgrade)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/ecosystem/uninstall")
def api_ecosystem_uninstall(req: SimpleIdRequest):
    try:
        return ECOSYSTEM.uninstall(req.id)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/ecosystem/enable")
def api_ecosystem_enable(req: EcosystemEnableRequest):
    try:
        return {"package": ECOSYSTEM.set_enabled(req.id, req.enabled)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/events")
def api_events(req: EventReadRequest):
    try:
        return {"events": read_events(PROJECTS_DIR, req.project_name)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/lock/acquire")
def api_lock_acquire(req: LockRequest):
    try:
        return acquire_lock(PROJECTS_DIR, req.project_name, req.actor)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/lock/release")
def api_lock_release(req: LockRequest):
    try:
        return release_lock(PROJECTS_DIR, req.project_name, req.actor)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/review/create")
def api_review_create(req: ReviewCreateRequest):
    try:
        return create_review(PROJECTS_DIR, req.project_name, req.author, req.summary, req.changes)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/review/update")
def api_review_update(req: ReviewUpdateRequest):
    try:
        return update_review(PROJECTS_DIR, req.review_id, req.actor, req.status, req.comment)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/design/review")
def api_design_review(req: DesignReviewRequest):
    try:
        d = req.model_dump()
        chip, modules, allocation, risks = build_project(d)
        return build_design_review(chip, modules, allocation, explain_risks(risks))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/design/review/export")
def api_design_review_export(req: DesignReviewRequest):
    try:
        d = req.model_dump()
        chip, modules, allocation, risks = build_project(d)
        review = build_design_review(chip, modules, allocation, explain_risks(risks))
        path = OUTPUT_DIR / f"{_safe_name(req.project_name or 'review')}_design_review.md"
        path.write_text(render_design_review_markdown(review), encoding="utf-8")
        return {"exported": True, "path": str(path)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/rules/list")
def api_rules_list():
    try:
        return {"rules": list_rule_packs(PROJECT_ROOT / 'rule_packs')}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/rules/import")
def api_rules_import(req: RuleImportRequest):
    try:
        return import_rule_pack(req.package_dir, PROJECT_ROOT / 'rule_packs')
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/release/build")
def api_release_build(req: ReleaseBuildRequest):
    try:
        return create_release_package(PROJECT_ROOT, OUTPUT_DIR / 'releases', req.name)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/backup/create")
def api_backup_create():
    try:
        return create_backup(PROJECT_ROOT, OUTPUT_DIR / 'backups')
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/backup/restore")
def api_backup_restore(req: RestoreRequest):
    try:
        return restore_backup(req.backup_path, PROJECT_ROOT)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/diagnostics/create")
def api_diagnostics_create(req: DiagnosticsRequest):
    try:
        return create_diagnostics(PROJECT_ROOT, OUTPUT_DIR / "diagnostics", req.include_project_data)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/api/release/build_local")
def api_release_build_local():
    try:
        return build_release()
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# ---------- 启动 ----------
def run(host="127.0.0.1", port=8765):
    import uvicorn
    print(f"EmbedPinDoctor (FastAPI): http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

# 静态文件最后挂载，避免掩盖 API 路由
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")

if __name__ == "__main__":
    run()
