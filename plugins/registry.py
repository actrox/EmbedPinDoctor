import json
from pathlib import Path


def discover_plugins(plugin_dir):
    plugin_dir = Path(plugin_dir)
    plugins = []
    if not plugin_dir.exists():
        return plugins
    for manifest in sorted(plugin_dir.glob("*/plugin.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["path"] = str(manifest.parent)
        plugins.append(data)
    return plugins
