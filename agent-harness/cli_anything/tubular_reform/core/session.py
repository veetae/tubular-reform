"""Stateful session with undo/redo and locked JSON saves."""

from __future__ import annotations

import copy
import json
import os
from typing import Any

from cli_anything.tubular_reform.core.project import load_project, new_project, save_project

MAX_UNDO = 50


def _locked_save_json(path: str, data: Any, **dump_kwargs) -> None:
    """Atomically write JSON with exclusive file locking."""
    dump_kwargs.setdefault("indent", 2)
    dump_kwargs.setdefault("ensure_ascii", False)
    dump_kwargs.setdefault("default", str)
    parent = os.path.dirname(os.path.abspath(path))
    try:
        handle = open(path, "r+")
    except FileNotFoundError:
        if parent:
            os.makedirs(parent, exist_ok=True)
        handle = open(path, "w")
    with handle:
        locked = False
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
        except (ImportError, OSError):
            pass
        try:
            handle.seek(0)
            handle.truncate()
            json.dump(data, handle, **dump_kwargs)
            handle.write("\n")
            handle.flush()
        finally:
            if locked:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def session_sidecar_path(project_path: str) -> str:
    root, _ext = os.path.splitext(os.path.abspath(project_path))
    return root + ".session.json"


class Session:
    """In-memory project plus undo/redo stacks, optionally persisted."""

    def __init__(self, project: dict[str, Any] | None = None) -> None:
        self.project: dict[str, Any] = project or new_project()
        self.undo_stack: list[dict[str, Any]] = []
        self.redo_stack: list[dict[str, Any]] = []

    def snapshot(self) -> None:
        self.undo_stack.append(copy.deepcopy(self.project))
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> dict[str, Any]:
        if not self.undo_stack:
            raise RuntimeError("nothing to undo")
        self.redo_stack.append(copy.deepcopy(self.project))
        self.project = self.undo_stack.pop()
        return self.project

    def redo(self) -> dict[str, Any]:
        if not self.redo_stack:
            raise RuntimeError("nothing to redo")
        self.undo_stack.append(copy.deepcopy(self.project))
        self.project = self.redo_stack.pop()
        return self.project

    def history(self) -> dict[str, Any]:
        return {
            "undo_depth": len(self.undo_stack),
            "redo_depth": len(self.redo_stack),
            "max_undo": MAX_UNDO,
            "project": self.project.get("name"),
            "path": self.project.get("path"),
            "modified": bool(self.project.get("modified")),
        }

    def load(self, path: str) -> dict[str, Any]:
        self.project = load_project(path)
        sidecar = session_sidecar_path(path)
        self.undo_stack = []
        self.redo_stack = []
        if os.path.isfile(sidecar):
            with open(sidecar, encoding="utf-8") as handle:
                data = json.load(handle)
            self.undo_stack = data.get("undo_stack") or []
            self.redo_stack = data.get("redo_stack") or []
        return self.project

    def save(self, path: str | None = None, *, dry_run: bool = False) -> str:
        dest = save_project(self.project, path)
        if not dry_run:
            _locked_save_json(
                session_sidecar_path(dest),
                {
                    "undo_stack": self.undo_stack,
                    "redo_stack": self.redo_stack,
                },
            )
        return dest

    def maybe_autosave(self, *, dry_run: bool = False) -> str | None:
        path = self.project.get("path")
        if dry_run or not path:
            return None
        return self.save(path, dry_run=False)
