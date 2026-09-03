"""Auto-detect a column count from flattened cells.

This is a *guess with a refusal*, not a silent reshape. The non-corruption
guarantee still holds: if the type pattern is uniform or two periods score
the same, :func:`detect_ncols` raises rather than picking a width that would
slide every cell into the wrong column.

Two signals, in order:

1. **Consistent tab width** — when the raw paste is already delimited and
   every non-empty line has the same field count ``k >= 2``, that ``k`` is
   the table's current width (useful for TSV → CSV/Markdown without ``-c``).
2. **Repeating type period** — classify each cell as empty / number / date /
   text and look for the smallest period that repeats for at least two full
   rows. Empty cells are wildcards. Uniform type (all text, all numbers)
   is not a signal, so it refuses.

Passing ``-c`` on the CLI still wins over either guess.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .tokenize import normalize_newlines

__all__ = [
    "KIND_DATE",
    "KIND_EMPTY",
    "KIND_NUMBER",
    "KIND_TEXT",
    "DetectError",
    "DetectResult",
    "classify_cell",
    "detect_ncols",
]

KIND_EMPTY = "empty"
KIND_NUMBER = "number"
KIND_DATE = "date"
KIND_TEXT = "text"

# Flattened one-cell-per-line tables rarely have more columns than this;
# capping keeps the search honest and cheap.
_MAX_AUTO_COLS = 48
_MIN_SCORE = 0.85
_TIE_DELTA = 0.04

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_US_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}(?:\d{2})?$")
_NUMBER = re.compile(r"^-?(?:\d+\.\d+|\d+)(?:[eE][+-]?\d+)?$")


@dataclass(frozen=True)
class DetectResult:
    """Outcome of a successful :func:`detect_ncols` call.

    Attributes:
        ncols: The detected column count (>= 2).
        method: ``"tab-width"`` or ``"type-period"``.
        score: 1.0 for a unanimous tab width; type-period majority-match rate.
        candidates: ``(ncols, score)`` pairs that were close enough to consider.
    """

    ncols: int
    method: str
    score: float
    candidates: tuple[tuple[int, float], ...] = ()

    def describe(self) -> str:
        if self.method == "tab-width":
            return f"detected {self.ncols} column(s) from consistent tab width"
        return f"detected {self.ncols} column(s) from repeating type pattern"


class DetectError(ValueError):
    """Raised when auto-detect cannot pick a unique, high-confidence width."""

    def __init__(self, message: str, candidates: tuple[tuple[int, float], ...] = ()):
        super().__init__(message)
        self.candidates = candidates


def classify_cell(cell: str) -> str:
    """Return one of empty / number / date / text for ``cell``."""
    text = cell.strip()
    if text == "":
        return KIND_EMPTY
    if _ISO_DATE.match(text) or _US_DATE.match(text):
        return KIND_DATE
    if _NUMBER.match(text):
        return KIND_NUMBER
    return KIND_TEXT


def _tab_row_widths(text: str) -> list[int] | None:
    """Per-line field counts when the paste already contains tabs, else None."""
    if "\t" not in text:
        return None
    body = normalize_newlines(text)
    if body.endswith("\n"):
        body = body[:-1]
    if body == "":
        return None
    return [len(line.split("\t")) for line in body.split("\n")]


def _detect_tab_width(text: str | None) -> DetectResult | None:
    if text is None:
        return None
    widths = _tab_row_widths(text)
    if not widths:
        return None
    nonempty = [w for w in widths if w >= 1]
    if not nonempty:
        return None
    unique = set(nonempty)
    if len(unique) != 1:
        # Mixed widths: flattening then wrapping to the mode would silently
        # slide cells. Refuse this signal and fall through to type-period.
        return None
    ncols = unique.pop()
    if ncols < 2:
        return None
    return DetectResult(
        ncols=ncols,
        method="tab-width",
        score=1.0,
        candidates=((ncols, 1.0),),
    )


def _period_score(kinds: list[str], period: int) -> float:
    """Fraction of non-empty cells matching the majority kind in their column."""
    n = len(kinds)
    matched = 0
    total = 0
    for col in range(period):
        col_kinds = [
            kinds[i] for i in range(col, n, period) if kinds[i] != KIND_EMPTY
        ]
        if not col_kinds:
            continue
        majority = Counter(col_kinds).most_common(1)[0][1]
        matched += majority
        total += len(col_kinds)
    if total == 0:
        return 0.0
    return matched / total


def _detect_type_period(cells: list[str]) -> DetectResult:
    n = len(cells)
    kinds = [classify_cell(c) for c in cells]
    distinct = {k for k in kinds if k != KIND_EMPTY}
    if len(distinct) < 2:
        raise DetectError(
            "could not auto-detect column count (cells are all the same type; "
            "pass -c N)"
        )
    if n < 4:
        raise DetectError(
            "could not auto-detect column count (need at least two rows of "
            "a mixed-type pattern; pass -c N)"
        )

    max_p = min(n // 2, _MAX_AUTO_COLS)
    scored: list[tuple[int, float]] = []
    for period in range(2, max_p + 1):
        full = _period_score(kinds, period)
        # A text header row (Name / Qty / Price) otherwise pulls a mixed-type
        # body below the accept threshold. If at least two body rows remain,
        # also score the tail and keep the better of the two.
        if n >= 3 * period:
            headered = _period_score(kinds[period:], period)
            score = max(full, headered)
        else:
            score = full
        scored.append((period, score))

    if not scored:
        raise DetectError(
            "could not auto-detect column count (not enough cells; pass -c N)"
        )

    best_score = max(score for _, score in scored)
    if best_score < _MIN_SCORE:
        top = tuple(sorted(scored, key=lambda kv: (-kv[1], kv[0]))[:5])
        raise DetectError(
            "could not auto-detect column count (no repeating type pattern "
            f"scored >= {_MIN_SCORE:.2f}; pass -c N)",
            candidates=top,
        )

    contenders = [
        (period, score)
        for period, score in scored
        if score >= best_score - _TIE_DELTA and score >= _MIN_SCORE
    ]
    contenders.sort(key=lambda kv: kv[0])
    smallest = contenders[0][0]
    # 6 scoring like 3 is the same pattern doubled — keep the smallest.
    # 3 vs 4 at the same score is a real fork — refuse.
    independent = [
        (period, score)
        for period, score in contenders
        if period == smallest or period % smallest != 0
    ]
    if len(independent) > 1:
        shown = tuple(contenders)
        labels = " vs ".join(str(p) for p, _ in independent)
        raise DetectError(
            f"could not auto-detect column count (ambiguous: {labels}; "
            "pass -c N to choose)",
            candidates=shown,
        )

    chosen = smallest
    chosen_score = next(score for period, score in contenders if period == chosen)
    return DetectResult(
        ncols=chosen,
        method="type-period",
        score=chosen_score,
        candidates=tuple(contenders),
    )


def detect_ncols(cells: list[str], *, text: str | None = None) -> DetectResult:
    """Guess a column count, or raise :class:`DetectError`.

    Args:
        cells: Flattened cells in reading order (same list :func:`reflow` gets).
        text: Optional raw clipboard/stdin text. Used only for the tab-width
            signal; type-period looks at ``cells`` alone.
    """
    tab = _detect_tab_width(text)
    if tab is not None:
        return tab
    if not cells:
        raise DetectError(
            "could not auto-detect column count (no input cells; pass -c N)"
        )
    return _detect_type_period(cells)
