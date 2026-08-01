import json
from pathlib import Path


class DataLoadError(ValueError):
    pass


def _read_json(path):
    if not path.exists():
        raise DataLoadError(f"数据文件不存在: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_chip(path):
    chip = _read_json(Path(path))
    required = ["id", "name", "voltage", "pins"]
    for key in required:
        if key not in chip:
            raise DataLoadError(f"芯片数据缺少字段: {key}")
    if not isinstance(chip["pins"], list) or not chip["pins"]:
        raise DataLoadError("芯片 pins 必须是非空列表")
    return chip


def load_module(path):
    module = _read_json(Path(path))
    required = ["id", "name", "voltage", "requirements"]
    for key in required:
        if key not in module:
            raise DataLoadError(f"模块数据缺少字段: {key}")
    return module


def load_modules(module_dir, module_ids):
    module_dir = Path(module_dir)
    return [load_module(module_dir / f"{module_id}.json") for module_id in module_ids]
