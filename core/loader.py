import json
from pathlib import Path

from core.schema import SchemaValidationError, validate_chip, validate_module


class DataLoadError(ValueError):
    pass


def _read_json(path):
    if not path.exists():
        raise DataLoadError(f"数据文件不存在: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_chip(path):
    chip = _read_json(Path(path))
    try:
        return validate_chip(chip)
    except SchemaValidationError as exc:
        raise DataLoadError(str(exc)) from exc


def load_module(path):
    module = _read_json(Path(path))
    try:
        return validate_module(module)
    except SchemaValidationError as exc:
        raise DataLoadError(str(exc)) from exc


def load_modules(module_dir, module_ids):
    module_dir = Path(module_dir)
    return [load_module(module_dir / f"{module_id}.json") for module_id in module_ids]
