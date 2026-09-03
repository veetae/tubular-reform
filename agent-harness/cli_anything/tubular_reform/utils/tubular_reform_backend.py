"""Backend: invoke the real tubular-reform library (and native CLI).

The harness is a structured interface TO tubular-reform, not a replacement.
If the library is missing, fail with install instructions — no fallback reshape.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any

SOFTWARE_INSTALL = (
    "tubular-reform is not installed. Install the real backend with:\n"
    "  pip install tubular-reform\n"
    "  # or from this repo:\n"
    "  pip install -e ."
)


def require_library():
    """Import the real tubular_reform package or raise with install help."""
    try:
        import tubular_reform
    except ImportError as exc:
        raise RuntimeError(SOFTWARE_INSTALL) from exc
    return tubular_reform


def find_native_cli() -> str:
    """Return the installed ``tubular-reform`` console script path."""
    path = shutil.which("tubular-reform")
    if path:
        return path
    raise RuntimeError(
        "tubular-reform CLI is not on PATH. Install with:\n"
        "  pip install tubular-reform\n"
        "and ensure the scripts directory is on PATH."
    )


def tokenize(text: str, *, strip: bool = True) -> list[str]:
    lib = require_library()
    return lib.tokenize(text, strip=strip)


def detect_ncols(cells: list[str], *, text: str | None = None) -> dict[str, Any]:
    lib = require_library()
    try:
        result = lib.detect_ncols(cells, text=text)
    except lib.DetectError as exc:
        raise DetectFailed(str(exc), getattr(exc, "candidates", None)) from exc
    return {
        "ncols": result.ncols,
        "method": result.method,
        "score": result.score,
        "candidates": [list(pair) for pair in result.candidates],
        "describe": result.describe(),
    }


def reflow(
    cells: list[str],
    ncols: int,
    *,
    pad: str = "-",
    header: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    lib = require_library()
    try:
        result = lib.reflow(
            cells, ncols, pad=pad, header=header, strict=strict,
        )
    except lib.RaggedError as exc:
        raise RaggedFailed(str(exc), result_to_dict(exc.result)) from exc
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    return result_to_dict(result)


def render(result: dict[str, Any], fmt: str = "tsv") -> str:
    lib = require_library()
    obj = dict_to_result(result)
    return lib.render(obj, fmt)


def result_to_dict(result) -> dict[str, Any]:
    return {
        "rows": [list(row) for row in result.rows],
        "ncols": result.ncols,
        "header": list(result.header) if result.header is not None else None,
        "total_cells": result.total_cells,
        "is_clean": result.is_clean,
        "remainder": result.remainder,
        "issues": [
            {
                "index": issue.index,
                "width": issue.width,
                "expected": issue.expected,
                "describe": issue.describe(),
            }
            for issue in result.issues
        ],
        "padded": result.padded,
        "pad": result.pad,
        "nrows": result.nrows,
        "summary": result.summary(),
    }


def dict_to_result(data: dict[str, Any]):
    lib = require_library()
    issues = [
        lib.RowIssue(
            index=item["index"],
            width=item["width"],
            expected=item["expected"],
        )
        for item in data.get("issues") or []
    ]
    return lib.ReflowResult(
        rows=[list(row) for row in data.get("rows") or []],
        ncols=int(data["ncols"]),
        header=list(data["header"]) if data.get("header") is not None else None,
        total_cells=int(data.get("total_cells") or 0),
        is_clean=bool(data.get("is_clean", True)),
        remainder=int(data.get("remainder") or 0),
        issues=issues,
        padded=bool(data.get("padded", False)),
        pad=str(data.get("pad", "-")),
    )


def invoke_native_cli(
    text: str,
    *,
    ncols: int | None,
    fmt: str = "tsv",
    header: bool = False,
    strict: bool = False,
    pad: str = "-",
    strip: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run the real ``tubular-reform`` console script on ``text``."""
    cmd = [find_native_cli(), "--stdin", "-q", "-f", fmt, "--pad", pad]
    if ncols is not None:
        cmd.extend(["-c", str(ncols)])
    if header:
        cmd.append("--header")
    if strict:
        cmd.append("--strict")
    if not strip:
        cmd.append("--no-strip")
    return subprocess.run(
        cmd,
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )


class DetectFailed(RuntimeError):
    """Auto-detect refused; agents must pass an explicit column count."""

    def __init__(self, message: str, candidates=None):
        super().__init__(message)
        self.candidates = list(candidates or [])


class RaggedFailed(RuntimeError):
    """Strict reflow refused a ragged cell count."""

    def __init__(self, message: str, result: dict[str, Any]):
        super().__init__(message)
        self.result = result
