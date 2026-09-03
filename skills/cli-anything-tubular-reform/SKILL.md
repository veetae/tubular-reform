---
name: "cli-anything-tubular-reform"
description: "Agent-native CLI for tubular-reform: reflow flattened one-cell-per-line text into TSV/CSV/Markdown without silently misaligning columns. Use --json."
---

# cli-anything-tubular-reform

Agent-native Click CLI for [tubular-reform](https://github.com/veetae/tubular-reform). This harness **calls the real library** (`tubular_reform.tokenize` / `detect_ncols` / `reflow` / `render`) and, in E2E tests, the installed `tubular-reform` console script. It does not reimplement reshape logic.

## Installation

```bash
pip install -e .                 # the tubular-reform library (repo root)
pip install -e ./agent-harness   # this harness
cli-anything-tubular-reform --help
```

**Prerequisites:**
- Python 3.10+
- The real `tubular-reform` backend on PATH / importable (`pip install tubular-reform` or editable install from this repo)

## Usage

```bash
# Show help
cli-anything-tubular-reform --help

# Start interactive REPL mode
cli-anything-tubular-reform

# One-shot reform with JSON (agents)
cli-anything-tubular-reform --json table reform --file dump.txt -c 3 -f md

# Create a new project
cli-anything-tubular-reform --json project new -o project.json --name produce
```

`--json` must come **before** the subcommand.

## Command Groups

### project

Create, open, save, and inspect the JSON project.

| Command | Description |
|---------|-------------|
| `new` | Create a new empty project. |
| `open` | Open an existing project JSON file. |
| `save` | Save the current project (and session sidecar). |
| `close` | Drop the current project from memory (does not delete files). |
| `info` | Show current project state. |

### table

Load flattened text, detect columns, and reflow.

| Command | Description |
|---------|-------------|
| `load` | Load flattened source text into the project. |
| `tokenize` | Tokenize source text via tubular_reform.tokenize. |
| `detect` | Auto-detect column count (refuses when ambiguous). |
| `reflow` | Reflow cells through tubular_reform.reflow. |
| `inspect` | Inspect cells, detect result, and last reflow. |
| `set` | Set reflow / export options without running reflow. |
| `reform` | One-shot load → detect/reflow → render (real library). |

### export

Render through tubular_reform.render (TSV / CSV / Markdown).

| Command | Description |
|---------|-------------|
| `render` | Render the current grid to stdout. |
| `write` | Write rendered output to a file. |

### session

Undo, redo, and session status.

| Command | Description |
|---------|-------------|
| `status` | Show undo/redo depth and project path. |
| `undo` | Restore the previous project snapshot. |
| `redo` | Re-apply an undone snapshot. |
| `history` | List undo/redo stack depths. |

### preview

Publish `preview-bundle/v1`. **Producer only.** Inspect with `cli-hub previews ...` (read-only consumer — not a render path).

| Command | Description |
|---------|-------------|
| `recipes` | List preview recipes (`table-md`, `table-tsv`, `table-html`). |
| `capture` | Render a fresh preview bundle from the current grid. |
| `latest` | Return the newest existing bundle without rendering. |
| `diff` | Publish an immutable TSV comparison bundle. |

### preview live

Live preview session (`session.json` + `trajectory.json`).

| Command | Description |
|---------|-------------|
| `start` | Start a live session and publish the first bundle. |
| `push` | Publish a new bundle onto an active live session. |
| `status` | Cheap probe; JSON includes `trajectory_summary`. |
| `stop` | Stop publishing; keep prior bundles and trajectory. |

## Examples

### Produce list → Markdown

```bash
cli-anything-tubular-reform --json table reform \
  --file examples/1-clean-produce.in.txt -c 3 -f md -o produce.md --overwrite
```

### Auto-detect, then inspect

```bash
cli-anything-tubular-reform --json -p table.json project new -o table.json --name countries
cli-anything-tubular-reform --json -p table.json table load --file examples/4-markdown-header.in.txt
cli-anything-tubular-reform --json -p table.json table detect
cli-anything-tubular-reform --json -p table.json table reflow --header
cli-anything-tubular-reform --json -p table.json export write out.md -f md --overwrite
```

### Preview producer + cli-hub consumer

```bash
cli-anything-tubular-reform --json -p table.json preview capture --recipe table-md
cli-hub previews inspect <bundle_dir>
cli-anything-tubular-reform --json -p table.json preview live status
```

Truthful previews: Markdown/TSV artifacts are `tubular_reform.render` of the current `ReflowResult`. HTML is the same grid with escaped cells.

## For AI Agents

1. **Always pass `--json` before the subcommand**
2. **Exit codes:** 0 ok, 2 detect/usage refusal, 1/4 errors (`ok: false` in JSON)
3. **Do not guess columns** when `table detect` fails — pass `-c N`
4. **Ragged input:** default pads-and-flags; `--strict` refuses (no table written)
5. **Use absolute paths** for `--file`, `-p`, and `-o`
6. **Verify export files** exist and size > 0
7. **Preview:** publish with this CLI, inspect with `cli-hub previews ...`
8. **`preview live status --json`** is the cheap introspection call between mutations (`trajectory_summary`)

## Version

1.0.0
