# cli-anything-tubular-reform

Agent-native Click CLI for [tubular-reform](https://github.com/veetae/tubular-reform).
This harness **calls the real library** (`tubular_reform.tokenize` / `detect_ncols` /
`reflow` / `render`) and, in E2E tests, the installed `tubular-reform` console
script. It does not reimplement reshape logic.

## Prerequisites

- Python 3.10+
- The real backend: `pip install tubular-reform` (or `pip install -e .` from
  this repo root)
- `click` and `prompt-toolkit` (pulled in by this package)

There is no apt/brew GUI package. If import fails, the backend raises with
install instructions.

## Install

```bash
# from the tubular-reform repo root
pip install -e .
pip install -e ./agent-harness
cli-anything-tubular-reform --help
```

Bare `cli-anything-tubular-reform` enters the REPL. Pass a subcommand for
one-shot use. Agents should pass `--json` before the subcommand.

## Usage

```bash
# Help / REPL
cli-anything-tubular-reform --help
cli-anything-tubular-reform

# One-shot reform (auto-detect columns when the type pattern is clear)
cli-anything-tubular-reform --json table reform --file examples/1-clean-produce.in.txt -f md

# Explicit columns + write
cli-anything-tubular-reform --json table reform --file dump.txt -c 3 -f tsv -o out.tsv --overwrite

# Project session
cli-anything-tubular-reform --json -p table.json project new -o table.json --name produce
cli-anything-tubular-reform --json -p table.json table load --file dump.txt
cli-anything-tubular-reform --json -p table.json table detect
cli-anything-tubular-reform --json -p table.json table reflow
cli-anything-tubular-reform --json -p table.json export write out.md -f md --overwrite

# Preview producer (inspect with cli-hub, do not treat cli-hub as a renderer)
cli-anything-tubular-reform --json -p table.json preview capture --recipe table-md
cli-hub previews inspect <bundle_dir>
cli-anything-tubular-reform --json -p table.json preview live status
```

## Command groups

| Group | Purpose |
|-------|---------|
| `project` | `new` `open` `save` `close` `info` |
| `table` | `load` `tokenize` `detect` `reflow` `inspect` `set` `reform` |
| `export` | `render` `write` via `tubular_reform.render` |
| `session` | `status` `undo` `redo` `history` |
| `preview` | `recipes` `capture` `latest` `diff` and `live start/push/status/stop` |

`--json` is required for agent consumption. `--dry-run` skips writing project
and session files. `--strict` refuses ragged input instead of padding.

Preview artifacts are the real Markdown/TSV render of the current
`ReflowResult`. `cli-hub previews inspect|html|watch|open` is the read-only
consumer.

## Tests

```bash
cd agent-harness
python3 -m pytest cli_anything/tubular_reform/tests -v --tb=no
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/tubular_reform/tests -v -s
```

See `cli_anything/tubular_reform/tests/TEST.md`.
