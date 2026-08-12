"""
SVG 芯片引脚图生成与风险可视化模块。

提供 LQFP 风格四边引脚封装图的生成能力，支持：
- 按引脚列表顺序自动均分四个边
- 显示引脚分配信息（模块名_引脚名）
- 按风险等级（错误/警告/提示）高亮引脚
- Hover 显示详细信息 tooltip
"""

import math
from html import escape


def allocate_pin_edges(chip):
    """
    把芯片引脚按列表顺序均分到四个边（左/下/右/上）。

    策略：
    - 取 len(pins) 数 N
    - per_side = ceil(N / 4)
    - 左: pins[0:per_side]
    - 下: pins[per_side:2*per_side]
    - 右: pins[2*per_side:3*per_side]
    - 上: pins[3*per_side:4*per_side]

    参数:
        chip: 芯片 JSON 对象，包含 pins 数组

    返回:
        dict: {"left": [...], "bottom": [...], "right": [...], "top": [...]}
              每个元素是 pin 对象本身（不是名字）。
    """
    pins = chip.get("pins", [])
    n = len(pins)
    per_side = math.ceil(n / 4) if n > 0 else 0

    return {
        "left": pins[0:per_side],
        "bottom": pins[per_side:2 * per_side],
        "right": pins[2 * per_side:3 * per_side],
        "top": pins[3 * per_side:4 * per_side],
    }


def risk_pin_map(risks):
    """
    把风险数组整理成 {pin_name: risk_level} 的映射。

    每个引脚对应最高级别的风险：错误 > 警告 > 提示 > None。

    参数:
        risks: checker 返回的风险数组，每个 risk 可能包含 pin 字段

    返回:
        dict: {引脚名: 风险等级字符串}，风险等级为 "错误"/"警告"/"提示"/None
    """
    level_priority = {"错误": 3, "警告": 2, "提示": 1}
    result = {}

    for risk in risks or []:
        pin_name = risk.get("pin")
        if not pin_name:
            continue
        level = risk.get("level")
        if level not in level_priority:
            continue
        current = result.get(pin_name)
        if current is None or level_priority[level] > level_priority.get(current, 0):
            result[pin_name] = level

    return result


def _risk_colors(level):
    """
    根据风险等级返回对应的边框色和背景色。

    返回: (border_color, background_color)
    """
    color_map = {
        "错误": ("#dc2626", "#fee2e2"),
        "警告": ("#d97706", "#fef3c7"),
        "提示": ("#2563eb", "#dbeafe"),
    }
    if level in color_map:
        return color_map[level]
    return ("#6b7280", None)


def _allocation_map(allocation):
    """
    把分配数组整理成 {chip_pin: [allocation_items]} 的映射，
    一个引脚可能对应多个分配项（共享总线）。
    """
    result = {}
    for item in allocation or []:
        pin = item.get("chip_pin")
        if not pin or pin == "未分配":
            continue
        if pin not in result:
            result[pin] = []
        result[pin].append(item)
    return result


def generate_chip_svg(chip, allocation=None, risks=None):
    """
    生成一个完整的 SVG 芯片封装图（LQFP 风格，四边引脚）。

    参数:
        chip: 芯片 JSON 对象（含 pins 数组，每个 pin 有 name, functions, tags 等）
        allocation: 可选，分配结果数组
        risks: 可选，checker 返回的风险数组

    返回:
        str: SVG 字符串
    """
    pins = chip.get("pins", [])
    n = len(pins)
    per_side = math.ceil(n / 4) if n > 0 else 0

    edges = allocate_pin_edges(chip)
    risk_map = risk_pin_map(risks)
    alloc_map = _allocation_map(allocation)

    TOTAL_W = 600
    CHIP_W = 400
    CHIP_X = (TOTAL_W - CHIP_W) // 2
    PIN_SPACING = 28
    PIN_LINE = 24
    LABEL_GAP = 4

    max_pins_per_side = max(
        len(edges["left"]), len(edges["bottom"]),
        len(edges["right"]), len(edges["top"])
    )
    max_pins_per_side = max(max_pins_per_side, 1)

    chip_h = max_pins_per_side * PIN_SPACING + 60
    CHIP_H = max(chip_h, 200)
    CHIP_Y = 80

    TOTAL_H = CHIP_Y + CHIP_H + 80

    svg_parts = []

    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TOTAL_W} {TOTAL_H}" '
        f'width="{TOTAL_W}" height="{TOTAL_H}" font-family="system-ui, -apple-system, sans-serif">'
    )

    svg_parts.append("""<style>
  .chip-body { fill: #f8fafc; stroke: #334155; stroke-width: 2; }
  .chip-name { fill: #1e293b; font-size: 20px; font-weight: bold; text-anchor: middle; }
  .chip-subtitle { fill: #64748b; font-size: 12px; text-anchor: middle; }
  .pin-line { stroke: #475569; stroke-width: 2; }
  .pin-label { fill: #1e293b; font-size: 11px; font-weight: 600; }
  .alloc-label { fill: #059669; font-size: 10px; font-weight: 500; }
  .pin-box { cursor: pointer; transition: all 0.15s; }
  .pin-box:hover .pin-box-bg { filter: brightness(0.92); }
  .pin-box:hover .pin-line { stroke: #0f172a; stroke-width: 3; }
  .pin-box-error .pin-box-bg { stroke: #dc2626; stroke-width: 2.5; }
  .pin-box-warning .pin-box-bg { stroke: #d97706; stroke-width: 2; }
  .pin-box-info .pin-box-bg { stroke: #2563eb; stroke-width: 2; }
  .pin-bg-error { fill: #fee2e2; }
  .pin-bg-warning { fill: #fef3c7; }
  .pin-bg-info { fill: #dbeafe; }
  .pin-bg-normal { fill: #e2e8f0; }
  .legend-item { font-size: 11px; fill: #475569; }
  .legend-box { stroke-width: 1.5; }
</style>""")

    chip_name = chip.get("name", chip.get("id", "Unknown"))
    chip_id = chip.get("id", "")
    voltage = chip.get("voltage", "")

    svg_parts.append(
        f'<rect class="chip-body" x="{CHIP_X}" y="{CHIP_Y}" '
        f'width="{CHIP_W}" height="{CHIP_H}" rx="16" ry="16"/>'
    )
    svg_parts.append(
        f'<text class="chip-name" x="{CHIP_X + CHIP_W // 2}" y="{CHIP_Y + CHIP_H // 2 - 6}">'
        f'{escape(chip_name)}</text>'
    )
    subtitle_parts = []
    if chip_id:
        subtitle_parts.append(chip_id)
    if voltage:
        subtitle_parts.append(str(voltage))
    if subtitle_parts:
        svg_parts.append(
            f'<text class="chip-subtitle" x="{CHIP_X + CHIP_W // 2}" y="{CHIP_Y + CHIP_H // 2 + 16}">'
            f'{escape(" | ".join(subtitle_parts))}</text>'
        )

    svg_parts.append(
        f'<circle cx="{CHIP_X + 18}" cy="{CHIP_Y + CHIP_H // 2}" r="8" '
        f'fill="#334155" stroke="#1e293b" stroke-width="1.5"/>'
    )

    def _draw_pin(pin, side, index, count):
        """绘制单个引脚及其标签、分配信息。"""
        pin_name = pin.get("name", "")
        risk_level = risk_map.get(pin_name)
        alloc_items = alloc_map.get(pin_name, [])

        border_color, bg_color = _risk_colors(risk_level)
        risk_class = ""
        bg_class = "pin-bg-normal"
        if risk_level == "错误":
            risk_class = "pin-box-error"
            bg_class = "pin-bg-error"
        elif risk_level == "警告":
            risk_class = "pin-box-warning"
            bg_class = "pin-bg-warning"
        elif risk_level == "提示":
            risk_class = "pin-box-info"
            bg_class = "pin-bg-info"

        BOX_W = 62
        BOX_H = 22
        spacing = PIN_SPACING
        start_offset = (CHIP_H - (count - 1) * spacing) / 2

        if side == "left":
            cy = CHIP_Y + start_offset + index * spacing
            line_x1 = CHIP_X
            line_x2 = CHIP_X - PIN_LINE
            box_x = line_x2 - BOX_W
            box_y = cy - BOX_H / 2
            label_x = box_x - LABEL_GAP
            label_anchor = "end"
            text_dx = -4
        elif side == "right":
            cy = CHIP_Y + start_offset + index * spacing
            line_x1 = CHIP_X + CHIP_W
            line_x2 = CHIP_X + CHIP_W + PIN_LINE
            box_x = line_x2
            box_y = cy - BOX_H / 2
            label_x = box_x + BOX_W + LABEL_GAP
            label_anchor = "start"
            text_dx = 4
        elif side == "top":
            cx = CHIP_X + start_offset + index * spacing
            line_y1 = CHIP_Y
            line_y2 = CHIP_Y - PIN_LINE
            box_x = cx - BOX_W / 2
            box_y = line_y2 - BOX_H
            label_x = cx
            label_y = box_y - LABEL_GAP
            label_anchor = "middle"
        elif side == "bottom":
            cx = CHIP_X + start_offset + index * spacing
            line_y1 = CHIP_Y + CHIP_H
            line_y2 = CHIP_Y + CHIP_H + PIN_LINE
            box_x = cx - BOX_W / 2
            box_y = line_y2
            label_x = cx
            label_y = box_y + BOX_H + LABEL_GAP + 10
            label_anchor = "middle"

        box_style = f"fill:{bg_color};" if bg_color else ""
        rect_style = f' style="{box_style}"' if box_style else ""

        svg_parts.append(f'<g class="pin-box {risk_class}">')

        if side in ("left", "right"):
            svg_parts.append(
                f'<line class="pin-line" x1="{line_x1}" y1="{cy}" x2="{line_x2}" y2="{cy}"/>'
            )
            svg_parts.append(
                f'<rect class="pin-box-bg {bg_class}" x="{box_x}" y="{box_y}" '
                f'width="{BOX_W}" height="{BOX_H}" rx="3" ry="3" '
                f'stroke="{border_color}"{rect_style}/>'
            )
            svg_parts.append(
                f'<text class="pin-label" x="{box_x + BOX_W / 2}" y="{box_y + BOX_H / 2 + 4}" '
                f'text-anchor="middle">{escape(pin_name)}</text>'
            )
            if alloc_items:
                for ai, alloc in enumerate(alloc_items[:2]):
                    mod_name = alloc.get("module_name", "")
                    mod_pin = alloc.get("module_pin", "")
                    label_text = f"{mod_name}_{mod_pin}" if mod_name else mod_pin
                    dy = 12 + ai * 11
                    svg_parts.append(
                        f'<text class="alloc-label" x="{label_x}" y="{cy + dy - BOX_H / 2}" '
                        f'text-anchor="{label_anchor}">{escape(label_text)}</text>'
                    )
        else:
            svg_parts.append(
                f'<line class="pin-line" x1="{cx}" y1="{line_y1}" x2="{cx}" y2="{line_y2}"/>'
            )
            svg_parts.append(
                f'<rect class="pin-box-bg {bg_class}" x="{box_x}" y="{box_y}" '
                f'width="{BOX_W}" height="{BOX_H}" rx="3" ry="3" '
                f'stroke="{border_color}"{rect_style}/>'
            )
            svg_parts.append(
                f'<text class="pin-label" x="{box_x + BOX_W / 2}" y="{box_y + BOX_H / 2 + 4}" '
                f'text-anchor="middle">{escape(pin_name)}</text>'
            )
            if alloc_items:
                for ai, alloc in enumerate(alloc_items[:2]):
                    mod_name = alloc.get("module_name", "")
                    mod_pin = alloc.get("module_pin", "")
                    label_text = f"{mod_name}_{mod_pin}" if mod_name else mod_pin
                    dy = (ai - 0.5) * 12
                    if side == "top":
                        ty = label_y + dy
                    else:
                        ty = label_y + dy
                    svg_parts.append(
                        f'<text class="alloc-label" x="{label_x}" y="{ty}" '
                        f'text-anchor="{label_anchor}">{escape(label_text)}</text>'
                    )

        title_parts = [f"引脚: {pin_name}"]
        funcs = pin.get("functions", [])
        if funcs:
            title_parts.append(f"功能: {', '.join(funcs)}")
        tags = pin.get("tags", [])
        if tags:
            title_parts.append(f"标签: {', '.join(tags)}")
        note = pin.get("note")
        if note:
            title_parts.append(f"备注: {note}")
        if risk_level:
            title_parts.append(f"风险: {risk_level}")
        for alloc in alloc_items:
            mod_name = alloc.get("module_name", "")
            mod_pin = alloc.get("module_pin", "")
            func = alloc.get("function", "")
            title_parts.append(f"分配: {mod_name} {mod_pin} ({func})")
        title_text = escape("\n".join(title_parts))
        svg_parts.append(f"<title>{title_text}</title>")

        svg_parts.append("</g>")

    for i, pin in enumerate(edges["left"]):
        _draw_pin(pin, "left", i, len(edges["left"]))
    for i, pin in enumerate(edges["right"]):
        _draw_pin(pin, "right", i, len(edges["right"]))
    for i, pin in enumerate(edges["top"]):
        _draw_pin(pin, "top", i, len(edges["top"]))
    for i, pin in enumerate(edges["bottom"]):
        _draw_pin(pin, "bottom", i, len(edges["bottom"]))

    legend_y = TOTAL_H - 28
    legend_items = [
        ("错误", "#dc2626", "#fee2e2"),
        ("警告", "#d97706", "#fef3c7"),
        ("提示", "#2563eb", "#dbeafe"),
        ("正常", "#6b7280", "#e2e8f0"),
    ]
    lx = 20
    for label, border, bg in legend_items:
        svg_parts.append(
            f'<rect class="legend-box" x="{lx}" y="{legend_y}" width="16" height="12" '
            f'rx="2" ry="2" fill="{bg}" stroke="{border}"/>'
        )
        svg_parts.append(
            f'<text class="legend-item" x="{lx + 22}" y="{legend_y + 10}">{escape(label)}</text>'
        )
        lx += 80

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
