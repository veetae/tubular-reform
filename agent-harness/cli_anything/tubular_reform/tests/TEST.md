# TEST.md — cli-anything-tubular-reform

Test plan written **before** test code (Phase 4). Results are appended in Phase 6.

## Test Inventory Plan

| File | Planned | Kind |
|------|---------|------|
| `test_core.py` | 28 | Unit: project, session, table, export, backend wrappers |
| `test_full_e2e.py` | 18 | Real files + native `tubular-reform` CLI + installed harness subprocess |

## Unit Test Plan (`test_core.py`)

### `project.py`

- `new_project` defaults (empty cells, ncols None, format tsv)
- `save_project` / `load_project` round-trip
- `project_info` reflects cell_count after tokenize
- load of non-object JSON raises

### `session.py`

- snapshot + undo restores previous source_text
- redo restores the undone state
- undo on empty stack raises
- redo on empty stack raises
- `_locked_save_json` writes valid JSON (sidecar after save)
- undo stack capped at MAX_UNDO (spot-check depth, not 50 inserts if slow — insert 3)

### `table.py` / backend

- tokenize uses real `tubular_reform.tokenize` (produce list → 12 cells)
- detect uses real `detect_ncols` (produce list → 3, type-period)
- detect all-text refuses (`DetectFailed`)
- reflow clean 3-col produce list
- reflow ragged pads and sets is_clean False
- reflow strict raises `RaggedFailed`
- `apply_settings` rejects ncols < 1

### `export.py`

- `render_project` TSV matches library `render`
- `write_project` creates file size > 0
- `write_project` without overwrite raises FileExistsError

### `preview.py` (synthetic project, tmp dir)

- recipes dict contains table-md / table-tsv / table-html
- capture writes manifest.json protocol_version preview-bundle/v1
- hero artifact table.md equals library markdown render
- latest returns the capture just written
- unknown recipe raises

## E2E Test Plan (`test_full_e2e.py`)

Real inputs: repo `examples/1-clean-produce.in.txt`,
`examples/2-ragged-missing-cell.in.txt`,
`examples/4-markdown-header.in.txt`.

### Workflows

1. **Produce list → Markdown** — harness `table reform --file ... -c 3 -f md -o out.md`.
   File exists, contains `| Apple |`, size > 0. Print artifact path.
2. **Native CLI parity** — same input through `tubular-reform --stdin -c 3 -f tsv`
   vs harness TSV; strings match (real software, not a second implementation).
3. **Ragged pad** — example 2 with `-c 3`; JSON `is_clean` is false; TSV contains pad.
4. **Ragged strict** — `--strict` non-zero; no output file.
5. **Header markdown** — example 4 `--header -f md`; first row is Country/Capital/Population.
6. **Auto-detect** — example 4 without `-c`; detect ncols 3.
7. **Project save/open** — new → load → reflow → save → open in a second process.
8. **Undo** — load A, load B, undo, inspect source of A.
9. **Preview capture** — reform then `preview capture`; bundle has table.md matching render;
   `preview latest` returns same bundle_id.
10. **Preview live** — start, status `--json` includes `trajectory_summary`, push, stop
    sets active false.
11. **Preview diff** — compare current TSV to a tweaked file; bundle_kind diff.
12. **CLI subprocess** — `_resolve_cli("cli-anything-tubular-reform")` `--help`,
    `--json project info`, full reform workflow. Do not set cwd.
13. **Dry-run write** — export write --dry-run does not create the file.

### Output verification

- TSV: tab-separated, expected cell values in column 0
- Markdown: header rule row `---`
- Bundle: `manifest.json` + `summary.json` + artifacts with size > 0
- Native CLI stdout equals harness TSV

### Realistic workflow scenarios

- **Clipboard-style produce list** — flatten → detect/reflow → markdown (spreadsheet paste)
- **Ragged EHR-style dump** — missing price cell → pad-and-flag, never silent slide
- **Country table with header** — `--header` markdown for docs
- **Iterative refine** — undo after a bad `-c`, redo
- **Preview for agents** — capture + live status JSON between mutations

## Phase 6 results

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1
collected 38 items

cli_anything/tubular_reform/tests/test_core.py ........................   [ 60%]
cli_anything/tubular_reform/tests/test_full_e2e.py ..............         [100%]

============================== 38 passed in 1.16s ==============================
```

**Summary:** 38 passed, 0 failed. Library suite at repo root: 97 passed, 1 skipped (clipboard backend present).

**Force-installed subprocess:** `CLI_ANYTHING_FORCE_INSTALLED=1` used `/home/ubuntu/.local/bin/cli-anything-tubular-reform` (`[_resolve_cli] Using installed command`).

**Coverage notes:** Unit tests cover project/session/table/export/preview against the real `tubular_reform` library. E2E uses repo `examples/*.in.txt`, native `tubular-reform` TSV parity, ragged strict refusal, preview-bundle/v1, live `trajectory_summary`, and installed-command subprocess tests. Clipboard round-trip is not exercised in the harness (headless); the library CLI test covers that when a backend exists.
