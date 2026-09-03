---
name: >-
  cli-anything-workspace
description: >-
  Command-line interface for Tubular Reform - Agent-native Click CLI for [tubular-reform](https://github.com/veetae/tubular-reform). This harness ...
---

# cli-anything-workspace

Agent-native Click CLI for [tubular-reform](https://github.com/veetae/tubular-reform). This harness **calls the real library** (`tubular_reform.tokenize` / `detect_ncols` / `reflow` / `render`) and, in E2E tests, the installed `tubular-reform` console script. It does not reimplement reshape logic.

## Installation

This CLI is installed as part of the cli-anything-tubular_reform package:

```bash
pip install cli-anything-tubular_reform
```

**Prerequisites:**
- Python 3.10+
- tubular_reform must be installed on your system


## Usage

### Basic Commands

```bash
# Show help
cli-anything-tubular_reform --help

# Start interactive REPL mode
cli-anything-tubular_reform

# Create a new project
cli-anything-tubular_reform project new -o project.json

# Run with JSON output (for agent consumption)
cli-anything-tubular_reform --json project info -p project.json
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-tubular_reform
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Cli

Agent-native CLI for tubular-reform (clipboard table reflow).

    Bare invocation enters the REPL. One-shot subcommands support --json.
    Preview producer commands live under `preview`; inspect bundles with
    `cli-hub previews ...` (read-only consumer — not a render path).

| Command | Description |
|---------|-------------|

| `repl` | Interactive REPL (default when no subcommand is given). |



### Project

Create, open, save, and inspect the JSON project.

| Command | Description |
|---------|-------------|

| `new` | Create a new empty project. |

| `open` | Open an existing project JSON file. |

| `save` | Save the current project (and session sidecar). |

| `close` | Drop the current project from memory (does not delete files). |

| `info` | Show current project state. |



### Table

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



### Export

Render through tubular_reform.render (TSV / CSV / Markdown).

| Command | Description |
|---------|-------------|

| `render` | Render the current grid to stdout. |

| `write` | Write rendered output to a file. |



### Session

Undo, redo, and session status.

| Command | Description |
|---------|-------------|

| `status` | Show undo/redo depth and project path. |

| `undo` | Restore the previous project snapshot. |

| `redo` | Re-apply an undone snapshot. |

| `history` | List undo/redo stack depths. |



### Preview

Publish preview-bundle/v1. Inspect with `cli-hub previews ...`.

| Command | Description |
|---------|-------------|

| `recipes` | List preview recipes. |

| `capture` | Render a fresh preview bundle from the current grid. |

| `latest` | Return the newest existing bundle without rendering. |

| `diff` | Publish an immutable TSV comparison bundle. |



### Preview Live

Live preview session (session.json + trajectory.json).

| Command | Description |
|---------|-------------|

| `start` | Start a live session and publish the first bundle. |

| `push` | Publish a new bundle onto the active live session. |

| `status` | Cheap live-session probe for agents (includes trajectory_summary). |

| `stop` | Stop publishing; keep prior bundles and trajectory. |




## Examples


### Create a New Project

Create a new tubular_reform project file.

```bash
cli-anything-tubular_reform project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-tubular_reform --json project new -o myproject.json
```


### Interactive REPL Session

Start an interactive session with undo/redo support.

```bash
cli-anything-tubular_reform
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation
```


### Export Project

Export the project to a final output format.

```bash
cli-anything-tubular_reform --project myproject.json export render output.pdf --overwrite
```


## State Management

The CLI maintains session state with:

- **Undo/Redo**: Up to 50 levels of history
- **Project persistence**: Save/load project state as JSON
- **Session tracking**: Track modifications and changes

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-tubular_reform project info -p project.json

# JSON output for agents
cli-anything-tubular_reform --json project info -p project.json
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Verify outputs exist** after export operations

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0