import json
import re
from pathlib import Path


PLUGIN_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
PLUGIN_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
ALLOWED_CAPABILITIES = {"export", "import", "analyze", "data", "rules"}


def validate_plugin_manifest(data):
    if not isinstance(data, dict):
        raise ValueError("插件清单必须是 JSON 对象")
    if not PLUGIN_ID.fullmatch(str(data.get("id", ""))):
        raise ValueError("插件 id 格式无效")
    if not data.get("name") or not PLUGIN_VERSION.fullmatch(str(data.get("version", ""))):
        raise ValueError("插件清单缺少 name 或 version")
    capabilities = data.get("capabilities", [])
    if not isinstance(capabilities, list) or not set(capabilities).issubset(ALLOWED_CAPABILITIES):
        raise ValueError("插件声明了不支持的 capability")
    return data


def discover_plugins(plugin_dir, states=None):
    plugin_dir = Path(plugin_dir)
    states = states or {}
    plugins = []
    if not plugin_dir.exists():
        return plugins
    seen = set()
    for manifest in sorted(plugin_dir.glob("*/plugin.json")):
        try:
            data = validate_plugin_manifest(json.loads(manifest.read_text(encoding="utf-8")))
            if data["id"] in seen:
                raise ValueError("插件 id 重复")
            seen.add(data["id"])
            data = dict(data)
            data["path"] = str(manifest.parent)
            data["enabled"] = bool(states.get(data["id"], True))
            data["status"] = "ready" if data["enabled"] else "disabled"
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            data = {"id": manifest.parent.name, "name": manifest.parent.name, "path": str(manifest.parent), "enabled": False, "status": "invalid", "error": str(exc), "capabilities": []}
        plugins.append(data)
    return plugins
