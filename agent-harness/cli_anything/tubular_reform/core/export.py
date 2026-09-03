"""Export pipeline: real tubular_reform.render only."""

from __future__ import annotations

import os
from typing import Any

from cli_anything.tubular_reform.core.table import reflow_project
from cli_anything.tubular_reform.utils import tubular_reform_backend as backend


def render_project(project: dict[str, Any], fmt: str | None = None) -> str:
    result = project.get("result")
    if result is None:
        result = reflow_project(project)
    chosen = fmt or project.get("format") or "tsv"
    output = backend.render(result, chosen)
    project["format"] = chosen
    project["output"] = output
    project["modified"] = True
    return output


def write_project(
    project: dict[str, Any],
    path: str,
    fmt: str | None = None,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    dest = os.path.abspath(path)
    if os.path.exists(dest) and not overwrite:
        raise FileExistsError(f"refusing to overwrite {dest} (pass --overwrite)")
    output = render_project(project, fmt)
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as handle:
        handle.write(output)
        if output and not output.endswith("\n"):
            handle.write("\n")
    size = os.path.getsize(dest)
    return {
        "output_path": dest,
        "format": project.get("format"),
        "file_size": size,
        "output": output,
    }
