"""Serialize a reconstructed grid to TSV, CSV, or Markdown.

Pure functions only — they take a :class:`~tubular_reform.core.ReflowResult`
(or plain rows) and return a string. No I/O here either.
"""

from __future__ import annotations

import csv
import io

from .core import ReflowResult

__all__ = ["FORMATS", "render", "to_tsv", "to_csv", "to_markdown"]

FORMATS = ("tsv", "csv", "md")


def _rows_with_header(result: ReflowResult) -> tuple[list[str] | None, list[list[str]]]:
    return result.header, result.rows


def to_tsv(result: ReflowResult) -> str:
    """Tab-separated values. Tabs/newlines inside a cell are neutralized to
    spaces so a cell can never break the row/column structure it lives in."""
    header, rows = _rows_with_header(result)
    all_rows = ([header] if header is not None else []) + rows

    def clean(cell: str) -> str:
        return cell.replace("\t", " ").replace("\r", " ").replace("\n", " ")

    return "\n".join("\t".join(clean(c) for c in row) for row in all_rows)


def to_csv(result: ReflowResult) -> str:
    """RFC 4180 CSV via the stdlib csv module (handles quoting/escaping)."""
    header, rows = _rows_with_header(result)
    all_rows = ([header] if header is not None else []) + rows
    buf = io.StringIO()
    # lineterminator="\n" keeps output platform-neutral and test-stable.
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerows(all_rows)
    return buf.getvalue().rstrip("\n")


def _md_escape(cell: str) -> str:
    # Pipes would break table columns; newlines would break rows.
    return (
        cell.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r\n", " ")
        .replace("\n", "<br>")
        .replace("\r", " ")
    )


def to_markdown(result: ReflowResult) -> str:
    """GitHub-flavored Markdown table.

    A Markdown table requires a header row. When the input had no header
    (``header=False``), synthesized ``Column 1..N`` headers are used rather than
    silently consuming the first data row — no data is lost or reinterpreted.
    Columns are space-padded so the raw text is also readable.
    """
    header, rows = _rows_with_header(result)
    ncols = result.ncols
    if header is None:
        header = [f"Column {i + 1}" for i in range(ncols)]

    esc_header = [_md_escape(c) for c in header]
    esc_rows = [[_md_escape(c) for c in row] for row in rows]

    # Compute display width per column for alignment (min 3 for the '---' rule).
    widths = [max(3, len(esc_header[i])) for i in range(ncols)]
    for row in esc_rows:
        for i in range(ncols):
            if i < len(row):
                widths[i] = max(widths[i], len(row[i]))

    def fmt_row(cells: list[str]) -> str:
        padded = [
            (cells[i] if i < len(cells) else "").ljust(widths[i]) for i in range(ncols)
        ]
        return "| " + " | ".join(padded) + " |"

    sep = "| " + " | ".join("-" * widths[i] for i in range(ncols)) + " |"
    lines = [fmt_row(esc_header), sep] + [fmt_row(r) for r in esc_rows]
    return "\n".join(lines)


def render(result: ReflowResult, fmt: str = "tsv") -> str:
    """Dispatch to the requested format ('tsv' | 'csv' | 'md')."""
    fmt = fmt.lower()
    if fmt == "tsv":
        return to_tsv(result)
    if fmt == "csv":
        return to_csv(result)
    if fmt in ("md", "markdown"):
        return to_markdown(result)
    raise ValueError(f"unknown format {fmt!r}; choose one of {', '.join(FORMATS)}")
