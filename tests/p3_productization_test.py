import json
import socket
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.project_store import ProjectStore
from diagnostics.collector import create_diagnostics
from launcher import _free_port
from release.validate_release import validate_release
from versioning.project_migration import CURRENT_PROJECT_SCHEMA, migrate_project
import app.web_app as web_app


def main():
    legacy, migrations = migrate_project({"project_name": "old", "chip": "esp32", "modules": ["button"]})
    assert legacy["schema_version"] == CURRENT_PROJECT_SCHEMA
    assert legacy["chip_id"] == "esp32" and legacy["module_ids"] == ["button"]
    assert len(migrations) == 2

    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        store = ProjectStore(temp / "projects", history_limit=3)
        first = {"project_name": "daily", "chip_id": "esp32", "module_ids": ["button"], "notes": "v1"}
        second = {**first, "notes": "v2"}
        path, _ = store.save(first)
        store.save(second)
        assert json.loads(path.read_text(encoding="utf-8"))["notes"] == "v2"
        restored, _ = store.undo("daily")
        assert restored["notes"] == "v1" and store.history("daily")["redo"] == 1
        restored, _ = store.redo("daily")
        assert restored["notes"] == "v2"
        assert not list(path.parent.glob("*.tmp"))

        (temp / "VERSION").write_text("0.1.0-test", encoding="utf-8")
        (temp / "projects").mkdir(exist_ok=True)
        (temp / "projects" / "private.json").write_text('{"secret": true}', encoding="utf-8")
        diagnostics = create_diagnostics(temp, temp / "diagnostics")
        with zipfile.ZipFile(diagnostics["path"]) as archive:
            assert "projects/private.json" not in archive.namelist()
        assert diagnostics["includes_project_data"] is False

        web_app.PROJECTS_DIR = temp / "http-projects"
        web_app.PROJECT_STORE = ProjectStore(web_app.PROJECTS_DIR)
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.EmbedPinDoctorHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            assert json.loads(urlopen(f"{base_url}/api/version", timeout=2).read())["version"]
            for note in ["first", "second"]:
                body = json.dumps({"schema_version": 2, "project_name": "http", "chip_id": "esp32", "module_ids": ["button"], "notes": note}).encode()
                response = urlopen(Request(f"{base_url}/api/save", data=body, headers={"Content-Type": "application/json"}), timeout=2)
                assert json.loads(response.read())["saved"]
            body = json.dumps({"project_name": "http"}).encode()
            response = urlopen(Request(f"{base_url}/api/project/undo", data=body, headers={"Content-Type": "application/json"}), timeout=2)
            result = json.loads(response.read())
            assert result["project"]["notes"] == "first" and result["history"]["redo"] == 1
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        assert _free_port(port, 2) == port + 1

    assert "EmbedPinDoctor.spec" in (ROOT / "build_windows.bat").read_text(encoding="utf-8")
    release_fixture = ROOT / "output" / "releases" / f"EmbedPinDoctor_{(ROOT / 'VERSION').read_text(encoding='utf-8').strip()}"
    if release_fixture.exists():
        assert validate_release(release_fixture)["valid"]
    print("P3 productization test passed")


if __name__ == "__main__":
    main()
