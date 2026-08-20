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
"""

from __future__ import annotations

__all__ = ["tokenize", "normalize_newlines"]


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def tokenize(text: str, *, strip: bool = True) -> list[str]:
    """Split raw ``text`` into cells (see module docstring for the rules).

    Args:
        text: The raw clipboard/stdin content.
        strip: When True (default) each cell is ``str.strip``-ed. Whitespace-only
            cells still survive as "" and keep their column position.

    Returns:
        The flat list of cells in reading order. Empty input -> ``[]``.
    """
    text = normalize_newlines(text)
    if text == "":
        return []
    # Drop exactly one trailing newline (final-line-break artifact), not interior ones.
    if text.endswith("\n"):
        text = text[:-1]
    if text == "":
        # Input was a single newline / all trailing breaks collapsed to nothing.
        return [""]

    lines = text.split("\n")
    has_tabs = any("\t" in line for line in lines)

    cells: list[str] = []
    if has_tabs:
        for line in lines:
            cells.extend(line.split("\t"))
    else:
        cells = lines

    if strip:
        cells = [c.strip() for c in cells]
    return cells
