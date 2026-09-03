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


def _tsv_clean(cell: str) -> str:
    """Neutralize tabs/newlines. Skip the replaces when the cell is already safe."""
    if "\t" not in cell and "\r" not in cell and "\n" not in cell:
        return cell
    return cell.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def to_tsv(result: ReflowResult) -> str:
    """Tab-separated values. Tabs/newlines inside a cell are neutralized to
    spaces so a cell can never break the row/column structure it lives in."""
    chunks: list[str] = []
    if result.header is not None:
        chunks.append("\t".join(_tsv_clean(c) for c in result.header))
    for row in result.rows:
        chunks.append("\t".join(_tsv_clean(c) for c in row))
    return "\n".join(chunks)


def to_csv(result: ReflowResult) -> str:
    """RFC 4180 CSV via the stdlib csv module (handles quoting/escaping)."""
    buf = io.StringIO()
    # lineterminator="\n" keeps output platform-neutral and test-stable.
    writer = csv.writer(buf, lineterminator="\n")
    if result.header is not None:
        writer.writerow(result.header)
    writer.writerows(result.rows)
    return buf.getvalue().rstrip("\n")


def _md_escape(cell: str) -> str:
    # Pipes would break table columns; newlines would break rows.
    if "\\" not in cell and "|" not in cell and "\n" not in cell and "\r" not in cell:
        return cell
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
    ncols = result.ncols
    header = result.header
    if header is None:
        header = [f"Column {i + 1}" for i in range(ncols)]

    widths = [3] * ncols  # min 3 for the '---' rule
    esc_header: list[str] = []
    for i in range(ncols):
        cell = header[i] if i < len(header) else ""
        escaped = _md_escape(cell)
        esc_header.append(escaped)
        widths[i] = max(widths[i], len(escaped))

    esc_rows: list[list[str]] = []
    for row in result.rows:
        esc_row: list[str] = []
        for i in range(ncols):
            cell = row[i] if i < len(row) else ""
            escaped = _md_escape(cell)
            esc_row.append(escaped)
            widths[i] = max(widths[i], len(escaped))
        esc_rows.append(esc_row)

    def fmt_row(cells: list[str]) -> str:
        padded = [cells[i].ljust(widths[i]) for i in range(ncols)]
        return "| " + " | ".join(padded) + " |"

    sep = "| " + " | ".join("-" * widths[i] for i in range(ncols)) + " |"
    lines = [fmt_row(esc_header), sep]
    lines.extend(fmt_row(r) for r in esc_rows)
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
