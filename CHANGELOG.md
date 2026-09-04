# Changelog

All notable changes to `tubular-reform` are documented here.

## [0.2.0] — 2026-09

The clipboard-native facelift.

- **Column auto-detect** — `-c` is now optional. The column count is inferred
  from a repeating cell-type pattern (text / number / date) or a unanimous
  tab-delimited row width. When no unique, high-confidence width exists the
  tool **refuses loudly** (exit 2) instead of guessing — by design.
- **Clipboard-native mode** — with no piped input, the clipboard is read and
  the reformed table is written straight back to it (`--clipboard` /
  `--stdin` force either side). Headless boxes degrade gracefully to
  stdin/stdout.
- Output formats hardened: `tsv` (default), `csv` (RFC-4180 quoting), `md`
  (pipe escaping, `<br>` newlines, synthesized `Column 1..N` headers).
- Tokenize / reflow / Markdown hot paths tightened.

## [0.1.0] — 2026-09

Initial release: ragged-safe reflow of flattened one-cell-per-line text into
N columns, with pad-and-flag or `--strict` refusal — never a silently
misaligned table.
