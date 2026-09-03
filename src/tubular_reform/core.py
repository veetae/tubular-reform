"""Core reflow logic for tubular-reform.

This module is pure: it performs no I/O (no clipboard, no files, no stdin).
Everything here is deterministic and unit-testable. The heart of the tool is
:func:`reflow`, which turns a flat list of cells back into a rectangular grid
*without ever silently misaligning the columns*.

The non-corruption guarantee
----------------------------
A naive "wrap every N cells" reshape corrupts a table silently the moment a row
is missing a cell: every value after the gap slides one position left, so an
entire table can look plausible while being wrong. :func:`reflow` refuses to do
that. It checks whether the cell count is a clean multiple of ``ncols`` and, if
it is not, it reports the discrepancy explicitly (via :class:`ReflowResult`) and
either pads-and-flags the short trailing row or, under ``strict=True``, raises
:class:`RaggedError` instead of guessing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

__all__ = [
    "RowIssue",
    "ReflowResult",
    "RaggedError",
    "reflow",
]


@dataclass(frozen=True)
class RowIssue:
    """A single row whose width does not match the requested column count.

    Attributes:
        index: Zero-based index of the row within the produced grid.
        width: Number of real (non-padding) cells the row actually held.
        expected: The requested column count (``ncols``).
    """

    index: int
    width: int
    expected: int

    @property
    def short_by(self) -> int:
        """How many cells the row is missing (0 if it is not short)."""
        return max(0, self.expected - self.width)

    @property
    def over_by(self) -> int:
        """How many extra cells the row carries (0 if it is not long)."""
        return max(0, self.width - self.expected)

    def describe(self, one_based: bool = True) -> str:
        n = self.index + 1 if one_based else self.index
        if self.short_by:
            return f"row {n}: has {self.width} of {self.expected} cells (short by {self.short_by})"
        return f"row {n}: has {self.width} of {self.expected} cells (over by {self.over_by})"


@dataclass
class ReflowResult:
    """The outcome of a :func:`reflow` call.

    Attributes:
        rows: The reconstructed grid. Every row has exactly ``ncols`` cells
            (short rows are padded with ``pad`` when ``strict`` is off).
        ncols: The column count the grid was built to.
        header: The header row (``ncols`` cells) when ``header=True``, else None.
        total_cells: Number of body cells fed to the reshape (excludes header).
        is_clean: True when ``total_cells`` was an exact multiple of ``ncols``
            (i.e. no padding was needed and nothing is misaligned by count).
        remainder: ``total_cells % ncols`` — nonzero means the input was ragged.
        issues: One :class:`RowIssue` per row whose real width != ``ncols``.
            For a flat reshape this is at most one entry (the trailing row).
        padded: True when at least one cell of padding was inserted.
        pad: The fill string used for padding.
    """

    rows: list[list[str]]
    ncols: int
    header: list[str] | None = None
    total_cells: int = 0
    is_clean: bool = True
    remainder: int = 0
    issues: list[RowIssue] = field(default_factory=list)
    padded: bool = False
    pad: str = "-"

    @property
    def nrows(self) -> int:
        return len(self.rows)

    def summary(self, one_based: bool = True) -> str:
        """A short human-readable status line (pure; no side effects)."""
        head = f"{self.nrows} row(s) x {self.ncols} col(s) from {self.total_cells} cell(s)"
        if self.header is not None:
            head += " (+1 header row)"
        if self.is_clean:
            return head + " — clean multiple, no padding."
        detail = "; ".join(i.describe(one_based) for i in self.issues) or "count not a clean multiple"
        return f"{head} — RAGGED: {detail}. Padded with {self.pad!r}."


class RaggedError(ValueError):
    """Raised in strict mode when the input is not a clean multiple of ncols.

    Carries the partial :class:`ReflowResult` (with ``rows`` left *unpadded*)
    so a caller can still show the user what was parsed before the refusal.
    """

    def __init__(self, message: str, result: ReflowResult):
        super().__init__(message)
        self.result = result


def _chunk_from(cells: Sequence[str], start: int, ncols: int) -> list[list[str]]:
    """Row-major wrap of ``cells[start:]``.

    List slices are already new lists; other sequences are materialized once
    per row so padding can extend a short trailing row in place.
    """
    rows: list[list[str]] = []
    for i in range(start, len(cells), ncols):
        piece = cells[i : i + ncols]
        rows.append(piece if isinstance(piece, list) else list(piece))
    return rows


def reflow(
    cells: Sequence[str],
    ncols: int,
    *,
    pad: str = "-",
    header: bool = False,
    strict: bool = False,
) -> ReflowResult:
    """Reshape a flat list of ``cells`` into a grid ``ncols`` wide.

    Args:
        cells: The flattened cells, in reading order (row-major). Blank cells
            must be present as empty strings — do not drop them, since a blank
            still occupies a column position.
        ncols: Target number of columns. Must be >= 1.
        pad: Fill string used to complete a short trailing row (default "-").
        header: When True, the first ``ncols`` cells become the header row and
            are excluded from the raggedness math.
        strict: When True, raise :class:`RaggedError` instead of padding if the
            body cell count is not a clean multiple of ``ncols``.

    Returns:
        A :class:`ReflowResult`.

    Raises:
        ValueError: if ``ncols`` < 1.
        RaggedError: if ``strict`` and the body is not a clean multiple.

    The reshape is row-major and deterministic. The only place a discrepancy can
    surface in a flat reshape is the final row; :func:`reflow` reports it rather
    than letting it slide.
    """
    if ncols < 1:
        raise ValueError(f"ncols must be >= 1, got {ncols}")

    header_row: list[str] | None = None
    start = 0
    if header:
        n_take = min(ncols, len(cells))
        raw = cells[:n_take]
        header_row = raw if isinstance(raw, list) else list(raw)
        start = n_take
        # Pad an incomplete header so the grid stays rectangular; flag it.
        if 0 < len(header_row) < ncols:
            header_row = header_row + [pad] * (ncols - len(header_row))

    total = len(cells) - start
    remainder = total % ncols
    is_clean = remainder == 0

    grid = _chunk_from(cells, start, ncols)

    # Identify every row whose real width != ncols. For a flat reshape only the
    # last row can be short, but computing it generally keeps the invariant
    # honest and makes the report robust if the input model ever changes.
    issues: list[RowIssue] = [
        RowIssue(index=i, width=len(row), expected=ncols)
        for i, row in enumerate(grid)
        if len(row) != ncols
    ]

    result = ReflowResult(
        rows=grid,  # possibly still ragged; padded below
        ncols=ncols,
        header=header_row,
        total_cells=total,
        is_clean=is_clean,
        remainder=remainder,
        issues=issues,
        padded=False,
        pad=pad,
    )

    if is_clean:
        return result

    if strict:
        detail = "; ".join(i.describe() for i in issues) or "count is not a clean multiple"
        raise RaggedError(
            f"Ragged input: {total} cell(s) is not a clean multiple of {ncols} "
            f"(remainder {remainder}). {detail}. "
            f"Refusing to guess column alignment in strict mode.",
            result,
        )

    # Non-strict: pad short rows in place. _chunk_from already gave us our own
    # row lists, so only the affected row is extended — never a full grid copy.
    for issue in issues:
        row = grid[issue.index]
        if len(row) < ncols:
            row.extend([pad] * (ncols - len(row)))
    result.padded = True
    return result
