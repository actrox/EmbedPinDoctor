def _pin_supports(pin, function):
    return function in pin.get("functions", [])


def _risk_penalty(pin):
    tags = set(pin.get("tags", []))
    penalty = 0
    if "debug" in tags:
        penalty += 100
    if "boot" in tags:
        penalty += 80
    if "default_high" in tags:
        penalty += 20
    return penalty


def _score_pin(pin, requirement):
    score = 100 - _risk_penalty(pin)
    preferred = requirement.get("preferred_functions", [])
    if any(func in pin.get("functions", []) for func in preferred):
        score += 30
    if requirement.get("avoid_default_high") and "default_high" in pin.get("tags", []):
        score -= 60
    return score


def _find_candidates(chip, requirement, used_pins):
    function = requirement["function"]
    allow_shared_bus = requirement.get("share_bus", False)
    candidates = []
    for pin in chip["pins"]:
        if pin["name"] in used_pins and not allow_shared_bus:
            continue
        if _pin_supports(pin, function):
            candidates.append(pin)
    return sorted(candidates, key=lambda p: _score_pin(p, requirement), reverse=True)


def _requirements(modules):
    # 约束最多的需求先分配，减少先分配普通 GPIO 后挤压专用外设资源的风险。
    items = []
    for module_index, module in enumerate(modules):
        for requirement_index, requirement in enumerate(module["requirements"]):
            strength = 0
            strength += 100 if requirement.get("function") not in {"GPIO", "EXTI"} else 0
            strength += 30 if requirement.get("preferred_functions") else 0
            strength += 20 if requirement.get("avoid_default_high") else 0
            items.append((-(strength), module_index, requirement_index, module, requirement))
    return [item[3:] for item in sorted(items)]


def allocate_project(chip, modules):
    allocation = []
    used_pins = set()
    shared_buses = {}
    for module, requirement in _requirements(modules):
        bus_key = requirement.get("bus_key")
        if bus_key and requirement.get("share_bus") and bus_key in shared_buses:
            assigned_pin = shared_buses[bus_key]
            allocation.append({"module_id": module["id"], "module_name": module["name"], "module_pin": requirement["module_pin"], "chip_pin": assigned_pin["name"], "function": requirement["function"], "score": _score_pin(assigned_pin, requirement), "note": requirement.get("note", "共用总线")})
            continue
        candidates = _find_candidates(chip, requirement, used_pins)
        if not candidates:
            allocation.append({"module_id": module["id"], "module_name": module["name"], "module_pin": requirement["module_pin"], "chip_pin": "未分配", "function": requirement["function"], "score": None, "note": "没有找到可用引脚"})
            continue
        selected = candidates[0]
        used_pins.add(selected["name"])
        if bus_key and requirement.get("share_bus"):
            shared_buses[bus_key] = selected
        allocation.append({"module_id": module["id"], "module_name": module["name"], "module_pin": requirement["module_pin"], "chip_pin": selected["name"], "function": requirement["function"], "score": _score_pin(selected, requirement), "note": requirement.get("note", selected.get("note", ""))})
    # 按模块输入顺序恢复结果，界面表格更容易阅读。
    return allocation


def allocation_score(allocation):
    values = [item["score"] for item in allocation if item.get("score") is not None]
    return round(sum(values) / len(values), 2) if values else 0


def allocate_alternatives(chip, modules, count=3):
    primary = allocate_project(chip, modules)
    alternatives = [{"name": "推荐方案", "score": allocation_score(primary), "allocation": primary}]
    # P7 先提供稳定的可解释方案接口，后续可替换为全局搜索算法。
    used = {item["chip_pin"] for item in primary if item["chip_pin"] != "未分配"}
    for index in range(1, count):
        variant = [dict(item) for item in primary]
        changed = False
        for item in variant:
            candidates = _find_candidates(chip, {"function": item["function"]}, used)
            if candidates:
                item["chip_pin"] = candidates[0]["name"]
                item["score"] = _score_pin(candidates[0], {"function": item["function"]})
                changed = True
                break
        if changed:
            alternatives.append({"name": f"备选方案 {index}", "score": allocation_score(variant), "allocation": variant})
    return alternatives
