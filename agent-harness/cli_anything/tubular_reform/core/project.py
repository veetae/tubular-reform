"""JSON project create / open / save / info."""

from __future__ import annotations

import json
import os
from typing import Any

SCHEMA_VERSION = 1


def new_project(name: str = "untitled") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "path": None,
        "source_text": "",
        "strip": True,
        "ncols": None,
        "header": False,
        "pad": "-",
        "strict": False,
        "format": "tsv",
        "cells": [],
        "detect": None,
        "result": None,
        "output": "",
        "modified": False,
    }


def load_project(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"project file is not a JSON object: {path}")
    project = new_project()
    project.update(data)
    project["path"] = os.path.abspath(path)
    project["modified"] = False
    return project


def save_project(project: dict[str, Any], path: str | None = None) -> str:
    dest = path or project.get("path")
    if not dest:
        raise ValueError("no project path; pass -o / --path")
    dest = os.path.abspath(dest)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    to_write = dict(project)
    to_write["path"] = dest
    to_write["modified"] = False
    with open(dest, "w", encoding="utf-8") as handle:
        json.dump(to_write, handle, indent=2, ensure_ascii=False, default=str)
        handle.write("\n")
    project["path"] = dest
    project["modified"] = False
    return dest


def project_info(project: dict[str, Any]) -> dict[str, Any]:
    result = project.get("result") or {}
    return {
        "name": project.get("name"),
        "path": project.get("path"),
        "modified": bool(project.get("modified")),
        "cell_count": len(project.get("cells") or []),
        "ncols": project.get("ncols"),
        "header": bool(project.get("header")),
        "pad": project.get("pad"),
        "strict": bool(project.get("strict")),
        "format": project.get("format"),
        "detect": project.get("detect"),
        "is_clean": result.get("is_clean"),
        "nrows": result.get("nrows"),
        "has_output": bool(project.get("output")),
        "summary": result.get("summary"),
    }
