def compare_allocations(old_allocation, new_allocation):
    old_map = {(i["module_id"], i["module_pin"]): i.get("chip_pin") for i in old_allocation}
    new_map = {(i["module_id"], i["module_pin"]): i.get("chip_pin") for i in new_allocation}
    changes = []
    for key in sorted(set(old_map) | set(new_map)):
        if old_map.get(key) != new_map.get(key):
            changes.append({"module_id": key[0], "module_pin": key[1], "old_pin": old_map.get(key), "new_pin": new_map.get(key)})
    return changes
