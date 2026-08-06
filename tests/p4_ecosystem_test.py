import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ecosystem.package_manager import PackageManager, compare_versions
from plugins.registry import discover_plugins


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    assert compare_versions("1.0.0", "1.0.0-rc.1") > 0
    assert compare_versions("1.0.0-beta.10", "1.0.0-beta.2") > 0
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        manager = PackageManager(temp / "state", temp / "data", temp / "rules", temp / "plugins", "0.1.0-alpha.8")

        original = json.loads((ROOT / "data/modules/button.json").read_text(encoding="utf-8"))
        original["name"] = "Original Button"
        target = temp / "data/modules/button.json"
        write_json(target, original)
        updated = dict(original)
        updated["name"] = "Package Button"
        package = temp / "button_pack"
        source = package / "modules/button.json"
        write_json(source, updated)
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        write_json(package / "manifest.json", {"id": "button-pack", "name": "Button Pack", "version": "1.0.0", "type": "data", "min_app_version": "0.1.0-alpha.1", "checksums": {"modules/button.json": checksum}})
        result = manager.install(package)
        assert result["installed"] and json.loads(target.read_text(encoding="utf-8"))["name"] == "Package Button"
        assert manager.list_packages()[0]["version"] == "1.0.0"

        updated["name"] = "Package Button 1.1"
        write_json(source, updated)
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        write_json(package / "manifest.json", {"id": "button-pack", "name": "Button Pack", "version": "1.1.0", "type": "data", "checksums": {"modules/button.json": checksum}})
        assert manager.install(package)["updated"]

        write_json(package / "manifest.json", {"id": "button-pack", "name": "Button Pack", "version": "0.9.0", "type": "data", "checksums": {"modules/button.json": checksum}})
        try:
            manager.install(package)
            raise AssertionError("downgrade should fail")
        except ValueError as exc:
            assert "降级" in str(exc)
        assert manager.uninstall("button-pack")["uninstalled"]
        assert json.loads(target.read_text(encoding="utf-8"))["name"] == "Original Button"

        plugin_package = temp / "plugin_pack"
        plugin = {"id": "safe-exporter", "name": "Safe Exporter", "version": "1.0.0", "capabilities": ["export"]}
        write_json(plugin_package / "plugin.json", plugin)
        write_json(plugin_package / "manifest.json", {"id": "safe-exporter", "name": "Safe Exporter", "version": "1.0.0", "type": "plugin"})
        manager.install(plugin_package)
        assert manager.set_enabled("safe-exporter", False)["enabled"] is False
        assert manager.set_enabled("safe-exporter", True)["enabled"] is True
        discovered = discover_plugins(temp / "plugins", {"safe-exporter": True})
        assert len(discovered) == 1 and discovered[0]["status"] == "ready"

        plugin["capabilities"] = ["shell"]
        write_json(temp / "plugins/safe-exporter/plugin.json", plugin)
        assert discover_plugins(temp / "plugins")[0]["status"] == "invalid"

        bad_package = temp / "bad_hash"
        write_json(bad_package / "modules/button.json", updated)
        write_json(bad_package / "manifest.json", {"id": "bad-hash", "name": "Bad", "version": "1.0.0", "type": "data", "checksums": {"modules/button.json": "0" * 64}})
        try:
            manager.install(bad_package)
            raise AssertionError("bad checksum should fail")
        except ValueError as exc:
            assert "哈希" in str(exc)
    print("P4 ecosystem test passed")


if __name__ == "__main__":
    main()
