"""Turn raw pasted/piped text into a flat list of cells.

Pure and deterministic. The rules here are deliberately conservative so that
column position is never lost:

* Line endings are normalized (CRLF/CR -> LF) before splitting.
* Exactly one trailing newline (the artifact of a final line break) is dropped;
  interior blank lines are kept, because a blank line is a blank *cell* that
  holds a column position.
* If any line already contains a tab, the input is treated as an
  already-delimited (possibly malformed) table: every line is split on tabs and
  the cells are concatenated in reading order, so a mis-widthed table can be
  re-flowed to the right column count.
* Each cell is stripped of surrounding whitespace by default; a whitespace-only
  cell becomes "" (an empty *kept* cell), never dropped.

Splitting on newline *or* tab in one pass is equivalent to the older
"split lines, then if any line had a tab, split every line on tabs" sequence,
without a normalized copy, a lines list, and a cells list all live at once.
"""

from __future__ import annotations

import re

__all__ = ["tokenize", "normalize_newlines"]

# One scan splits CRLF / CR / LF / tab. Order matters: CRLF before CR.
_CELL_SPLIT = re.compile(r"\r\n|\r|\n|\t")


def normalize_newlines(text: str) -> str:
    """CRLF/CR -> LF. Fast-path when the paste is already LF-only."""
    if "\r" not in text:
        return text
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _drop_one_trailing_newline(text: str) -> str:
    """Remove exactly one trailing CRLF, CR, or LF (final-line-break artifact)."""
    if text.endswith("\r\n"):
        return text[:-2]
    if text.endswith("\n") or text.endswith("\r"):
        return text[:-1]
    return text


def tokenize(text: str, *, strip: bool = True) -> list[str]:
    """Split raw ``text`` into cells (see module docstring for the rules).

    Args:
        text: The raw clipboard/stdin content.
        strip: When True (default) each cell is ``str.strip``-ed. Whitespace-only
            cells still survive as "" and keep their column position.

    Returns:
        The flat list of cells in reading order. Empty input -> ``[]``.
    """
    if text == "":
        return []
    core = _drop_one_trailing_newline(text)
    if core == "":
        # Input was a single newline / all trailing breaks collapsed to nothing.
        return [""]

    # LF-only, no tabs: one C-level split. Otherwise one regex scan for mixed
    # line endings and already-delimited (tab) pastes.
    if "\t" not in core and "\r" not in core:
        parts = core.split("\n")
    else:
        parts = _CELL_SPLIT.split(core)

    if not strip:
        return parts
    for i, cell in enumerate(parts):
        parts[i] = cell.strip()
    return parts
