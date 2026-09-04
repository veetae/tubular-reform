# tubular-reform

[![CI](https://github.com/veetae/tubular-reform/actions/workflows/ci.yml/badge.svg)](https://github.com/veetae/tubular-reform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Reform flattened "tubular" text back into a real table — without silently
misaligning columns.**

Sometimes you copy a table and it arrives *flattened*: every cell on its own
line, the column structure gone. Copying from PDFs, some enterprise/EHR web UIs,
terminal dumps, and scraped pages all do this. You get this —

```
Apple
3
0.50
Banana
6
0.25
```

— when you wanted this:

| Apple  | 3 | 0.50 |
|--------|---|------|
| Banana | 6 | 0.25 |

`tubular-reform` puts the columns back. You tell it how many columns the table
has; it reflows the flat list into rows and writes the result straight back to
your clipboard (or to stdout).

## Why this needs to exist (the gap)

Re-wrapping a flat list every _N_ cells is a one-liner, so nobody packages it.
But that one-liner has a **silent-corruption bug**: if a single row is missing a
cell — omitted entirely, not left blank — every value after the gap slides one
position left. The table still *looks* rectangular, so you never notice it's
wrong. In a spreadsheet, an EHR, or a report, that is a genuinely dangerous
failure mode.

**That non-corruption guarantee is the whole point of this tool.** When the cell
count isn't a clean multiple of your column count, `tubular-reform` does **not**
hand you a plausible-looking, wrongly-aligned grid. It:

- **detects** the mismatch,
- **reports** exactly which row is short (or long) and by how much,
- and either **pads-and-flags** the short trailing row (default) or **refuses**
  with a clear message (`--strict`).

It never shifts your data into the wrong columns behind your back.

> Honest scope: once a table is fully flattened to one-cell-per-line, the
> information about *where* a missing middle cell used to be is genuinely gone —
> no tool can recover it from the flat list alone. What `tubular-reform`
> guarantees is that it will **never silently pretend the result is fine**: a
> ragged count is always surfaced loudly so you can inspect or refuse. Missing
> cells at the **end** of the data it localizes exactly.

## Install

```bash
pip install tubular-reform      # or, isolated on your PATH:
pipx install tubular-reform
```

Python 3.10+. The only dependency is [`pyperclip`](https://pypi.org/project/pyperclip/)
for clipboard access. On headless Linux (no clipboard backend) the tool degrades
gracefully to stdin/stdout with a clear message.

Want a single-file Windows `.exe` (no Python on the target machine)? Build one
with PyInstaller — see [Windows: one-click launcher](#windows-one-click-launcher-optional).

## Usage

```bash
# Clipboard in -> clipboard out. If the cells alternate types
# (name / number / number, …) you can omit -c:
tubular-reform

# Same, but you already know it is 6 columns:
tubular-reform -c 6

# Piped stdin -> stdout:
cat dump.txt | tubular-reform -c 4

# Markdown output, first 3 cells become the header:
tubular-reform -c 3 --format md --header

# Refuse (exit code 1) instead of padding when the input is ragged:
tubular-reform -c 5 --strict
```

### Before / after

Input (clipboard or stdin), 9 cells:

```
Apple
3
0.50
Banana
6
0.25
Cherry
12
2.00
```

`tubular-reform -c 3` →

```
Apple	3	0.50
Banana	6	0.25
Cherry	12	2.00
```

with `-f md` →

```
| Column 1 | Column 2 | Column 3 |
| -------- | -------- | -------- |
| Apple    | 3        | 0.50     |
| Banana   | 6        | 0.25     |
| Cherry   | 12       | 2.00     |
```

### A realistic example: a flattened lab-style panel

Copy a results table from a PDF or a web viewer and the clipboard often arrives
as a flat vertical mess (values below are **synthetic**, invented for the demo):

```
WBC
6.4
4.0-11.0
HGB
14.2
13.5-17.5
PLT
212
150-400
MCV
88.1
80-100
```

`tubular-reform` (no `-c` needed — the analyte / value / range type pattern
auto-detects as 3 columns) →

```
WBC	6.4	4.0-11.0
HGB	14.2	13.5-17.5
PLT	212	150-400
MCV	88.1	80-100
```

…already back on your clipboard, ready to paste into a spreadsheet.

### The ragged case (the reason to use this)

Ten cells into 3 columns — one cell is missing somewhere:

```bash
$ printf 'a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n' | tubular-reform -c 3
a	b	c
d	e	f
g	h	i
j	-	-
# stderr:
# tubular-reform: 4 row(s) x 3 col(s) from 10 cell(s) — RAGGED:
#   row 4: has 1 of 3 cells (short by 2). Padded with '-'.
```

Same input with `--strict` prints the same diagnosis and **exits non-zero
without emitting a table** — nothing downstream ever consumes a misaligned grid.

## Options

| Flag | Meaning |
|------|---------|
| `-c, --cols N` | Number of columns to reflow into (≥ 1). Omit to auto-detect from a repeating type pattern (text / number / date) or from a consistent tab-delimited row width. All-text (or all-number) lists have no type signal, so they still need `-c`. |
| `-f, --format {tsv,csv,md}` | Output format. Default `tsv` (pastes into spreadsheets). |
| `--pad STR` | Fill for a short trailing row. Default `-`. |
| `--header` | Treat the first `N` cells as a header row. |
| `--strict` | Refuse (exit 1) on ragged input instead of pad-and-flag. |
| `--clipboard` | Force clipboard in/out (default when stdin is a terminal). |
| `--stdin` | Force stdin→stdout (default when input is piped). |
| `--no-strip` | Keep surrounding whitespace on each cell. |
| `-q, --quiet` | Suppress the status/flag summary on stderr. |

Status and raggedness messages go to **stderr**, so piping stdout stays clean.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (including ragged input that was padded-and-flagged). |
| `1` | Ragged input refused under `--strict`. |
| `2` | Usage error (bad/missing arguments). |
| `3` | No input available (empty clipboard on a terminal, nothing piped). |
| `4` | Other error. |

## Behavior details

- **Blank cells are preserved.** A blank line becomes an empty cell that keeps
  its column position — blanks are never dropped, because dropping one would
  shift the row.
- **Line endings** (LF / CRLF / CR) are normalized; one trailing newline is
  treated as an artifact, interior blank lines are kept.
- **Already-delimited input** (a table that was pasted with tabs but at the wrong
  width) is flattened and re-flowed to the column count you ask for.
- **Unicode** passes through untouched.
- **Column auto-detect:** omitting `-c` looks for a repeating cell-type
  pattern (text / number / date) across at least two rows, or a unanimous
  tab-delimited row width. If the list is all text (or all numbers), or two
  widths score the same, it **refuses** and asks for `-c` rather than guessing.
  An explicit `-c` always wins.
- **Safe serialization:** TSV neutralizes embedded tabs/newlines; CSV uses RFC-
  4180 quoting; Markdown escapes `|` and encodes newlines as `<br>`, so a cell's
  content can never break the table structure. When no header is given, Markdown
  synthesizes `Column 1..N` rather than silently promoting your first data row.

## Windows: one-click launcher (optional)

The everyday flow — copy table, run tool, paste result — works nicely as a
double-clickable desktop icon that never flashes a console window.

1. **Freeze a single-file exe** (once, on any Windows box with Python):

   ```bat
   pip install tubular-reform pyinstaller
   echo from tubular_reform.cli import main; raise SystemExit(main()) > tr_entry.py
   pyinstaller --onefile --name tubular-reform tr_entry.py
   ```

   `dist\tubular-reform.exe` is now standalone — copy it anywhere (no Python
   needed on the target machine). If Python/pip is fine on the machine, skip
   this step and use the installed `tubular-reform` command directly.

2. **Hide the console** with a two-line `.vbs` wrapper, e.g.
   `tubular-reform.vbs` next to the exe:

   ```vb
   Set sh = CreateObject("Wscript.Shell")
   sh.Run """C:\path\to\tubular-reform.exe"" -q", 0, False
   ```

   (`0` = no window. Add flags like `-c 6` or `-f md` inside the quoted
   command as needed.)

3. **Desktop shortcut**: right-click the `.vbs` → *Send to → Desktop
   (create shortcut)*, give it a name/icon. From then on: copy the flattened
   table, double-click the icon, paste the fixed table.

## Limitations (honest scope)

- **Column-major / vertically-stacked layouts are not reconstructed yet.** If
  the clipboard arrives as *all of column 1, then all of column 2* (rather
  than row-by-row), no row-wise pattern exists; auto-detect refuses rather
  than emitting a transposed grid (see `examples/6-column-major-refused`).
  Reconstructing column-major input is on the roadmap.
- **OCR-mangled input is out of scope.** Merged or split cells, garbled
  glyphs, and lost line breaks from OCR can't be repaired by reflowing —
  garbage in stays garbage, just rectangular.
- **Auto-detect needs a type signal.** All-text (or all-number) lists carry no
  repeating pattern, so they still require `-c` — refusing to guess is the
  design, not a bug.

## Library use

The core is a pure, deterministic function with no I/O:

```python
from tubular_reform import reflow, render, detect_ncols

detect_ncols(["Apple", "3", "0.50", "Banana", "6", "0.25"]).ncols  # 3

result = reflow(["a", "b", "c", "d", "e"], ncols=3)   # ragged
result.is_clean          # False
result.remainder         # 2
result.issues[0].describe()   # 'row 2: has 2 of 3 cells (short by 1)'
result.rows              # [['a','b','c'], ['d','e','-']]  (padded + flagged)
print(render(result, "md"))

# Strict mode raises instead of guessing:
from tubular_reform import RaggedError
reflow(["a", "b", "c", "d", "e"], ncols=3, strict=True)   # -> RaggedError
```

## Prior art

Tools exist at both ends of this problem, but none is a clipboard-native,
ragged-safe, column-count-driven reflow:

- **Excel `WRAPROWS` / `pandas` reshape / NumPy `reshape`** wrap a flat vector to
  a width, but on a ragged count they either error opaquely (`cannot reshape
  array of size N`) or pad without telling you *which* row is wrong — and they
  need a spreadsheet or a Python session, not your clipboard.
- **Online "list → columns / → Markdown table" converters** (ListShift,
  codeshack, etc.) do the trivial wrap in a browser tab with no integrity check;
  a missing cell silently misaligns.
- **`rs` (BSD reshape), `column`, `pr -t`, `colcise`** are column *formatting* /
  alignment tools; `rs` can reshape but pads/truncates silently.
- **`csvkit`, `viewcsv`, CSV-repair tools** do handle ragged rows — but they
  assume you already have *delimited* rows and just fix widths; they don't
  address the fully-flattened one-cell-per-line case, and they aren't a clipboard
  round-trip.

So the hypothesis holds, refined: it isn't that nothing touches raggedness — CSV
repair tools do, for already-delimited data. It's that the specific, everyday
task — *take a table that got flattened to one value per line on my clipboard,
put it back to N columns, and never lie to me about alignment* — falls in the gap
between "too trivial to package" and the "repair a delimited CSV" tools, and
`tubular-reform` fills it.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

Issues and small PRs welcome. Please run `ruff check .` and `pytest` (both run
in CI) before submitting.

An experimental interactive/agent harness for this tool, built with
[CLI-Anything](https://github.com/HKUDS/CLI-Anything), lives on the
`cursor/cli-anything-harness-fd9d` branch; it is not part of the released
package.

## License

MIT — see [LICENSE](LICENSE).
