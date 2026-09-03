"""Tests for the CLI + clipboard front-end.

The stdin->stdout path is exercised via a real subprocess (end-to-end). The
clipboard path is exercised in-process with the clipboard functions monkey-
patched, so no real system clipboard is required.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tubular_reform import cli

SRC = str(Path(__file__).resolve().parent.parent / "src")


def run_cli(input_text: str, *args: str):
    """Run the CLI as a subprocess in stdin mode; return CompletedProcess."""
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "tubular_reform.cli", "--stdin", *args],
        input=input_text,
        capture_output=True,
        text=True,
        env=env,
    )


# --------------------------------------------------------------------------- #
# stdin -> stdout end-to-end
# --------------------------------------------------------------------------- #
def test_stdin_tsv_default():
    p = run_cli("a\nb\nc\nd\ne\nf\n", "-c", "3")
    assert p.returncode == 0
    assert p.stdout.rstrip("\n") == "a\tb\tc\nd\te\tf"


def test_stdin_csv():
    p = run_cli("a\nb\nc\nd\n", "-c", "2", "-f", "csv")
    assert p.returncode == 0
    assert p.stdout.rstrip("\n") == "a,b\nc,d"


def test_stdin_markdown():
    p = run_cli("a\nb\nc\nd\n", "-c", "2", "-f", "md")
    assert p.returncode == 0
    assert p.stdout.splitlines()[0].startswith("| Column 1")


def test_ragged_default_pads_and_flags_on_stderr():
    p = run_cli("a\nb\nc\nd\ne\n", "-c", "3")  # 5 cells / 3 cols -> ragged
    assert p.returncode == 0
    # Padded output present on stdout...
    assert "d\te\t-" in p.stdout
    # ...and the raggedness is reported (not hidden) on stderr.
    assert "RAGGED" in p.stderr


def test_strict_refuses_with_exit_1():
    p = run_cli("a\nb\nc\nd\ne\n", "-c", "3", "--strict")
    assert p.returncode == 1
    assert "not a clean multiple" in p.stderr
    # Nothing corrupted printed to stdout.
    assert p.stdout.strip() == ""


def test_custom_pad():
    p = run_cli("a\nb\nc\n", "-c", "2", "--pad", "NA")
    assert p.returncode == 0
    assert "c\tNA" in p.stdout


def test_header_flag():
    p = run_cli("Name\nQty\napple\n3\n", "-c", "2", "--header")
    assert p.returncode == 0
    assert p.stdout.splitlines()[0] == "Name\tQty"


def test_no_strip_flag_keeps_whitespace():
    p = run_cli("  a  \nb\nc\nd\n", "-c", "2", "--no-strip", "-f", "csv")
    assert p.returncode == 0
    # Leading/trailing spaces preserved verbatim (csv only quotes on
    # delimiter/quote/newline, not on spaces).
    assert p.stdout.startswith("  a  ,b")


def test_empty_input_is_noop_exit_0():
    p = run_cli("", "-c", "3")
    assert p.returncode == 0
    assert p.stdout.strip() == ""


def test_missing_cols_auto_detects_mixed_types():
    p = run_cli("Apple\n3\n0.50\nBanana\n6\n0.25\n")  # no -c
    assert p.returncode == 0
    assert p.stdout.rstrip("\n") == "Apple\t3\t0.50\nBanana\t6\t0.25"
    assert "detected 3 column" in p.stderr


def test_missing_cols_without_signal_is_usage_error():
    p = run_cli("a\nb\n")  # no -c, all text, too few cells
    assert p.returncode == 2
    assert "auto-detect" in p.stderr.lower() or "pass -c" in p.stderr.lower()


def test_auto_detect_all_text_refuses():
    p = run_cli("a\nb\nc\nd\ne\nf\n")
    assert p.returncode == 2
    assert "pass -c" in p.stderr.lower()


def test_auto_detect_tab_width():
    p = run_cli("a\tb\tc\nd\te\tf\n")
    assert p.returncode == 0
    assert p.stdout.rstrip("\n") == "a\tb\tc\nd\te\tf"
    assert "tab width" in p.stderr


def test_auto_detect_with_header_flag():
    p = run_cli(
        "Name\nQty\nPrice\nApple\n3\n0.50\nBanana\n6\n0.25\n",
        "--header",
    )
    assert p.returncode == 0
    assert p.stdout.splitlines()[0] == "Name\tQty\tPrice"
    assert "Apple\t3\t0.50" in p.stdout


def test_explicit_cols_overrides_auto_detect():
    # Mixed-type 3-col data forced into 2 columns — user said 2, so 2.
    p = run_cli("Apple\n3\n0.50\nBanana\n6\n0.25\n", "-c", "2")
    assert p.returncode == 0
    assert p.stdout.splitlines()[0] == "Apple\t3"


def test_cols_zero_rejected():
    p = run_cli("a\nb\n", "-c", "0")
    assert p.returncode == 2


def test_version():
    p = run_cli("", "--version")
    assert p.returncode == 0
    assert "tubular-reform" in p.stdout


def test_help_mentions_examples():
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    p = subprocess.run(
        [sys.executable, "-m", "tubular_reform.cli", "--help"],
        capture_output=True, text=True, env=env,
    )
    assert p.returncode == 0
    assert "Examples" in p.stdout
    assert "clipboard" in p.stdout.lower()
    assert "auto-detect" in p.stdout.lower()


def test_quiet_suppresses_summary():
    p = run_cli("a\nb\nc\n", "-c", "2", "--quiet")
    assert p.returncode == 0
    assert p.stderr.strip() == ""


def test_tab_delimited_reflow_end_to_end():
    # A 2-wide table pasted but wanted at 3 wide -> flatten and re-flow.
    p = run_cli("a\tb\nc\td\ne\tf\n", "-c", "3")
    assert p.returncode == 0
    assert p.stdout.rstrip("\n") == "a\tb\tc\nd\te\tf"


def test_forced_clipboard_without_backend_falls_back_to_stdin():
    # On a headless host (no clipboard backend) --clipboard should degrade to
    # stdin/stdout rather than crash. Skip when this machine has a live
    # clipboard: the CLI then reads the clipboard instead of the piped stdin.
    if cli.clipboard_available():
        pytest.skip("host has a working clipboard backend")
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    p = subprocess.run(
        [sys.executable, "-m", "tubular_reform.cli", "--clipboard", "-c", "2"],
        input="a\nb\nc\nd\n", capture_output=True, text=True, env=env,
    )
    assert p.returncode == 0
    assert "a\tb" in p.stdout and "c\td" in p.stdout


# --------------------------------------------------------------------------- #
# Clipboard path (in-process, monkeypatched — no real clipboard needed)
# --------------------------------------------------------------------------- #
class FakeClipboard:
    def __init__(self, text=""):
        self.text = text

    def paste(self):
        return self.text

    def copy(self, text):
        self.text = text


@pytest.fixture
def fake_clip(monkeypatch):
    clip = FakeClipboard()
    monkeypatch.setattr(cli, "clipboard_available", lambda: True)
    monkeypatch.setattr(cli, "get_clipboard_text", lambda: clip.text)
    monkeypatch.setattr(cli, "set_clipboard_text", lambda t: setattr(clip, "text", t))
    # Force clipboard mode by pretending stdin is a TTY.
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    return clip


def test_clipboard_roundtrip(fake_clip, capsys):
    fake_clip.text = "a\nb\nc\nd\ne\nf\n"
    rc = cli.main(["-c", "3"])
    assert rc == 0
    assert fake_clip.text == "a\tb\tc\nd\te\tf"
    err = capsys.readouterr().err
    assert "copied to clipboard" in err


def test_clipboard_ragged_still_copies_and_warns(fake_clip, capsys):
    fake_clip.text = "a\nb\nc\nd\ne\n"  # 5 / 3 -> ragged
    rc = cli.main(["-c", "3"])
    assert rc == 0
    assert "-" in fake_clip.text  # padded
    assert "RAGGED" in capsys.readouterr().err


def test_clipboard_strict_refuses_does_not_overwrite(fake_clip, capsys):
    fake_clip.text = "a\nb\nc\nd\ne\n"
    rc = cli.main(["-c", "3", "--strict"])
    assert rc == cli.EXIT_RAGGED_STRICT
    # Clipboard is left untouched on refusal.
    assert fake_clip.text == "a\nb\nc\nd\ne\n"


def test_clipboard_unavailable_with_tty_reports_no_input(monkeypatch, capsys):
    def _no_clip():
        raise RuntimeError("pyperclip is not installed")

    monkeypatch.setattr(cli, "get_clipboard_text", _no_clip)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    rc = cli.main(["-c", "3", "--clipboard"])
    assert rc == cli.EXIT_NO_INPUT
    assert "clipboard" in capsys.readouterr().err.lower()


def test_clipboard_auto_detects_cols(fake_clip, capsys):
    fake_clip.text = "Apple\n3\n0.50\nBanana\n6\n0.25\n"
    rc = cli.main([])
    assert rc == 0
    assert fake_clip.text == "Apple\t3\t0.50\nBanana\t6\t0.25"
    err = capsys.readouterr().err
    assert "detected 3 column" in err


def test_decide_use_clipboard_logic():
    parser = cli.build_parser()
    # Auto + piped stdin -> stdin mode. -c is optional.
    args = parser.parse_args(["-c", "3"])
    assert cli._decide_use_clipboard(args, stdin_is_tty=False) is False
    # Auto + interactive -> clipboard mode.
    assert cli._decide_use_clipboard(args, stdin_is_tty=True) is True
    args = parser.parse_args([])
    assert args.cols is None
    assert cli._decide_use_clipboard(args, stdin_is_tty=True) is True
    # Explicit --stdin always stdin.
    args = parser.parse_args(["-c", "3", "--stdin"])
    assert cli._decide_use_clipboard(args, stdin_is_tty=True) is False
    # Explicit --clipboard always clipboard.
    args = parser.parse_args(["-c", "3", "--clipboard"])
    assert cli._decide_use_clipboard(args, stdin_is_tty=False) is True
