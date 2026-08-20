"""tubular-reform — reform flattened 'tubular' text back into a real table.

Public API:
    reflow(cells, ncols, *, pad="-", header=False, strict=False) -> ReflowResult
    render(result, fmt="tsv") -> str
    tokenize(text, *, strip=True) -> list[str]
"""

from __future__ import annotations

__version__ = "0.1.0"

from .core import RaggedError, ReflowResult, RowIssue, reflow
from .formats import FORMATS, render, to_csv, to_markdown, to_tsv
from .tokenize import tokenize

__all__ = [
    "__version__",
    "reflow",
    "ReflowResult",
    "RowIssue",
    "RaggedError",
    "render",
    "to_tsv",
    "to_csv",
    "to_markdown",
    "FORMATS",
    "tokenize",
]
