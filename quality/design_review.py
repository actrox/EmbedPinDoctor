def build_design_review(chip, modules, allocation, risks):
    score = 100
    for risk in risks:
        if risk["level"] == "错误":
            score -= 25
        elif risk["level"] == "警告":
            score -= 10
        else:
            score -= 2
    score = max(0, score)
    categories = {"电气兼容": [], "调试下载": [], "启动时序": [], "文档一致性": []}
    for risk in risks:
        code = risk.get("code")
        if code == "voltage_mismatch": categories["电气兼容"].append(risk)
        elif code == "debug_pin": categories["调试下载"].append(risk)
        elif code == "boot_pin": categories["启动时序"].append(risk)
        else: categories["文档一致性"].append(risk)
    return {"score": score, "chip": chip["name"], "module_count": len(modules), "allocation_count": len(allocation), "categories": categories}


def render_design_review_markdown(review):
    lines = [f"# 硬件设计审查报告", "", f"- 芯片：{review['chip']}", f"- 模块数量：{review['module_count']}", f"- 接线数量：{review['allocation_count']}", f"- 设计评分：{review['score']}", ""]
    for name, risks in review["categories"].items():
        lines.append(f"## {name}")
        if not risks:
            lines.append("- 未发现明显问题。")
        for risk in risks:
            lines.append(f"- [{risk['level']}] {risk['message']}")
            if risk.get("suggestion"):
                lines.append(f"  - 建议：{risk['suggestion']}")
        lines.append("")
    return "\n".join(lines)
