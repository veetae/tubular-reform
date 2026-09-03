"""Command-line + clipboard front-end for tubular-reform.

Design note: all clipboard/stdin/stdout side effects live here and are kept thin.
The reshaping decisions happen in the pure modules (:mod:`core`, :mod:`formats`,
:mod:`tokenize`) so they can be tested without a real clipboard or a TTY.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .core import RaggedError, reflow
from .detect import DetectError, detect_ncols
from .formats import FORMATS, render
from .tokenize import tokenize

EXIT_OK = 0
EXIT_RAGGED_STRICT = 1
# 2 is argparse's own usage-error code.
EXIT_NO_INPUT = 3
EXIT_ERROR = 4


# --------------------------------------------------------------------------- #
# Clipboard access (lazy import, graceful degradation)
# --------------------------------------------------------------------------- #
def _clipboard():
    """Return the pyperclip module, or None if it is unusable on this host."""
    try:
        import pyperclip  # noqa: WPS433 (intentional lazy import)
    except Exception:  # pragma: no cover - import guard
        return None
    return pyperclip


def get_clipboard_text() -> str:
    pc = _clipboard()
    if pc is None:
        raise RuntimeError("pyperclip is not installed")
    return pc.paste()


def set_clipboard_text(text: str) -> None:
    pc = _clipboard()
    if pc is None:
        raise RuntimeError("pyperclip is not installed")
    pc.copy(text)


def clipboard_available() -> bool:
    """True only if a clipboard backend actually works (headless boxes fail)."""
    pc = _clipboard()
    if pc is None:
        return False
    try:
        pc.paste()
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tubular-reform",
        description=(
            "Reform flattened 'tubular' text (a table dumped one cell per line, "
            "columns collapsed) back into a real table — without silently "
            "misaligning columns when a row is ragged."
        ),
        epilog=(
            "Examples:\n"
            "  tubular-reform                      # auto-detect cols; clipboard in/out\n"
            "  tubular-reform -c 6                 # clipboard in -> clipboard out\n"
            "  cat dump.txt | tubular-reform -c 4  # stdin -> stdout\n"
            "  tubular-reform -c 3 -f md --header  # markdown, first 3 cells = header\n"
            "  tubular-reform -c 5 --strict        # refuse (exit 1) if ragged\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "-c", "--cols", type=int, default=None, metavar="N",
        help=(
            "number of columns to reflow into (>= 1). "
            "Omit to auto-detect from a repeating type pattern "
            "(text/number/date) or from a consistent tab-delimited row width"
        ),
    )
    p.add_argument(
        "-f", "--format", choices=FORMATS, default="tsv",
        help="output format (default: tsv)",
    )
    p.add_argument(
        "--pad", default="-", metavar="STR",
        help="fill string for a short trailing row (default: '-')",
    )
    p.add_argument(
        "--header", action="store_true",
        help="treat the first N cells as a header row",
    )
    p.add_argument(
        "--strict", action="store_true",
        help="refuse (exit 1) on ragged input instead of pad-and-flag",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--clipboard", action="store_true",
        help="force clipboard in/out (default when stdin is a terminal)",
    )
    src.add_argument(
        "--stdin", action="store_true",
        help="force stdin->stdout (default when input is piped)",
    )
    p.add_argument(
        "--no-strip", dest="strip", action="store_false",
        help="do not strip surrounding whitespace from each cell",
    )
    p.add_argument(
        "-q", "--quiet", action="store_true",
        help="suppress the status summary on stderr",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def _decide_use_clipboard(args, stdin_is_tty: bool) -> bool:
    if args.stdin:
        return False
    if args.clipboard:
        return True
    # Auto: piped input -> stdin mode; interactive terminal -> clipboard mode.
    return stdin_is_tty


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cols is not None and args.cols < 1:
        parser.error("--cols must be >= 1")

    stdin_is_tty = sys.stdin.isatty()
    use_clipboard = _decide_use_clipboard(args, stdin_is_tty)

    def warn(msg: str) -> None:
        if not args.quiet:
            print(msg, file=sys.stderr)

    # ---- read input ---------------------------------------------------------
    text = ""
    if use_clipboard:
        if clipboard_available():
            text = get_clipboard_text()
        else:
            warn(
                "tubular-reform: no working clipboard backend "
                "(install pyperclip and a copy/paste tool). Falling back to stdin."
            )
            use_clipboard = False
            if stdin_is_tty:
                warn("tubular-reform: nothing on stdin either. Pipe input or fix the clipboard.")
                return EXIT_NO_INPUT
            text = sys.stdin.read()
    else:
        text = sys.stdin.read()

    cells = tokenize(text, strip=args.strip)
    if not cells:
        warn("tubular-reform: no input cells; nothing to do.")
        # Empty output, non-fatal.
        if not use_clipboard:
            pass  # nothing to print
        return EXIT_OK

    if args.cols is None:
        try:
            detected = detect_ncols(cells, text=text)
        except DetectError as exc:
            print(f"tubular-reform: {exc}", file=sys.stderr)
            if exc.candidates:
                shown = ", ".join(
                    f"{n} ({s:.2f})" for n, s in exc.candidates[:5]
                )
                print(f"  candidates: {shown}", file=sys.stderr)
            return 2
        ncols = detected.ncols
        warn(f"tubular-reform: {detected.describe()}.")
    else:
        ncols = args.cols

    # ---- reflow -------------------------------------------------------------
    try:
        result = reflow(
            cells, ncols, pad=args.pad, header=args.header, strict=args.strict,
        )
    except RaggedError as exc:
        print(f"tubular-reform: {exc}", file=sys.stderr)
        return EXIT_RAGGED_STRICT
    except ValueError as exc:
        print(f"tubular-reform: {exc}", file=sys.stderr)
        return EXIT_ERROR

    output = render(result, args.format)

    # ---- write output -------------------------------------------------------
    if use_clipboard:
        try:
            set_clipboard_text(output)
        except Exception as exc:  # pragma: no cover - backend write failure
            warn(f"tubular-reform: could not write clipboard ({exc}); printing instead.")
            print(output)
        else:
            warn("tubular-reform: reformed table copied to clipboard.")
            if not args.quiet:
                # Show a preview on stdout in interactive mode.
                print(output)
    else:
        print(output)

    warn(f"tubular-reform: {result.summary()}")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
