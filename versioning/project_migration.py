from copy import deepcopy


CURRENT_PROJECT_SCHEMA = 2


def migrate_project(project):
    """Return a current project document and the applied migration labels."""
    if not isinstance(project, dict):
        raise ValueError("项目文件必须是 JSON 对象")
    data = deepcopy(project)
    migrations = []
    version = int(data.get("schema_version", 0) or 0)

    if version < 1:
        if "chip_id" not in data and "chip" in data:
            data["chip_id"] = data.pop("chip")
        if "module_ids" not in data and "modules" in data:
            data["module_ids"] = data.pop("modules")
        migrations.append("legacy-fields-to-v1")
        version = 1

    if version < 2:
        data.setdefault("project_path", "")
        data.setdefault("notes", "")
        data.setdefault("strategy", "recommended")
        data.setdefault("locked_pins", {})
        data.setdefault("allocation", [])
        migrations.append("project-settings-to-v2")
        version = 2

    if version > CURRENT_PROJECT_SCHEMA:
        raise ValueError(f"项目版本 {version} 高于当前支持版本 {CURRENT_PROJECT_SCHEMA}")
    if not isinstance(data.get("module_ids", []), list):
        raise ValueError("module_ids 必须是数组")
    if not isinstance(data.get("locked_pins", {}), dict):
        raise ValueError("locked_pins 必须是对象")
    if not isinstance(data.get("allocation", []), list):
        raise ValueError("allocation 必须是数组")
    data["schema_version"] = CURRENT_PROJECT_SCHEMA
    return data, migrations
