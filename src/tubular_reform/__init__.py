"""tubular-reform — reform flattened 'tubular' text back into a real table.

Public API:
    reflow(cells, ncols, *, pad="-", header=False, strict=False) -> ReflowResult
    detect_ncols(cells, *, text=None) -> DetectResult
    render(result, fmt="tsv") -> str
    tokenize(text, *, strip=True) -> list[str]
"""

from __future__ import annotations

__version__ = "0.2.0"

from .core import RaggedError, ReflowResult, RowIssue, reflow
from .detect import DetectError, DetectResult, detect_ncols
from .formats import FORMATS, render, to_csv, to_markdown, to_tsv
from .tokenize import tokenize

__all__ = [
    "__version__",
    "reflow",
    "ReflowResult",
    "RowIssue",
    "RaggedError",
    "detect_ncols",
    "DetectResult",
    "DetectError",
    "render",
    "to_tsv",
    "to_csv",
    "to_markdown",
    "FORMATS",
    "tokenize",
]
