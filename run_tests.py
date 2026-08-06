from pathlib import Path
import py_compile
import runpy
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    source_dirs = ["app", "core", "ecosystem", "export", "integrations", "versioning", "plugins", "collaboration", "quality", "release", "backup", "diagnostics", "utils", "tests"]
    sources = [p for name in source_dirs for p in (ROOT / name).glob("*.py")]
    for path in sorted(sources):
        py_compile.compile(str(path), doraise=True)
    tests = [
        "tests/p0_smoke_test.py",
        "tests/p0_risk_test.py",
        "tests/p0_trust_test.py",
        "tests/p1_project_scan_test.py",
        "tests/p2_enhancement_test.py",
        "tests/p2_recommendation_test.py",
        "tests/p3_productization_test.py",
        "tests/p3_extension_test.py",
        "tests/p4_platform_test.py",
        "tests/p4_ecosystem_test.py",
        "tests/p5_product_test.py",
        "tests/p6_release_test.py",
    ]
    for test in tests:
        print(f"RUN {test}")
        runpy.run_path(str(ROOT / test), run_name="__main__")
    print(f"Regression passed: compiled={len(sources)} tests={len(tests)}")


if __name__ == "__main__":
    main()
