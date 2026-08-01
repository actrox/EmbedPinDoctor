import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.loader import load_chip, load_modules
from core.allocator import allocate_project
from core.checker import check_project
from export.markdown import render_markdown


def main():
    parser = argparse.ArgumentParser(description="EmbedPinDoctor P0 命令行原型")
    parser.add_argument("--chip", required=True, help="芯片 ID，例如 stm32f103c8t6")
    parser.add_argument("--modules", nargs="+", required=True, help="模块 ID 列表")
    parser.add_argument("--out", default="output/wiring_report.md", help="Markdown 导出路径")
    args = parser.parse_args()

    data_dir = PROJECT_ROOT / "data"
    chip = load_chip(data_dir / "chips" / f"{args.chip}.json")
    modules = load_modules(data_dir / "modules", args.modules)

    allocation = allocate_project(chip, modules)
    risks = check_project(chip, modules, allocation)
    markdown = render_markdown(chip, modules, allocation, risks)

    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    error_count = sum(1 for risk in risks if risk["level"] == "错误")
    warning_count = sum(1 for risk in risks if risk["level"] == "警告")
    tip_count = sum(1 for risk in risks if risk["level"] == "提示")

    print(f"芯片: {chip['name']}")
    print(f"模块数量: {len(modules)}")
    print(f"接线项: {len(allocation)}")
    print(f"风险: 错误 {error_count}, 警告 {warning_count}, 提示 {tip_count}")
    print(f"已导出: {out_path}")


if __name__ == "__main__":
    main()
