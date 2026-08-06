import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from core.schema import validate_chip, validate_module


SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?$")
PACKAGE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
PACKAGE_TYPES = {"data", "rules", "plugin"}


def _atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _version_key(version):
    match = SEMVER.fullmatch(str(version))
    if not match:
        raise ValueError(f"无效语义版本: {version}")
    major, minor, patch, prerelease = match.groups()
    identifiers = () if prerelease is None else tuple((0, int(item)) if item.isdigit() else (1, item) for item in prerelease.split("."))
    return int(major), int(minor), int(patch), prerelease is None, identifiers


def compare_versions(left, right):
    return (_version_key(left) > _version_key(right)) - (_version_key(left) < _version_key(right))


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PackageManager:
    def __init__(self, state_dir, data_dir, rule_dir, plugin_dir, app_version="0.0.0"):
        self.state_dir = Path(state_dir)
        self.data_dir = Path(data_dir)
        self.rule_dir = Path(rule_dir)
        self.plugin_dir = Path(plugin_dir)
        self.app_version = app_version
        self.registry_path = self.state_dir / "registry.json"
        self.backup_dir = self.state_dir / "backups"

    def _registry(self):
        if not self.registry_path.exists():
            return {"schema_version": 1, "packages": {}}
        data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or not isinstance(data.get("packages"), dict):
            raise ValueError("生态包注册表格式无效")
        return data

    def list_packages(self):
        return sorted(self._registry()["packages"].values(), key=lambda item: item["id"])

    def inspect(self, package_dir):
        root = Path(package_dir).resolve()
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"缺少生态包清单: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        package_id = str(manifest.get("id", ""))
        package_type = manifest.get("type")
        version = str(manifest.get("version", ""))
        if not PACKAGE_ID.fullmatch(package_id):
            raise ValueError("生态包 id 只能包含小写字母、数字、点、下划线和连字符")
        if package_type not in PACKAGE_TYPES:
            raise ValueError(f"不支持的生态包类型: {package_type}")
        _version_key(version)
        minimum = manifest.get("min_app_version")
        if minimum and compare_versions(self.app_version, minimum) < 0:
            raise ValueError(f"当前应用版本 {self.app_version} 低于生态包要求 {minimum}")

        files = []
        patterns = {"data": ["chips/*.json", "modules/*.json"], "rules": ["rules/*.json"], "plugin": ["plugin.json"]}
        for pattern in patterns[package_type]:
            for source in sorted(root.glob(pattern)):
                if source.is_file():
                    if not source.resolve().is_relative_to(root):
                        raise ValueError(f"生态包文件越界: {source}")
                    relative = source.relative_to(root).as_posix()
                    files.append((relative, source))
        if not files:
            raise ValueError("生态包没有可安装文件")
        checksums = manifest.get("checksums", {})
        if checksums and set(checksums) != {relative for relative, _ in files}:
            raise ValueError("checksums 必须完整覆盖生态包文件")
        for relative, source in files:
            expected = checksums.get(relative)
            if expected and _sha256(source) != str(expected).lower():
                raise ValueError(f"文件哈希不匹配: {relative}")
            data = json.loads(source.read_text(encoding="utf-8"))
            if package_type == "data":
                validate_chip(data) if relative.startswith("chips/") else validate_module(data)
            elif package_type == "rules":
                for field in ["id", "name", "version"]:
                    if not data.get(field):
                        raise ValueError(f"规则文件缺少 {field}: {relative}")
            elif package_type == "plugin":
                if data.get("id") != package_id or data.get("version") != version:
                    raise ValueError("plugin.json 的 id/version 必须与 manifest.json 一致")
        return manifest, files

    def _target(self, package_type, package_id, relative):
        if package_type == "data":
            return self.data_dir / relative
        if package_type == "rules":
            return self.rule_dir / package_id / Path(relative).name
        return self.plugin_dir / package_id / Path(relative).name

    def _managed_target(self, target):
        resolved = Path(target).resolve()
        roots = [self.data_dir.resolve(), self.rule_dir.resolve(), self.plugin_dir.resolve()]
        return any(resolved.is_relative_to(root) for root in roots)

    def install(self, package_dir, allow_downgrade=False):
        manifest, files = self.inspect(package_dir)
        registry = self._registry()
        package_id, version, package_type = manifest["id"], manifest["version"], manifest["type"]
        installed = registry["packages"].get(package_id)
        if installed and installed["type"] != package_type:
            raise ValueError("同名生态包类型冲突")
        if installed and compare_versions(version, installed["version"]) < 0 and not allow_downgrade:
            raise ValueError("拒绝降级安装；如确有需要请显式允许降级")
        old_files = {item["source"]: item for item in installed.get("files", [])} if installed else {}
        if installed and set(old_files) != {relative for relative, _ in files}:
            raise ValueError("更新包文件集合发生变化；请先卸载旧版本再安装")

        backup_root = self.backup_dir / package_id / "baseline"
        inventory = []
        staged = []
        committed = []
        try:
            for relative, source in files:
                target = self._target(package_type, package_id, relative)
                backup = backup_root / relative
                existed = old_files.get(relative, {}).get("existed", target.exists())
                if target.exists() and not installed:
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(prefix=f".{target.stem}-", suffix=".tmp", dir=target.parent)
                os.close(fd)
                shutil.copy2(source, temporary)
                staged.append((Path(temporary), target))
                inventory.append({"source": relative, "target": str(target.resolve()), "existed": existed})
            for temporary, target in staged:
                os.replace(temporary, target)
                committed.append(target)
            record = {"id": package_id, "name": manifest.get("name", package_id), "version": version, "type": package_type, "enabled": True, "files": inventory}
            registry["packages"][package_id] = record
            _atomic_json(self.registry_path, registry)
            return {"installed": True, "package": record, "updated": bool(installed)}
        except Exception:
            for temporary, _ in staged:
                if temporary.exists():
                    temporary.unlink()
            for item, target in zip(inventory, committed):
                backup = backup_root / item["source"]
                if item["existed"] and backup.exists():
                    shutil.copy2(backup, target)
                elif target.exists():
                    target.unlink()
            raise

    def uninstall(self, package_id):
        registry = self._registry()
        record = registry["packages"].get(package_id)
        if not record:
            raise ValueError(f"生态包未安装: {package_id}")
        backup_root = self.backup_dir / package_id / "baseline"
        for item in record["files"]:
            target = Path(item["target"])
            if not self._managed_target(target):
                raise ValueError(f"注册表包含越界文件路径: {target}")
            backup = backup_root / item["source"]
            if item["existed"] and backup.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
            elif target.exists():
                target.unlink()
        del registry["packages"][package_id]
        _atomic_json(self.registry_path, registry)
        return {"uninstalled": True, "id": package_id}

    def set_enabled(self, package_id, enabled):
        registry = self._registry()
        if package_id not in registry["packages"]:
            raise ValueError(f"生态包未安装: {package_id}")
        if registry["packages"][package_id]["type"] != "plugin":
            raise ValueError("只有插件包支持启用或停用；数据包和规则包请通过卸载停用")
        registry["packages"][package_id]["enabled"] = bool(enabled)
        _atomic_json(self.registry_path, registry)
        return registry["packages"][package_id]
