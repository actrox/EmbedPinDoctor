from pathlib import Path
import shutil
import json

ROOT = Path(__file__).resolve().parents[1]


def build_release():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    target = ROOT / "output" / "releases" / f"EmbedPinDoctor_{version}"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    folders = ["app", "core", "data", "export", "integrations", "versioning", "plugins", "collaboration", "quality", "release", "backup", "diagnostics", "utils", "web", "docs", "examples", "rule_packs"]
    for folder in folders:
        src = ROOT / folder
        if src.exists():
            shutil.copytree(src, target / folder)
    for file_name in ["README.md", "VERSION", "CHANGELOG.md", "launcher.py", "start_embedpindoctor.py", "start_embedpindoctor.bat", "requirements.txt"]:
        src = ROOT / file_name
        if src.exists():
            shutil.copyfile(src, target / file_name)
    manifest = {"name": "EmbedPinDoctor", "version": version, "entry": "launcher.py"}
    (target / "release_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(target), "version": version}


if __name__ == "__main__":
    result = build_release()
    print(result)
