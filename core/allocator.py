MAX_SEARCH_NODES = 50000


def _signal_key(module_id, module_pin):
    return f"{module_id}:{module_pin}"


def _normalize_assignment_map(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return {str(key): str(pin) for key, pin in value.items() if pin and pin != "未分配"}
    result = {}
    for item in value:
        pin = item.get("chip_pin")
        if pin and pin != "未分配":
            result[_signal_key(item["module_id"], item["module_pin"])] = pin
    return result


def _pin_supports(pin, function):
    return function in pin.get("functions", [])


def _direction_allowed(pin, requirement):
    direction = requirement.get("direction", "bidirectional")
    tags = set(pin.get("tags", []))
    return not (direction in {"output", "bidirectional"} and "input_only" in tags)


def _electrical_allowed(pin, requirement):
    tags = set(pin.get("tags", []))
    return not requirement.get("requires_five_v_tolerant") or "five_v_tolerant" in tags


def _risk_penalty(pin):
    tags = set(pin.get("tags", []))
    return (100 if "debug" in tags else 0) + (80 if "boot" in tags else 0) + (20 if "default_high" in tags else 0)


def _score_pin(pin, requirement):
    score = 100 - _risk_penalty(pin)
    if any(function in pin.get("functions", []) for function in requirement.get("preferred_functions", [])):
        score += 30
    if requirement.get("avoid_default_high") and "default_high" in pin.get("tags", []):
        score -= 60
    if requirement.get("direction") == "input" and "input_only" in pin.get("tags", []):
        score += 5
    return score


def _candidate_reasons(pin, requirement, locked=False, kept=False):
    reasons = [f"支持 {requirement['function']}"]
    tags = set(pin.get("tags", []))
    if not tags.intersection({"boot", "debug", "default_high"}):
        reasons.append("避开启动、调试和默认高电平风险脚")
    if requirement.get("preferred_functions") and any(item in pin.get("functions", []) for item in requirement["preferred_functions"]):
        reasons.append("命中模块首选复用功能")
    if locked:
        reasons.append("按用户锁定保留")
    elif kept:
        reasons.append("保持现有接线，减少改板范围")
    if "input_only" in tags and requirement.get("direction") == "input":
        reasons.append("输入信号优先使用输入专用脚")
    return reasons


def _find_candidates(chip, requirement, used_pins, allowed_pin=None, forbidden=None, key=None, preferred_pin=None):
    candidates = []
    forbidden = forbidden or set()
    for pin in chip["pins"]:
        if pin["name"] in used_pins or (allowed_pin and pin["name"] != allowed_pin):
            continue
        if key and (key, pin["name"]) in forbidden:
            continue
        if not _pin_supports(pin, requirement["function"]):
            continue
        if not _direction_allowed(pin, requirement) or not _electrical_allowed(pin, requirement):
            continue
        candidates.append(pin)
    return sorted(candidates, key=lambda pin: (pin["name"] != preferred_pin, -_score_pin(pin, requirement), pin["name"]))


def _requirements(chip, modules, locked):
    items = []
    for module_index, module in enumerate(modules):
        for requirement_index, requirement in enumerate(module["requirements"]):
            key = _signal_key(module["id"], requirement["module_pin"])
            candidate_count = sum(
                1 for pin in chip["pins"]
                if (not locked.get(key) or pin["name"] == locked[key])
                and _pin_supports(pin, requirement["function"])
                and _direction_allowed(pin, requirement)
                and _electrical_allowed(pin, requirement)
            )
            strength = (100 if requirement["function"] not in {"GPIO", "EXTI"} else 0) + (30 if requirement.get("preferred_functions") else 0) + (20 if requirement.get("avoid_default_high") else 0)
            items.append({"module": module, "requirement": requirement, "module_index": module_index, "requirement_index": requirement_index, "candidate_count": candidate_count, "strength": strength, "key": key})
    return sorted(items, key=lambda item: (item["candidate_count"], -item["strength"], item["module_index"], item["requirement_index"]))


def _allocation_item(item, pin=None, locked=False, kept=False):
    module, requirement = item["module"], item["requirement"]
    if pin is None:
        note = "锁定引脚不满足功能、电气或占用约束" if locked else "没有找到满足全部约束的可用引脚"
        return {"module_id": module["id"], "module_name": module["name"], "module_pin": requirement["module_pin"], "chip_pin": "未分配", "function": requirement["function"], "direction": requirement.get("direction", "bidirectional"), "score": None, "note": note, "locked": locked, "kept_existing": False, "reasons": [note]}
    reasons = _candidate_reasons(pin, requirement, locked, kept)
    return {"module_id": module["id"], "module_name": module["name"], "module_pin": requirement["module_pin"], "chip_pin": pin["name"], "function": requirement["function"], "direction": requirement.get("direction", "bidirectional"), "score": _score_pin(pin, requirement), "note": "；".join(reasons), "locked": locked, "kept_existing": kept, "reasons": reasons}


def allocate_project(chip, modules, locked_pins=None, preferred_allocation=None, strategy="recommended", forbidden=None, return_metadata=False):
    """Return a deterministic, globally feasible allocation.

    ``locked_pins`` maps ``module_id:module_pin`` to a mandatory MCU pin.
    ``preferred_allocation`` is used by ``min_change`` strategy to preserve an
    existing board layout whenever it does not reduce assignment completeness.
    """
    locked = _normalize_assignment_map(locked_pins)
    preferred = _normalize_assignment_map(preferred_allocation)
    forbidden = set(forbidden or set())
    items = _requirements(chip, modules, locked)
    best = {"objective": (-1, -1, -1), "rows": []}
    nodes, memo, limit_reached = 0, {}, False

    def search(index, used_pins, shared_buses, rows, assigned, stability, score):
        nonlocal nodes, limit_reached
        nodes += 1
        if nodes > MAX_SEARCH_NODES:
            limit_reached = True
            return
        if assigned + len(items) - index < best["objective"][0]:
            return
        state_key = (index, tuple(sorted(used_pins)), tuple(sorted((key, pin["name"]) for key, pin in shared_buses.items())))
        objective = (assigned, stability if strategy == "min_change" else 0, score)
        if memo.get(state_key, (-1, -1, -1)) >= objective:
            return
        memo[state_key] = objective
        if index == len(items):
            if objective > best["objective"]:
                best.update(objective=objective, rows=list(rows))
            return

        item, requirement, key = items[index], items[index]["requirement"], items[index]["key"]
        locked_pin, preferred_pin = locked.get(key), preferred.get(key)
        bus_key = requirement.get("bus_key") if requirement.get("share_bus") else None
        if bus_key and bus_key in shared_buses:
            pin = shared_buses[bus_key]
            compatible = (not locked_pin or locked_pin == pin["name"]) and (key, pin["name"]) not in forbidden and _pin_supports(pin, requirement["function"]) and _direction_allowed(pin, requirement)
            if compatible:
                kept = pin["name"] == preferred_pin
                row = _allocation_item(item, pin, bool(locked_pin), kept)
                search(index + 1, used_pins, shared_buses, rows + [(item, row)], assigned + 1, stability + int(kept), score + row["score"])
            else:
                search(index + 1, used_pins, shared_buses, rows + [(item, _allocation_item(item, None, bool(locked_pin)))], assigned, stability, score)
            return

        candidates = _find_candidates(chip, requirement, used_pins, locked_pin, forbidden, key, preferred_pin if strategy == "min_change" else None)
        for pin in candidates:
            kept = pin["name"] == preferred_pin
            row = _allocation_item(item, pin, bool(locked_pin), kept)
            next_shared = dict(shared_buses)
            if bus_key:
                next_shared[bus_key] = pin
            search(index + 1, used_pins | {pin["name"]}, next_shared, rows + [(item, row)], assigned + 1, stability + int(kept), score + row["score"])
        search(index + 1, used_pins, shared_buses, rows + [(item, _allocation_item(item, None, bool(locked_pin)))], assigned, stability, score)

    search(0, set(), {}, [], 0, 0, 0)
    ordered = sorted(best["rows"], key=lambda pair: (pair[0]["module_index"], pair[0]["requirement_index"]))
    allocation = [row for _, row in ordered]
    assigned_count = sum(row["chip_pin"] != "未分配" for row in allocation)
    metadata = {
        "status": "incomplete" if limit_reached else ("optimal" if assigned_count == len(items) else "impossible"),
        "nodes_searched": nodes,
        "limit_reached": limit_reached,
        "assigned_count": assigned_count,
        "total_count": len(items),
    }
    return (allocation, metadata) if return_metadata else allocation


def allocation_score(allocation):
    values = [item["score"] for item in allocation if item.get("score") is not None]
    return round(sum(values) / len(values), 2) if values else 0


def _allocation_signature(allocation):
    return tuple((item["module_id"], item["module_pin"], item["chip_pin"]) for item in allocation)


def _changes_from(primary, alternative):
    old = {(item["module_id"], item["module_pin"]): item["chip_pin"] for item in primary}
    return [{"module_id": item["module_id"], "module_pin": item["module_pin"], "from": old.get((item["module_id"], item["module_pin"])), "to": item["chip_pin"]} for item in alternative if old.get((item["module_id"], item["module_pin"])) != item["chip_pin"]]


def allocate_alternatives(chip, modules, count=3, locked_pins=None, preferred_allocation=None, strategy="recommended"):
    count = max(1, min(int(count), 5))
    primary = allocate_project(chip, modules, locked_pins, preferred_allocation, strategy)
    plans = [{"name": "推荐方案", "score": allocation_score(primary), "allocation": primary, "changes": [], "change_count": 0}]
    seen = {_allocation_signature(primary)}
    locked = _normalize_assignment_map(locked_pins)
    for item in primary:
        if len(plans) >= count or item["chip_pin"] == "未分配":
            break
        key = _signal_key(item["module_id"], item["module_pin"])
        if key in locked:
            continue
        forbidden = {(key, item["chip_pin"])}
        alternative = allocate_project(chip, modules, locked, preferred_allocation, strategy, forbidden)
        signature = _allocation_signature(alternative)
        if signature in seen or sum(row["chip_pin"] != "未分配" for row in alternative) < sum(row["chip_pin"] != "未分配" for row in primary):
            continue
        seen.add(signature)
        changes = _changes_from(primary, alternative)
        plans.append({"name": f"备选方案 {len(plans)}", "score": allocation_score(alternative), "allocation": alternative, "changes": changes, "change_count": len(changes)})
    return plans
