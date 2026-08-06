from pathlib import Path

from core.loader import DataLoadError, load_chip, load_module


def audit_data(data_dir):
    data_dir = Path(data_dir)
    errors = []
    warnings = []
    chips = []
    modules = []

    for path in sorted((data_dir / "chips").glob("*.json")):
        try:
            chip = load_chip(path)
            chips.append(chip)
            if not chip.get("verified"):
                warnings.append({"code": "review_required", "file": str(path), "message": f"{chip['id']} 尚未人工签字复核"})
            if not chip.get("datasheet_url", "").startswith("https://"):
                errors.append({"code": "invalid_source", "file": str(path), "message": "datasheet_url 必须使用 HTTPS"})
        except (DataLoadError, ValueError) as exc:
            errors.append({"code": "schema_invalid", "file": str(path), "message": str(exc)})

    for path in sorted((data_dir / "modules").glob("*.json")):
        try:
            modules.append(load_module(path))
        except (DataLoadError, ValueError) as exc:
            errors.append({"code": "schema_invalid", "file": str(path), "message": str(exc)})

    supported_functions = {function for chip in chips for pin in chip["pins"] for function in pin["functions"]}
    for module in modules:
        for requirement in module["requirements"]:
            if requirement["function"] not in supported_functions:
                errors.append({
                    "code": "unsupported_function", "file": module["id"],
                    "message": f"没有任何芯片支持 {requirement['function']}",
                })

    return {
        "ok": not errors,
        "chip_count": len(chips),
        "module_count": len(modules),
        "verified_chip_count": sum(1 for chip in chips if chip.get("verified")),
        "errors": errors,
        "warnings": warnings,
    }


def render_audit_markdown(audit):
    lines = [
        "# 硬件数据审计报告", "",
        f"- 结果：{'通过' if audit['ok'] else '失败'}",
        f"- 芯片：{audit['chip_count']}",
        f"- 模块：{audit['module_count']}",
        f"- 已人工签字芯片：{audit['verified_chip_count']}", "",
        "## 错误", "",
    ]
    lines.extend([f"- `{item['code']}` {item['file']}：{item['message']}" for item in audit["errors"]] or ["- 无"])
    lines.extend(["", "## 待办", ""])
    lines.extend([f"- `{item['code']}` {item['file']}：{item['message']}" for item in audit["warnings"]] or ["- 无"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = audit_data(root / "data")
    print(render_audit_markdown(result))
    raise SystemExit(0 if result["ok"] else 1)
