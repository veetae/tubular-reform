"""Fixture-driven tests: every committed example in ``examples/`` must
reproduce byte-for-byte through the real CLI (stdin mode, subprocess).

These are the public, synthetic fixtures shipped with the repo — if one of
them drifts from the tool's actual output, the docs are lying and this suite
fails.
"""

import os
import subprocess
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SRC = str(Path(__file__).resolve().parent.parent / "src")


def run_cli(input_text: str, *args: str):
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "tubular_reform.cli", "--stdin", *args],
        input=input_text,
        capture_output=True,
        text=True,
        env=env,
    )


def read(name: str) -> str:
    return (EXAMPLES / name).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Happy path, one per output format
# --------------------------------------------------------------------------- #
def test_clean_produce_tsv():
    p = run_cli(read("1-clean-produce.in.txt"), "-c", "3", "-q")
    assert p.returncode == 0
    assert p.stdout == read("1-clean-produce.out.tsv")


def test_trailing_row_csv():
    p = run_cli(read("3-trailing-row.in.txt"), "-c", "2", "-f", "csv", "-q")
    assert p.returncode == 0
    assert p.stdout == read("3-trailing-row.out.csv")


def test_markdown_header_md():
    p = run_cli(
        read("4-markdown-header.in.txt"), "-c", "3", "-f", "md", "--header", "-q"
    )
    assert p.returncode == 0
    assert p.stdout == read("4-markdown-header.out.md")


# --------------------------------------------------------------------------- #
# Auto-detect success (no -c): lab-style text/number/range panel
# --------------------------------------------------------------------------- #
def test_cbc_panel_autodetects_three_columns():
    p = run_cli(read("5-cbc-panel.in.txt"))
    assert p.returncode == 0
    assert p.stdout == read("5-cbc-panel.out.tsv")
    assert "detected 3 column(s)" in p.stderr


# --------------------------------------------------------------------------- #
# Auto-detect refusal: column-major layout has no row-wise type pattern.
# The tool must refuse (exit 2) rather than emit a transposed/misaligned grid.
# --------------------------------------------------------------------------- #
def test_column_major_layout_is_refused():
    p = run_cli(read("6-column-major-refused.in.txt"))
    assert p.returncode == 2
    assert p.stdout == ""
    assert "could not auto-detect column count" in p.stderr
    assert p.stderr == read("6-column-major-refused.stderr.txt")


# --------------------------------------------------------------------------- #
# Ragged rows: padded + flagged on stderr, byte-exact committed outputs
# --------------------------------------------------------------------------- #
def test_ragged_missing_cell_padded_and_flagged():
    p = run_cli(read("2-ragged-missing-cell.in.txt"), "-c", "3")
    assert p.returncode == 0
    assert p.stdout == read("2-ragged-missing-cell.out.tsv")
    assert "RAGGED" in p.stderr
    assert read("2-ragged-missing-cell.stderr.txt").strip() in p.stderr


def test_trailing_row_flag_message():
    p = run_cli(read("3-trailing-row.in.txt"), "-c", "2", "-f", "csv")
    assert p.returncode == 0
    assert read("3-trailing-row.stderr.txt").strip() in p.stderr
