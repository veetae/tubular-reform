# tubular-reform — CLI-Anything SOP

Agent-native CLI harness for [tubular-reform](https://github.com/veetae/tubular-reform).
This document is the Phase 1–2 analysis and architecture for
`cli-anything-tubular-reform`.

## Phase 1: Codebase Analysis

### Backend engine

`tubular-reform` is already a Python 3.10+ library plus a thin argparse CLI.
There is no GUI. The engine is the pure library in `src/tubular_reform/`:

| Module | Role |
|--------|------|
| `tokenize` | Flatten clipboard/stdin text into cells (tabs and newlines) |
| `detect` | Column auto-detect (tab-width or type-period) with refusal |
| `core.reflow` | Wrap cells to N columns without silent misalignment |
| `formats.render` | Serialize to TSV / CSV / Markdown |

The harness **must call this library** (and, for E2E, the installed
`tubular-reform` console script). It must not reimplement tokenize / detect /
reflow / render.

### Data model

There is no project file format in the upstream tool. State is:

1. **Source text** — flattened paste (one cell per line, or tab-delimited).
2. **Cells** — `list[str]` after tokenize.
3. **ReflowResult** — rectangular grid + raggedness diagnostics.
4. **Rendered string** — TSV, CSV, or Markdown.

The harness persists that as JSON (`schema_version: 1`) so a REPL session and
one-shot subcommands share the same object.

Native “export” formats are the three serializers. Markdown is also the
truthful preview artifact (same `render(result, "md")` path).

### Existing CLI

```text
tubular-reform [-c N] [-f tsv|csv|md] [--header] [--strict] [--pad STR]
               [--clipboard | --stdin] [--quiet]
```

Exit codes: 0 ok, 1 strict-ragged, 2 usage/detect-ambiguous, 3 no input, 4 error.
Status on stderr; table on stdout.

### GUI-to-API map

No GUI. The human loop is: copy flattened text → run CLI → paste table.
Harness command groups wrap that loop so agents can inspect, detect, refuse,
reflow, export, and preview without a clipboard.

### Undo / command pattern

The library is a pure function: one `reflow` call, no undo stack. The harness
adds session snapshots (deep-copy of the JSON project) with undo/redo, matching
the CLI-Anything session contract.

### Non-corruption rule (must preserve)

Never silently slide cells into the wrong columns. Auto-detect **refuses**
rather than guessing. Ragged counts are flagged; `--strict` / `strict=True`
raises instead of padding.

## Phase 2: CLI Architecture

### Interaction model

Both:

- One-shot Click subcommands (`--json` for agents).
- Default REPL (`invoke_without_command=True`) with vendored `ReplSkin`.

### Command groups

| Group | Commands | Domain |
|-------|----------|--------|
| `project` | `new`, `open`, `save`, `close`, `info` | JSON project lifecycle |
| `table` | `load`, `tokenize`, `detect`, `reflow`, `inspect`, `set`, `reform` | Core reshape |
| `export` | `render`, `write` | TSV/CSV/Markdown via real `tubular_reform.render` |
| `session` | `status`, `undo`, `redo`, `history` | Undo/redo + introspection |
| `preview` | `recipes`, `capture`, `latest`, `diff`, `live start/push/status/stop` | preview-bundle/v1 |

### State model

Project JSON (in-memory + file):

- `name`, `path`, `source_text`, `strip`
- `ncols` (int or null), `header`, `pad`, `strict`, `format`
- `cells`, `detect` (method/score or null)
- `result` (grid + issues + summary), `output`
- `modified`

Session sidecar (`<project>.session.json`): undo/redo stacks, exclusive file
lock on save (`_locked_save_json`).

### Output

- Human: ReplSkin tables / status lines.
- Machine: `--json` object with `ok` plus command fields. Errors: `ok: false`.

### Preview SOP

Recipes (`table-md`, `table-html`, `table-tsv`) serialize the **current
ReflowResult** through the real library (Markdown/TSV) or an HTML view of the
same grid (escaped cells; not a second reshape). Bundles follow
`preview-bundle/v1`. Live preview keeps `session.json` (head) and
`trajectory.json` (append-only). Agents inspect with `cli-hub previews ...`
(consumer); this harness only publishes.

### Packaging

PEP 420 namespace `cli_anything.tubular_reform`. Console script
`cli-anything-tubular-reform`. Hard dependency: the `tubular-reform` library
(same repo / `pip install tubular-reform`).
