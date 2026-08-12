"""Shared application service used by both HTTP adapters."""

import json
from pathlib import Path
from time import perf_counter

from core.allocator import allocate_project, allocate_alternatives
from core.checker import check_project
from core.loader import load_chip, load_module


class ProjectService:
    def __init__(self, builtin_data_dir, user_data_dir=None):
        self.builtin_data_dir = Path(builtin_data_dir)
        self.user_data_dir = Path(user_data_dir) if user_data_dir else None
        self._allocation_cache = {}

    def data_files(self, kind):
        files = {path.name: path for path in (self.builtin_data_dir / kind).glob("*.json")}
        if self.user_data_dir:
            files.update({path.name: path for path in (self.user_data_dir / kind).glob("*.json")})
        return [files[name] for name in sorted(files)]

    def data_file(self, kind, data_id):
        if self.user_data_dir:
            user_path = self.user_data_dir / kind / f"{data_id}.json"
            if user_path.exists():
                return user_path
        return self.builtin_data_dir / kind / f"{data_id}.json"

    def list_chips(self, query=""):
        query = query.lower().strip()
        result = []
        for path in self.data_files("chips"):
            chip = load_chip(path)
            item = {
                "id": chip["id"], "name": chip["name"],
                "voltage": chip.get("voltage", "未知"),
                "tier": "verified" if chip.get("verified") else "experimental",
                "confidence": chip.get("confidence", "low"),
            }
            if not query or query in item["id"].lower() or query in item["name"].lower():
                result.append(item)
        return result

    def list_modules(self, query=""):
        query = query.lower().strip()
        result = []
        for path in self.data_files("modules"):
            data = json.loads(path.read_text(encoding="utf-8"))
            item = {"id": data["id"], "name": data["name"], "voltage": data.get("voltage", "未知"), "description": data.get("description", "")}
            if not query or query in f"{item['id']} {item['name']} {item['description']}".lower():
                result.append(item)
        return result

    def build_project(self, payload):
        chip_id = payload.get("chip_id") or payload.get("chip")
        module_ids = payload.get("module_ids") or payload.get("modules") or []
        if not chip_id:
            raise ValueError("缺少 chip_id")
        if not module_ids:
            raise ValueError("至少选择一个模块")
        chip = load_chip(self.data_file("chips", chip_id))
        modules = [load_module(self.data_file("modules", str(item))) for item in module_ids]
        override = payload.get("allocation")
        started = perf_counter()
        cache_key = json.dumps({"chip": chip_id, "modules": module_ids, "locks": payload.get("locked_pins"), "preferred": payload.get("preferred_allocation"), "strategy": payload.get("strategy", "recommended")}, sort_keys=True, ensure_ascii=False)
        cache_hit = False
        if override:
            allocation = override
            solver = {"status": "manual", "nodes_searched": 0, "limit_reached": False, "assigned_count": sum(item.get("chip_pin") != "未分配" for item in allocation), "total_count": len(allocation)}
        elif cache_key in self._allocation_cache:
            allocation, solver = self._allocation_cache[cache_key]
            allocation = [dict(item) for item in allocation]
            solver = dict(solver)
            cache_hit = True
        else:
            allocation, solver = allocate_project(chip, modules, payload.get("locked_pins"), payload.get("preferred_allocation"), payload.get("strategy", "recommended"), return_metadata=True)
            if len(self._allocation_cache) >= 128:
                self._allocation_cache.pop(next(iter(self._allocation_cache)))
            self._allocation_cache[cache_key] = ([dict(item) for item in allocation], dict(solver))
        solver.update(elapsed_ms=round((perf_counter() - started) * 1000, 2), cache_hit=cache_hit)
        risks = check_project(chip, modules, allocation)
        alternatives = allocate_alternatives(chip, modules, int(payload.get("alternative_count", 3)), payload.get("locked_pins"), payload.get("preferred_allocation"), payload.get("strategy", "recommended")) if payload.get("include_alternatives", False) else []
        return {"chip": chip, "modules": modules, "allocation": allocation, "risks": risks, "alternatives": alternatives, "solver": solver, "data_trust": {"verified": chip.get("verified", False), "tier": "verified" if chip.get("verified") else "experimental", "status": chip.get("data_status"), "source": chip.get("datasheet_url")}}
