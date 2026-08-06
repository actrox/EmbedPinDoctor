import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from versioning.project_migration import migrate_project


def _safe_name(name):
    cleaned = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", str(name)).strip("_")
    return cleaned or "untitled_project"


class ProjectStore:
    def __init__(self, root, history_limit=30):
        self.root = Path(root)
        self.history_root = self.root / ".history"
        self.history_limit = history_limit

    def _path(self, name):
        return self.root / f"{_safe_name(name)}.json"

    def _history_dir(self, name, kind):
        return self.history_root / _safe_name(name) / kind

    @staticmethod
    def _atomic_write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def _snapshot(self, name, kind, data):
        folder = self._history_dir(name, kind)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        self._atomic_write(folder / f"{stamp}.json", data)
        entries = sorted(folder.glob("*.json"), reverse=True)
        for old in entries[self.history_limit:]:
            old.unlink()

    def _clear(self, name, kind):
        folder = self._history_dir(name, kind)
        if folder.exists():
            for path in folder.glob("*.json"):
                path.unlink()

    def load(self, name):
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"项目不存在: {name}")
        data = json.loads(path.read_text(encoding="utf-8"))
        migrated, migrations = migrate_project(data)
        if migrations:
            self._snapshot(name, "undo", data)
            self._atomic_write(path, migrated)
        return migrated, migrations

    def save(self, project):
        migrated, migrations = migrate_project(project)
        name = migrated.get("project_name", "untitled_project")
        path = self._path(name)
        if path.exists():
            previous = json.loads(path.read_text(encoding="utf-8"))
            self._snapshot(name, "undo", previous)
        self._clear(name, "redo")
        self._atomic_write(path, migrated)
        return path, migrations

    def _move(self, name, source, destination):
        current, _ = self.load(name)
        entries = sorted(self._history_dir(name, source).glob("*.json"))
        if not entries:
            raise ValueError("没有可用的历史版本")
        target = entries[-1]
        restored = json.loads(target.read_text(encoding="utf-8"))
        self._snapshot(name, destination, current)
        target.unlink()
        restored, migrations = migrate_project(restored)
        self._atomic_write(self._path(name), restored)
        return restored, migrations

    def undo(self, name):
        return self._move(name, "undo", "redo")

    def redo(self, name):
        return self._move(name, "redo", "undo")

    def history(self, name):
        return {
            "undo": len(list(self._history_dir(name, "undo").glob("*.json"))),
            "redo": len(list(self._history_dir(name, "redo").glob("*.json"))),
            "limit": self.history_limit,
        }
