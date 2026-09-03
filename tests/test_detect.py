"""Tests for column-count auto-detection (refusal when the guess is unsafe)."""

import pytest

from tubular_reform.detect import (
    KIND_DATE,
    KIND_EMPTY,
    KIND_NUMBER,
    KIND_TEXT,
    DetectError,
    classify_cell,
    detect_ncols,
)


def test_classify_number_int_and_float():
    assert classify_cell("3") == KIND_NUMBER
    assert classify_cell("0.50") == KIND_NUMBER
    assert classify_cell("-2.5e3") == KIND_NUMBER


def test_classify_date_iso_and_us():
    assert classify_cell("2026-08-20") == KIND_DATE
    assert classify_cell("8/20/2026") == KIND_DATE
    assert classify_cell("08/20/26") == KIND_DATE


def test_classify_empty_and_text():
    assert classify_cell("") == KIND_EMPTY
    assert classify_cell("   ") == KIND_EMPTY
    assert classify_cell("Apple") == KIND_TEXT
    assert classify_cell("N/A") == KIND_TEXT


def test_produce_list_detects_three_columns():
    cells = [
        "Apple", "3", "0.50",
        "Banana", "6", "0.25",
        "Cherry", "12", "2.00",
        "Date", "4", "5.75",
    ]
    result = detect_ncols(cells)
    assert result.ncols == 3
    assert result.method == "type-period"
    assert result.score >= 0.99


def test_name_qty_detects_two_columns():
    cells = ["apple", "3", "banana", "6", "cherry", "12"]
    result = detect_ncols(cells)
    assert result.ncols == 2
    assert result.method == "type-period"


def test_header_row_does_not_break_type_period():
    cells = [
        "Name", "Qty", "Price",
        "Apple", "3", "0.50",
        "Banana", "6", "0.25",
    ]
    result = detect_ncols(cells)
    assert result.ncols == 3


def test_date_column_in_ehr_like_rows():
    cells = [
        "Alice", "1980-01-01", "active",
        "Bob", "1975-12-31", "inactive",
        "Cara", "1990-06-15", "active",
    ]
    result = detect_ncols(cells)
    assert result.ncols == 3


def test_empty_cells_are_wildcards():
    cells = [
        "Apple", "3", "0.50",
        "Banana", "", "0.25",
        "Cherry", "12", "2.00",
    ]
    result = detect_ncols(cells)
    assert result.ncols == 3


def test_all_text_refuses():
    cells = ["a", "b", "c", "d", "e", "f"]
    with pytest.raises(DetectError) as exc:
        detect_ncols(cells)
    assert "same type" in str(exc.value)
    assert "pass -c N" in str(exc.value)


def test_all_numbers_refuses():
    cells = ["1", "2", "3", "4", "5", "6"]
    with pytest.raises(DetectError) as exc:
        detect_ncols(cells)
    assert "same type" in str(exc.value)


def test_too_few_cells_refuses():
    with pytest.raises(DetectError):
        detect_ncols(["Apple", "3", "0.50"])  # one mixed row, cannot confirm


def test_empty_input_refuses():
    with pytest.raises(DetectError) as exc:
        detect_ncols([])
    assert "no input" in str(exc.value)


def test_consistent_tab_width_wins():
    text = "a\tb\tc\nd\te\tf\n"
    cells = ["a", "b", "c", "d", "e", "f"]
    result = detect_ncols(cells, text=text)
    assert result.ncols == 3
    assert result.method == "tab-width"
    assert result.score == 1.0


def test_single_tab_row_is_enough():
    text = "name\tqty\tprice"
    result = detect_ncols(["name", "qty", "price"], text=text)
    assert result.ncols == 3
    assert result.method == "tab-width"


def test_blank_tsv_lines_do_not_veto_tab_width():
    # A second trailing newline and an interior blank line must not count as
    # width 1; every non-empty line is still 3-wide.
    text = "a\tb\tc\n\nd\te\tf\n\n"
    cells = ["a", "b", "c", "", "d", "e", "f", ""]
    result = detect_ncols(cells, text=text)
    assert result.ncols == 3
    assert result.method == "tab-width"


def test_ragged_tab_widths_do_not_use_mode():
    # Mixed 2-wide and 3-wide rows: using the mode would slide cells.
    text = "a\tb\nc\td\te\nf\tg\n"
    cells = ["a", "b", "c", "d", "e", "f", "g"]
    with pytest.raises(DetectError):
        detect_ncols(cells, text=text)


def test_no_tabs_falls_through_to_type_period():
    text = "Apple\n3\n0.50\nBanana\n6\n0.25\n"
    cells = ["Apple", "3", "0.50", "Banana", "6", "0.25"]
    result = detect_ncols(cells, text=text)
    assert result.method == "type-period"
    assert result.ncols == 3


def test_doubled_period_prefers_smallest():
    # 4 rows x 3 cols of T/N/N also looks like 2 rows x 6; pick 3.
    cells = [
        "a", "1", "0.1",
        "b", "2", "0.2",
        "c", "3", "0.3",
        "d", "4", "0.4",
    ]
    result = detect_ncols(cells)
    assert result.ncols == 3
