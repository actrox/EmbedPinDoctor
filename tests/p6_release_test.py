from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diagnostics.collector import create_diagnostics
from release.build_release import build_release
from app.web_app import build_project


def main():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip().startswith("0.1.0")
    assert (ROOT / "CHANGELOG.md").exists()
    examples = sorted((ROOT / "examples").glob("*.json"))
    assert len(examples) >= 3
    for example in examples:
        payload = __import__("json").loads(example.read_text(encoding="utf-8"))
        chip, modules, allocation, risks = build_project(payload)
        assert chip and modules and allocation
    diagnostics = create_diagnostics(ROOT, ROOT / "output/diagnostics")
    assert Path(diagnostics["path"]).exists() and diagnostics["size"] > 0
    release = build_release()
    release_path = Path(release["path"])
    assert release_path.exists()
    assert (release_path / "release_manifest.json").exists()
    assert (ROOT / "launcher.py").exists()
    print("P6 release test passed")
    print(f"examples={len(examples)} diagnostics={diagnostics['size']} release={release['path']}")


if __name__ == "__main__":
    main()
