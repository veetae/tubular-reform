"""Table load / tokenize / detect / reflow — all via the real library."""

from __future__ import annotations

from typing import Any

from cli_anything.tubular_reform.utils import tubular_reform_backend as backend


def load_text(project: dict[str, Any], text: str) -> dict[str, Any]:
    project["source_text"] = text
    project["cells"] = []
    project["detect"] = None
    project["result"] = None
    project["output"] = ""
    project["modified"] = True
    return project


def tokenize_project(project: dict[str, Any]) -> list[str]:
    cells = backend.tokenize(
        project.get("source_text") or "",
        strip=bool(project.get("strip", True)),
    )
    project["cells"] = cells
    project["modified"] = True
    return cells


def detect_project(project: dict[str, Any]) -> dict[str, Any]:
    if not project.get("cells"):
        tokenize_project(project)
    detected = backend.detect_ncols(
        project["cells"],
        text=project.get("source_text") or "",
    )
    project["detect"] = detected
    project["ncols"] = detected["ncols"]
    project["modified"] = True
    return detected


def reflow_project(project: dict[str, Any]) -> dict[str, Any]:
    if not project.get("cells"):
        tokenize_project(project)
    ncols = project.get("ncols")
    if ncols is None:
        detect_project(project)
        ncols = project["ncols"]
    result = backend.reflow(
        project["cells"],
        int(ncols),
        pad=str(project.get("pad") or "-"),
        header=bool(project.get("header")),
        strict=bool(project.get("strict")),
    )
    project["result"] = result
    project["modified"] = True
    return result


def apply_settings(
    project: dict[str, Any],
    *,
    ncols: int | None = None,
    header: bool | None = None,
    pad: str | None = None,
    strict: bool | None = None,
    fmt: str | None = None,
    strip: bool | None = None,
) -> dict[str, Any]:
    if ncols is not None:
        if ncols < 1:
            raise ValueError("ncols must be >= 1")
        project["ncols"] = ncols
    if header is not None:
        project["header"] = header
    if pad is not None:
        project["pad"] = pad
    if strict is not None:
        project["strict"] = strict
    if fmt is not None:
        project["format"] = fmt
    if strip is not None:
        project["strip"] = strip
    project["modified"] = True
    return project
