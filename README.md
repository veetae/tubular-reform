# tubular-reform

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
pip install tubular-reform
```

Python 3.10+. The only dependency is [`pyperclip`](https://pypi.org/project/pyperclip/)
for clipboard access. On headless Linux (no clipboard backend) the tool degrades
gracefully to stdin/stdout with a clear message.

## Usage

```bash
# Clipboard in -> clipboard out (the common case): copy the flat text, run:
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
| `-c, --cols N` | Number of columns to reflow into (required, ≥ 1). |
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
- **Safe serialization:** TSV neutralizes embedded tabs/newlines; CSV uses RFC-
  4180 quoting; Markdown escapes `|` and encodes newlines as `<br>`, so a cell's
  content can never break the table structure. When no header is given, Markdown
  synthesizes `Column 1..N` rather than silently promoting your first data row.

## Library use

The core is a pure, deterministic function with no I/O:

```python
from tubular_reform import reflow, render

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
pytest
```

## License

MIT — see [LICENSE](LICENSE).
