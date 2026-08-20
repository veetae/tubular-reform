"""Tests for TSV / CSV / Markdown rendering."""

import csv
import io

import pytest

from tubular_reform.core import reflow
from tubular_reform.formats import render, to_csv, to_markdown, to_tsv


def test_tsv_basic():
    r = reflow(["a", "b", "c", "d"], 2)
    assert to_tsv(r) == "a\tb\nc\td"


def test_tsv_with_header():
    r = reflow(["H1", "H2", "a", "b"], 2, header=True)
    assert to_tsv(r) == "H1\tH2\na\tb"


def test_tsv_neutralizes_embedded_tab():
    # A cell containing a tab must not create a phantom column.
    r = reflow(["a\tx", "b", "c", "d"], 2)
    out = to_tsv(r)
    # First row must still have exactly one tab separator (2 columns).
    assert out.splitlines()[0].count("\t") == 1


def test_csv_basic_roundtrips():
    r = reflow(["a", "b", "c", "d"], 2)
    out = to_csv(r)
    parsed = list(csv.reader(io.StringIO(out)))
    assert parsed == [["a", "b"], ["c", "d"]]


def test_csv_quotes_comma_and_quote():
    r = reflow(["a,b", 'he said "hi"', "c", "d"], 2)
    out = to_csv(r)
    parsed = list(csv.reader(io.StringIO(out)))
    assert parsed[0] == ["a,b", 'he said "hi"']


def test_csv_with_header():
    r = reflow(["H1", "H2", "a", "b"], 2, header=True)
    out = to_csv(r)
    parsed = list(csv.reader(io.StringIO(out)))
    assert parsed == [["H1", "H2"], ["a", "b"]]


def test_markdown_synthesizes_headers_when_none():
    r = reflow(["a", "b", "c", "d"], 2)
    out = to_markdown(r)
    lines = out.splitlines()
    assert lines[0].startswith("| Column 1")
    assert set(lines[1].replace("|", "").replace(" ", "")) <= {"-"}
    # Data rows follow the separator; no data row was consumed as a header.
    assert "a" in lines[2] and "b" in lines[2]
    assert len(lines) == 4  # header + separator + 2 data rows


def test_markdown_uses_provided_header():
    r = reflow(["Name", "Qty", "apple", "3"], 2, header=True)
    out = to_markdown(r)
    assert out.splitlines()[0].startswith("| Name")


def test_markdown_escapes_pipe():
    r = reflow(["a|b", "c", "d", "e"], 2)
    out = to_markdown(r)
    assert r"a\|b" in out
    # The escaped pipe must not add a column. After removing escaped pipes the
    # only remaining bars are the structural ones: ncols+1 = 3 for 2 columns.
    data_line = [ln for ln in out.splitlines() if "a" in ln][0]
    structural = data_line.replace(r"\|", "")
    assert structural.count("|") == 3


def test_markdown_escapes_newline_as_br():
    r = reflow(["line1\nline2", "b", "c", "d"], 2)
    out = to_markdown(r)
    assert "<br>" in out


def test_markdown_padded_row_shows_pad():
    r = reflow(["a", "b", "c"], 2, pad="-")
    out = to_markdown(r)
    assert out.splitlines()[-1].count("-") >= 1  # padded cell present


def test_render_dispatch():
    r = reflow(["a", "b"], 2)
    assert render(r, "tsv") == "a\tb"
    assert render(r, "csv") == "a,b"
    assert render(r, "md").startswith("| Column 1")
    assert render(r, "markdown").startswith("| Column 1")


def test_render_unknown_format_raises():
    r = reflow(["a", "b"], 2)
    with pytest.raises(ValueError):
        render(r, "xml")


def test_unicode_in_all_formats():
    r = reflow(["café", "🚀", "Ω", "λ"], 2)
    assert "café" in to_tsv(r)
    assert "🚀" in to_csv(r)
    assert "Ω" in to_markdown(r)
