"""Tests for the text tokenizer (flattened text -> cells)."""

from tubular_reform.tokenize import normalize_newlines, tokenize


def test_simple_one_cell_per_line():
    assert tokenize("a\nb\nc") == ["a", "b", "c"]


def test_trailing_newline_dropped_once():
    # A single final newline is an artifact, not a blank cell.
    assert tokenize("a\nb\nc\n") == ["a", "b", "c"]


def test_interior_blank_line_preserved_as_blank_cell():
    assert tokenize("a\n\nc") == ["a", "", "c"]


def test_whitespace_only_line_becomes_blank_cell():
    assert tokenize("a\n   \nc") == ["a", "", "c"]


def test_whitespace_only_line_preserved_when_no_strip():
    assert tokenize("a\n   \nc", strip=False) == ["a", "   ", "c"]


def test_crlf_normalized():
    assert tokenize("a\r\nb\r\nc\r\n") == ["a", "b", "c"]


def test_bare_cr_normalized():
    assert tokenize("a\rb\rc") == ["a", "b", "c"]


def test_empty_string_yields_no_cells():
    assert tokenize("") == []


def test_only_newline_yields_single_blank_cell():
    # "\n" -> after dropping one trailing newline the text is empty but a line
    # break was present, so one blank cell is kept.
    assert tokenize("\n") == [""]


def test_tab_delimited_input_is_split_and_flattened():
    # Already-a-table (possibly wrong width) -> flatten so it can be re-flowed.
    text = "a\tb\tc\nd\te\tf"
    assert tokenize(text) == ["a", "b", "c", "d", "e", "f"]


def test_mixed_tab_and_plain_lines():
    text = "a\tb\nc\nd\te"
    assert tokenize(text) == ["a", "b", "c", "d", "e"]


def test_tab_empty_cells_preserved():
    text = "a\t\tc"
    assert tokenize(text) == ["a", "", "c"]


def test_strip_default_trims_cells():
    assert tokenize("  a  \n b ") == ["a", "b"]


def test_no_strip_keeps_padding():
    assert tokenize("  a  \n b ", strip=False) == ["  a  ", " b "]


def test_unicode_preserved():
    assert tokenize("café\n🚀\nΩ") == ["café", "🚀", "Ω"]


def test_normalize_newlines_helper():
    assert normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"
