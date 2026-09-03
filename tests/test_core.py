"""Tests for the pure reflow core, including the non-corruption guarantees."""

import pytest

from tubular_reform.core import RaggedError, RowIssue, reflow


def test_clean_multiple_reshapes_row_major():
    cells = ["a", "b", "c", "d", "e", "f"]
    r = reflow(cells, 3)
    assert r.rows == [["a", "b", "c"], ["d", "e", "f"]]
    assert r.is_clean is True
    assert r.remainder == 0
    assert r.padded is False
    assert r.issues == []
    assert r.nrows == 2


def test_single_column():
    cells = ["x", "y", "z"]
    r = reflow(cells, 1)
    assert r.rows == [["x"], ["y"], ["z"]]
    assert r.is_clean is True


def test_ragged_trailing_row_is_padded_and_flagged():
    # 7 cells into 3 columns -> last row short by 2.
    cells = ["a", "b", "c", "d", "e", "f", "g"]
    r = reflow(cells, 3, pad="-")
    assert r.is_clean is False
    assert r.remainder == 1
    assert r.padded is True
    assert r.rows == [["a", "b", "c"], ["d", "e", "f"], ["g", "-", "-"]]
    assert len(r.issues) == 1
    issue = r.issues[0]
    assert issue.index == 2
    assert issue.width == 1
    assert issue.expected == 3
    assert issue.short_by == 2


def test_ragged_reported_row_index_is_exact():
    cells = list("abcdefghij")  # 10 cells
    r = reflow(cells, 4)  # rows: 4,4,2 -> last row (index 2) short by 2
    assert [i.index for i in r.issues] == [2]
    assert r.issues[0].short_by == 2
    # Confirms exactly which row is short (the guarantee: report, never hide).
    assert "row 3" in r.summary()


def test_strict_mode_refuses_on_ragged():
    cells = ["a", "b", "c", "d", "e"]
    with pytest.raises(RaggedError) as exc:
        reflow(cells, 3, strict=True)
    # The refusal carries a partial (unpadded) result for display.
    result = exc.value.result
    assert result.is_clean is False
    assert result.padded is False
    assert result.rows[-1] == ["d", "e"]  # not padded
    assert "not a clean multiple" in str(exc.value)


def test_strict_mode_passes_on_clean():
    cells = ["a", "b", "c", "d"]
    r = reflow(cells, 2, strict=True)
    assert r.is_clean is True
    assert r.rows == [["a", "b"], ["c", "d"]]


def test_ncols_larger_than_cell_count():
    cells = ["a", "b"]
    r = reflow(cells, 5)
    assert r.is_clean is False
    assert r.rows == [["a", "b", "-", "-", "-"]]
    assert r.issues[0].short_by == 3


def test_ncols_larger_than_cell_count_strict_refuses():
    with pytest.raises(RaggedError):
        reflow(["a", "b"], 5, strict=True)


def test_header_consumes_first_n_and_excludes_from_math():
    cells = ["H1", "H2", "a", "b", "c", "d"]
    r = reflow(cells, 2, header=True)
    assert r.header == ["H1", "H2"]
    assert r.rows == [["a", "b"], ["c", "d"]]
    assert r.total_cells == 4  # header excluded
    assert r.is_clean is True


def test_header_ragged_body_still_flags():
    cells = ["H1", "H2", "a", "b", "c"]  # body has 3 cells -> ragged for 2 cols
    r = reflow(cells, 2, header=True)
    assert r.header == ["H1", "H2"]
    assert r.is_clean is False
    assert r.rows == [["a", "b"], ["c", "-"]]


def test_incomplete_header_is_padded():
    # Fewer total cells than ncols with header=True -> the header itself is
    # short and gets padded (and there is no body).
    cells = ["H1"]  # 1 cell, ncols=2
    r = reflow(cells, 2, header=True)
    assert r.header == ["H1", "-"]
    assert r.rows == []


def test_empty_input():
    r = reflow([], 3)
    assert r.rows == []
    assert r.is_clean is True
    assert r.total_cells == 0
    assert r.nrows == 0


def test_blank_cells_preserved_as_positions():
    # A blank cell in the middle must keep its column position.
    cells = ["a", "", "c", "d", "e", "f"]
    r = reflow(cells, 3)
    assert r.rows == [["a", "", "c"], ["d", "e", "f"]]


def test_unicode_cells_pass_through():
    cells = ["café", "naïve", "🚀", "Ω", "λ", "「表」"]
    r = reflow(cells, 3)
    assert r.rows == [["café", "naïve", "🚀"], ["Ω", "λ", "「表」"]]


def test_custom_pad_string():
    r = reflow(["a", "b", "c"], 2, pad="N/A")
    assert r.rows == [["a", "b"], ["c", "N/A"]]


def test_ncols_zero_raises():
    with pytest.raises(ValueError):
        reflow(["a"], 0)


def test_ncols_negative_raises():
    with pytest.raises(ValueError):
        reflow(["a"], -1)


def test_rowissue_over_by():
    issue = RowIssue(index=0, width=5, expected=3)
    assert issue.over_by == 2
    assert issue.short_by == 0
    assert "over by 2" in issue.describe()


def test_result_summary_clean_vs_ragged():
    clean = reflow(["a", "b", "c", "d"], 2)
    assert "clean multiple" in clean.summary()
    ragged = reflow(["a", "b", "c"], 2)
    assert "RAGGED" in ragged.summary()
    assert "row 2" in ragged.summary()


def test_reflow_does_not_mutate_input_list():
    cells = ["a", "b", "c"]
    original = list(cells)
    reflow(cells, 2)
    assert cells == original


def test_reflow_accepts_tuple_without_requiring_a_list():
    r = reflow(("a", "b", "c", "d"), 2)
    assert r.rows == [["a", "b"], ["c", "d"]]
    r = reflow(("a", "b", "c"), 2)
    assert r.rows == [["a", "b"], ["c", "-"]]
