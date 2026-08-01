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


def allocate_project(chip, modules):
    allocation = []
    used_pins = set()
    shared_buses = {}

    for module in modules:
        for requirement in module["requirements"]:
            bus_key = requirement.get("bus_key")
            if bus_key and requirement.get("share_bus") and bus_key in shared_buses:
                assigned_pin = shared_buses[bus_key]
                allocation.append({
                    "module_id": module["id"],
                    "module_name": module["name"],
                    "module_pin": requirement["module_pin"],
                    "chip_pin": assigned_pin["name"],
                    "function": requirement["function"],
                    "score": _score_pin(assigned_pin, requirement),
                    "note": requirement.get("note", "共用总线"),
                })
                continue

            candidates = _find_candidates(chip, requirement, used_pins)
            if not candidates:
                allocation.append({
                    "module_id": module["id"],
                    "module_name": module["name"],
                    "module_pin": requirement["module_pin"],
                    "chip_pin": "未分配",
                    "function": requirement["function"],
                    "score": None,
                    "note": "没有找到可用引脚",
                })
                continue

            selected = candidates[0]
            used_pins.add(selected["name"])
            if bus_key and requirement.get("share_bus"):
                shared_buses[bus_key] = selected

            allocation.append({
                "module_id": module["id"],
                "module_name": module["name"],
                "module_pin": requirement["module_pin"],
                "chip_pin": selected["name"],
                "function": requirement["function"],
                "score": _score_pin(selected, requirement),
                "note": requirement.get("note", selected.get("note", "")),
            })
    return allocation
