"""cli-anything-tubular-reform — Click CLI + REPL wrapping tubular-reform."""

from __future__ import annotations

import os
import shlex

import click

from cli_anything.tubular_reform import CLI_NAME, SOFTWARE, __version__
from cli_anything.tubular_reform.core import export as export_core
from cli_anything.tubular_reform.core import preview as preview_core
from cli_anything.tubular_reform.core.project import new_project, project_info
from cli_anything.tubular_reform.core.session import Session
from cli_anything.tubular_reform.core import table as table_core
from cli_anything.tubular_reform.utils import tubular_reform_backend as backend
from cli_anything.tubular_reform.utils.output import emit, fail
from cli_anything.tubular_reform.utils.repl_skin import ReplSkin

REPL_COMMANDS = {
    "help": "Show this list",
    "exit": "Leave the REPL",
    "project new|open|save|close|info": "JSON project lifecycle",
    "table load|tokenize|detect|reflow|inspect|set|reform": "Reshape flattened text",
    "export render|write": "TSV / CSV / Markdown via tubular_reform.render",
    "session status|undo|redo|history": "Undo/redo",
    "preview recipes|capture|latest|diff": "Publish preview-bundle/v1",
    "preview live start|push|status|stop": "Live preview session",
}


def _session(ctx: click.Context) -> Session:
    return ctx.obj["session"]


def _autosave(ctx: click.Context) -> None:
    if ctx.obj.get("dry_run"):
        return
    _session(ctx).maybe_autosave(dry_run=False)


def _handle_backend(ctx: click.Context, exc: Exception) -> None:
    if isinstance(exc, backend.DetectFailed):
        extra = {"candidates": exc.candidates} if exc.candidates else None
        fail(ctx, str(exc), code=2, extra=extra)
    if isinstance(exc, backend.RaggedFailed):
        fail(ctx, str(exc), extra={"result": exc.result})
    fail(ctx, str(exc), code=4)


@click.group(invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable JSON on stdout.")
@click.option(
    "-p", "--project", "project_path",
    type=click.Path(),
    default=None,
    help="JSON project file to load / auto-save.",
)
@click.option("--dry-run", is_flag=True, help="Mutate in memory only; do not write project files.")
@click.version_option(__version__, prog_name=CLI_NAME)
@click.pass_context
def cli(ctx: click.Context, as_json: bool, project_path: str | None, dry_run: bool) -> None:
    """Agent-native CLI for tubular-reform (clipboard table reflow).

    Bare invocation enters the REPL. One-shot subcommands support --json.
    Preview producer commands live under `preview`; inspect bundles with
    `cli-hub previews ...` (read-only consumer — not a render path).
    """
    ctx.ensure_object(dict)
    sess = Session()
    if project_path and os.path.isfile(project_path):
        sess.load(project_path)
    elif project_path:
        sess.project["path"] = os.path.abspath(project_path)
        sess.project["name"] = os.path.splitext(os.path.basename(project_path))[0]
    ctx.obj.update(
        json=as_json,
        dry_run=dry_run,
        project_path=project_path,
        session=sess,
    )
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# --------------------------------------------------------------------------- #
# project
# --------------------------------------------------------------------------- #
@cli.group()
def project() -> None:
    """Create, open, save, and inspect the JSON project."""


@project.command("new")
@click.option("-o", "--output", "output_path", type=click.Path(), default=None)
@click.option("--name", default="untitled")
@click.pass_context
def project_new(ctx: click.Context, output_path: str | None, name: str) -> None:
    """Create a new empty project."""
    sess = _session(ctx)
    sess.snapshot()
    sess.project = new_project(name)
    if output_path and not ctx.obj.get("dry_run"):
        sess.save(output_path)
    emit(
        ctx,
        {"action": "project.new", "project": project_info(sess.project)},
        [f"created project {sess.project['name']!r}", f"path: {sess.project.get('path') or '(unsaved)'}"],
    )


@project.command("open")
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def project_open(ctx: click.Context, path: str) -> None:
    """Open an existing project JSON file."""
    sess = _session(ctx)
    sess.snapshot()
    try:
        sess.load(path)
    except Exception as exc:
        fail(ctx, str(exc), code=4)
    emit(
        ctx,
        {"action": "project.open", "project": project_info(sess.project)},
        [f"opened {sess.project['path']}", project_info(sess.project).get("summary") or "empty"],
    )


@project.command("save")
@click.option("-o", "--output", "output_path", type=click.Path(), default=None)
@click.pass_context
def project_save(ctx: click.Context, output_path: str | None) -> None:
    """Save the current project (and session sidecar)."""
    sess = _session(ctx)
    if ctx.obj.get("dry_run"):
        emit(ctx, {"action": "project.save", "dry_run": True, "path": output_path or sess.project.get("path")}, ["dry-run: not written"])
        return
    try:
        dest = sess.save(output_path)
    except Exception as exc:
        fail(ctx, str(exc), code=4)
        return
    emit(ctx, {"action": "project.save", "path": dest}, [f"saved {dest}"])


@project.command("close")
@click.pass_context
def project_close(ctx: click.Context) -> None:
    """Drop the current project from memory (does not delete files)."""
    sess = _session(ctx)
    sess.snapshot()
    sess.project = new_project("untitled")
    emit(ctx, {"action": "project.close"}, ["project closed"])


@project.command("info")
@click.pass_context
def project_info_cmd(ctx: click.Context) -> None:
    """Show current project state."""
    info = project_info(_session(ctx).project)
    emit(
        ctx,
        {"action": "project.info", "project": info},
        [f"{k}: {v}" for k, v in info.items()],
    )


# --------------------------------------------------------------------------- #
# table
# --------------------------------------------------------------------------- #
@cli.group()
def table() -> None:
    """Load flattened text, detect columns, and reflow."""


def _read_input(file: str | None, text: str | None) -> str:
    if text is not None:
        return text
    if file:
        with open(file, encoding="utf-8") as handle:
            return handle.read()
    if not click.get_text_stream("stdin").isatty():
        return click.get_text_stream("stdin").read()
    raise click.UsageError("provide --file, --text, or pipe stdin")


@table.command("load")
@click.option("--file", "file_path", type=click.Path(exists=True), default=None)
@click.option("--text", default=None, help="Literal source text.")
@click.pass_context
def table_load(ctx: click.Context, file_path: str | None, text: str | None) -> None:
    """Load flattened source text into the project."""
    sess = _session(ctx)
    try:
        source = _read_input(file_path, text)
    except click.UsageError as exc:
        fail(ctx, str(exc), code=2)
        return
    sess.snapshot()
    table_core.load_text(sess.project, source)
    _autosave(ctx)
    emit(
        ctx,
        {"action": "table.load", "chars": len(source), "preview": source[:120]},
        [f"loaded {len(source)} character(s)"],
    )


@table.command("tokenize")
@click.pass_context
def table_tokenize(ctx: click.Context) -> None:
    """Tokenize source text via tubular_reform.tokenize."""
    sess = _session(ctx)
    sess.snapshot()
    try:
        cells = table_core.tokenize_project(sess.project)
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    _autosave(ctx)
    emit(
        ctx,
        {"action": "table.tokenize", "cell_count": len(cells), "cells": cells},
        [f"{len(cells)} cell(s)"],
    )


@table.command("detect")
@click.pass_context
def table_detect(ctx: click.Context) -> None:
    """Auto-detect column count (refuses when ambiguous)."""
    sess = _session(ctx)
    sess.snapshot()
    try:
        detected = table_core.detect_project(sess.project)
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    _autosave(ctx)
    emit(
        ctx,
        {"action": "table.detect", "detect": detected},
        [detected["describe"]],
    )


@table.command("reflow")
@click.option("-c", "--cols", type=int, default=None)
@click.option("--header/--no-header", default=None)
@click.option("--strict/--no-strict", default=None)
@click.option("--pad", default=None)
@click.pass_context
def table_reflow(
    ctx: click.Context,
    cols: int | None,
    header: bool | None,
    strict: bool | None,
    pad: str | None,
) -> None:
    """Reflow cells through tubular_reform.reflow."""
    sess = _session(ctx)
    sess.snapshot()
    try:
        table_core.apply_settings(
            sess.project, ncols=cols, header=header, strict=strict, pad=pad,
        )
        result = table_core.reflow_project(sess.project)
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    _autosave(ctx)
    emit(
        ctx,
        {"action": "table.reflow", "result": result},
        [result["summary"]],
    )


@table.command("inspect")
@click.pass_context
def table_inspect(ctx: click.Context) -> None:
    """Inspect cells, detect result, and last reflow."""
    project = _session(ctx).project
    payload = {
        "action": "table.inspect",
        "cell_count": len(project.get("cells") or []),
        "ncols": project.get("ncols"),
        "detect": project.get("detect"),
        "result": project.get("result"),
    }
    result = project.get("result") or {}
    emit(ctx, payload, [result.get("summary") or f"{payload['cell_count']} cell(s), ncols={project.get('ncols')}"])


@table.command("set")
@click.option("-c", "--cols", type=int, default=None)
@click.option("--header/--no-header", default=None)
@click.option("--strict/--no-strict", default=None)
@click.option("--pad", default=None)
@click.option("-f", "--format", "fmt", type=click.Choice(["tsv", "csv", "md"]), default=None)
@click.option("--strip/--no-strip", default=None)
@click.pass_context
def table_set(
    ctx: click.Context,
    cols: int | None,
    header: bool | None,
    strict: bool | None,
    pad: str | None,
    fmt: str | None,
    strip: bool | None,
) -> None:
    """Set reflow / export options without running reflow."""
    sess = _session(ctx)
    sess.snapshot()
    try:
        table_core.apply_settings(
            sess.project,
            ncols=cols,
            header=header,
            strict=strict,
            pad=pad,
            fmt=fmt,
            strip=strip,
        )
    except Exception as exc:
        fail(ctx, str(exc), code=2)
        return
    _autosave(ctx)
    emit(
        ctx,
        {"action": "table.set", "project": project_info(sess.project)},
        [f"ncols={sess.project.get('ncols')} format={sess.project.get('format')}"],
    )


@table.command("reform")
@click.option("--file", "file_path", type=click.Path(exists=True), default=None)
@click.option("--text", default=None)
@click.option("-c", "--cols", type=int, default=None)
@click.option("-f", "--format", "fmt", type=click.Choice(["tsv", "csv", "md"]), default="tsv")
@click.option("--header", is_flag=True)
@click.option("--strict", is_flag=True)
@click.option("--pad", default="-")
@click.option("-o", "--output", "output_path", type=click.Path(), default=None)
@click.option("--overwrite", is_flag=True)
@click.pass_context
def table_reform(
    ctx: click.Context,
    file_path: str | None,
    text: str | None,
    cols: int | None,
    fmt: str,
    header: bool,
    strict: bool,
    pad: str,
    output_path: str | None,
    overwrite: bool,
) -> None:
    """One-shot load → detect/reflow → render (real library)."""
    sess = _session(ctx)
    sess.snapshot()
    try:
        if file_path or text is not None or not click.get_text_stream("stdin").isatty():
            source = _read_input(file_path, text)
            table_core.load_text(sess.project, source)
        table_core.apply_settings(
            sess.project, ncols=cols, header=header, strict=strict, pad=pad, fmt=fmt,
        )
        table_core.tokenize_project(sess.project)
        if sess.project.get("ncols") is None:
            table_core.detect_project(sess.project)
        result = table_core.reflow_project(sess.project)
        written = None
        if output_path:
            written = export_core.write_project(
                sess.project, output_path, fmt, overwrite=overwrite,
            )
        else:
            export_core.render_project(sess.project, fmt)
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    _autosave(ctx)
    payload = {
        "action": "table.reform",
        "result": result,
        "detect": sess.project.get("detect"),
        "format": fmt,
        "output": sess.project.get("output"),
        "output_path": None if written is None else written["output_path"],
        "file_size": None if written is None else written["file_size"],
    }
    human = [result["summary"], sess.project.get("output") or ""]
    emit(ctx, payload, human)


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #
@cli.group()
def export() -> None:
    """Render through tubular_reform.render (TSV / CSV / Markdown)."""


@export.command("render")
@click.option("-f", "--format", "fmt", type=click.Choice(["tsv", "csv", "md"]), default=None)
@click.pass_context
def export_render(ctx: click.Context, fmt: str | None) -> None:
    """Render the current grid to stdout."""
    sess = _session(ctx)
    sess.snapshot()
    try:
        output = export_core.render_project(sess.project, fmt)
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    _autosave(ctx)
    emit(
        ctx,
        {"action": "export.render", "format": sess.project.get("format"), "output": output},
        [output],
    )


@export.command("write")
@click.argument("path", type=click.Path())
@click.option("-f", "--format", "fmt", type=click.Choice(["tsv", "csv", "md"]), default=None)
@click.option("--overwrite", is_flag=True)
@click.pass_context
def export_write(ctx: click.Context, path: str, fmt: str | None, overwrite: bool) -> None:
    """Write rendered output to a file."""
    sess = _session(ctx)
    sess.snapshot()
    if ctx.obj.get("dry_run"):
        output = export_core.render_project(sess.project, fmt)
        emit(
            ctx,
            {"action": "export.write", "dry_run": True, "output_path": path, "output": output},
            [f"dry-run: would write {path}"],
        )
        return
    try:
        written = export_core.write_project(sess.project, path, fmt, overwrite=overwrite)
    except FileExistsError as exc:
        fail(ctx, str(exc), code=4)
        return
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    _autosave(ctx)
    emit(
        ctx,
        {"action": "export.write", **written},
        [f"wrote {written['output_path']} ({written['file_size']} bytes)"],
    )


# --------------------------------------------------------------------------- #
# session
# --------------------------------------------------------------------------- #
@cli.group()
def session() -> None:
    """Undo, redo, and session status."""


@session.command("status")
@click.pass_context
def session_status(ctx: click.Context) -> None:
    """Show undo/redo depth and project path."""
    hist = _session(ctx).history()
    emit(ctx, {"action": "session.status", **hist}, [f"undo={hist['undo_depth']} redo={hist['redo_depth']} path={hist['path']}"])


@session.command("undo")
@click.pass_context
def session_undo(ctx: click.Context) -> None:
    """Restore the previous project snapshot."""
    try:
        _session(ctx).undo()
    except RuntimeError as exc:
        fail(ctx, str(exc), code=4)
        return
    _autosave(ctx)
    emit(ctx, {"action": "session.undo", "project": project_info(_session(ctx).project)}, ["undone"])


@session.command("redo")
@click.pass_context
def session_redo(ctx: click.Context) -> None:
    """Re-apply an undone snapshot."""
    try:
        _session(ctx).redo()
    except RuntimeError as exc:
        fail(ctx, str(exc), code=4)
        return
    _autosave(ctx)
    emit(ctx, {"action": "session.redo", "project": project_info(_session(ctx).project)}, ["redone"])


@session.command("history")
@click.pass_context
def session_history(ctx: click.Context) -> None:
    """List undo/redo stack depths."""
    hist = _session(ctx).history()
    emit(ctx, {"action": "session.history", **hist}, [str(hist)])


# --------------------------------------------------------------------------- #
# preview (producer)
# --------------------------------------------------------------------------- #
@cli.group()
def preview() -> None:
    """Publish preview-bundle/v1. Inspect with `cli-hub previews ...`."""


@preview.command("recipes")
@click.pass_context
def preview_recipes(ctx: click.Context) -> None:
    """List preview recipes."""
    recipes = [
        {"name": name, "description": desc}
        for name, desc in preview_core.RECIPES.items()
    ]
    emit(
        ctx,
        {"action": "preview.recipes", "recipes": recipes, "consumer": "cli-hub previews inspect|html|watch|open"},
        [f"{item['name']}: {item['description']}" for item in recipes]
        + ["inspect published bundles with: cli-hub previews inspect <bundle_dir>"],
    )


@preview.command("capture")
@click.option("--recipe", default="table-md", type=click.Choice(sorted(preview_core.RECIPES)))
@click.option("--force", is_flag=True, help="Ignore cache and write a new bundle.")
@click.pass_context
def preview_capture(ctx: click.Context, recipe: str, force: bool) -> None:
    """Render a fresh preview bundle from the current grid."""
    try:
        payload = preview_core.capture(_session(ctx).project, recipe=recipe, force=force)
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    emit(
        ctx,
        {"action": "preview.capture", **payload},
        [
            f"bundle {payload.get('bundle_id')} ({'cached' if payload.get('cached') else 'new'})",
            f"dir: {payload.get('bundle_dir')}",
            f"inspect: cli-hub previews inspect {payload.get('bundle_dir')}",
        ],
    )


@preview.command("latest")
@click.option("--recipe", default=None)
@click.pass_context
def preview_latest(ctx: click.Context, recipe: str | None) -> None:
    """Return the newest existing bundle without rendering."""
    payload = preview_core.latest(_session(ctx).project, recipe=recipe)
    if payload is None:
        fail(ctx, "no preview bundle found", code=4)
        return
    emit(
        ctx,
        {"action": "preview.latest", **payload},
        [f"latest {payload.get('bundle_id')}", str(payload.get("bundle_dir"))],
    )


@preview.command("diff")
@click.option("--file", "file_path", type=click.Path(exists=True), required=True, help="TSV file to compare against.")
@click.pass_context
def preview_diff(ctx: click.Context, file_path: str) -> None:
    """Publish an immutable TSV comparison bundle."""
    with open(file_path, encoding="utf-8") as handle:
        other = handle.read()
    try:
        payload = preview_core.diff_capture(_session(ctx).project, other)
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    emit(
        ctx,
        {"action": "preview.diff", **payload},
        [f"diff bundle {payload.get('bundle_id')}", str(payload.get("bundle_dir"))],
    )


@preview.group("live")
def preview_live() -> None:
    """Live preview session (session.json + trajectory.json)."""


@preview_live.command("start")
@click.option("--recipe", default="table-md")
@click.pass_context
def preview_live_start(ctx: click.Context, recipe: str) -> None:
    """Start a live session and publish the first bundle."""
    try:
        payload = preview_core.live_start(_session(ctx).project, recipe=recipe)
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    live = payload.get("live") or {}
    emit(
        ctx,
        {"action": "preview.live.start", **payload},
        [f"live session {live.get('session_dir')}", f"bundle {payload.get('bundle_id')}"],
    )


@preview_live.command("push")
@click.option("--recipe", default="table-md")
@click.pass_context
def preview_live_push(ctx: click.Context, recipe: str) -> None:
    """Publish a new bundle onto the active live session."""
    try:
        payload = preview_core.live_push(_session(ctx).project, recipe=recipe)
    except Exception as exc:
        _handle_backend(ctx, exc)
        return
    emit(
        ctx,
        {"action": "preview.live.push", **payload},
        [f"pushed {payload.get('bundle_id')}"],
    )


@preview_live.command("status")
@click.pass_context
def preview_live_status(ctx: click.Context) -> None:
    """Cheap live-session probe for agents (includes trajectory_summary)."""
    payload = preview_core.live_status(_session(ctx).project)
    emit(
        ctx,
        {"action": "preview.live.status", **payload},
        [
            f"active={payload.get('active')} exists={payload.get('exists')}",
            f"bundle={payload.get('bundle_id')}",
            f"trajectory_summary={payload.get('trajectory_summary')}",
        ],
    )


@preview_live.command("stop")
@click.pass_context
def preview_live_stop(ctx: click.Context) -> None:
    """Stop publishing; keep prior bundles and trajectory."""
    payload = preview_core.live_stop(_session(ctx).project)
    emit(
        ctx,
        {"action": "preview.live.stop", **payload},
        [f"stopped live session {payload.get('session_dir')}"],
    )


# --------------------------------------------------------------------------- #
# REPL
# --------------------------------------------------------------------------- #
@cli.command()
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Interactive REPL (default when no subcommand is given)."""
    if ctx.obj.get("json"):
        emit(ctx, {"action": "repl", "error": "REPL is interactive; omit --json or pass a subcommand"}, [])
        ctx.exit(2)
        return
    skin = ReplSkin(SOFTWARE, version=__version__)
    skin.print_banner()
    pt_session = skin.create_prompt_session()
    sess = _session(ctx)
    while True:
        try:
            line = skin.get_input(
                pt_session,
                project_name=sess.project.get("name") or "untitled",
                modified=bool(sess.project.get("modified")),
            )
        except (EOFError, KeyboardInterrupt):
            break
        if line is None:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in {"exit", "quit"}:
            break
        if stripped in {"help", "?"}:
            skin.help(REPL_COMMANDS)
            continue
        try:
            args = shlex.split(stripped)
            cli.main(args, standalone_mode=False, obj=ctx.obj)
        except SystemExit:
            pass
        except Exception as exc:
            skin.error(str(exc))
    skin.print_goodbye()


def main(argv: list[str] | None = None) -> None:
    cli.main(args=argv, prog_name=CLI_NAME)


if __name__ == "__main__":
    main()
