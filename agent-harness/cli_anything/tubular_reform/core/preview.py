"""Preview producer: preview-bundle/v1 from the real reflowed grid."""

from __future__ import annotations

import html
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli_anything.tubular_reform import CLI_NAME, SOFTWARE, __version__
from cli_anything.tubular_reform.core.table import reflow_project
from cli_anything.tubular_reform.utils import preview_bundle as pb
from cli_anything.tubular_reform.utils import tubular_reform_backend as backend

RECIPES = {
    "table-md": "Markdown table from tubular_reform.render(..., 'md')",
    "table-tsv": "TSV from tubular_reform.render(..., 'tsv')",
    "table-html": "HTML table of the same ReflowResult grid (escaped cells)",
}


def _require_result(project: dict[str, Any]) -> dict[str, Any]:
    result = project.get("result")
    if result is None:
        result = reflow_project(project)
    return result


def _source_fingerprint(project: dict[str, Any]) -> str:
    result = project.get("result") or {}
    return pb.fingerprint_data(
        {
            "source_text": project.get("source_text") or "",
            "ncols": project.get("ncols"),
            "header": project.get("header"),
            "pad": project.get("pad"),
            "strict": project.get("strict"),
            "rows": result.get("rows"),
            "result_header": result.get("header"),
        }
    )


def _html_table(result: dict[str, Any]) -> str:
    header = result.get("header") or [
        f"Column {i + 1}" for i in range(int(result["ncols"]))
    ]
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>tubular-reform preview</title></head><body>",
        "<table>",
        "<thead><tr>",
    ]
    for cell in header:
        lines.append(f"<th>{html.escape(str(cell))}</th>")
    lines.append("</tr></thead><tbody>")
    for row in result.get("rows") or []:
        lines.append("<tr>")
        for cell in row:
            lines.append(f"<td>{html.escape(str(cell))}</td>")
        lines.append("</tr>")
    lines.append("</tbody></table></body></html>")
    return "\n".join(lines) + "\n"


def _write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
        if content and not content.endswith("\n"):
            handle.write("\n")


def capture(
    project: dict[str, Any],
    *,
    recipe: str = "table-md",
    force: bool = False,
    command: str | None = None,
) -> dict[str, Any]:
    if recipe not in RECIPES:
        known = ", ".join(sorted(RECIPES))
        raise ValueError(f"unknown recipe {recipe!r}; choose one of: {known}")
    result = _require_result(project)
    fingerprint = _source_fingerprint(project)
    project_path = project.get("path")
    prepared = pb.prepare_bundle(
        software=SOFTWARE,
        recipe=recipe,
        bundle_kind="capture",
        source_fingerprint=fingerprint,
        options={"format": recipe},
        harness_version=__version__,
        project_path=project_path,
        force=force,
    )
    if prepared.get("cached"):
        manifest = prepared["manifest"]
        manifest["cached"] = True
        return _bundle_payload(manifest, cached=True)

    artifacts_dir = prepared["artifacts_dir"]
    artifacts: list[dict[str, Any]] = []
    warnings: list[str] = []

    md_text = backend.render(result, "md")
    tsv_text = backend.render(result, "tsv")
    md_path = os.path.join(artifacts_dir, "table.md")
    tsv_path = os.path.join(artifacts_dir, "table.tsv")
    _write_text(md_path, md_text)
    _write_text(tsv_path, tsv_text)
    artifacts.append(
        pb.artifact_record(
            prepared["bundle_dir"], md_path, "table-md", "hero",
            "document", "Markdown table", media_type="text/markdown",
        )
    )
    artifacts.append(
        pb.artifact_record(
            prepared["bundle_dir"], tsv_path, "table-tsv", "gallery",
            "document", "TSV table", media_type="text/tab-separated-values",
        )
    )

    if recipe == "table-html":
        html_path = os.path.join(artifacts_dir, "table.html")
        _write_text(html_path, _html_table(result))
        artifacts.append(
            pb.artifact_record(
                prepared["bundle_dir"], html_path, "table-html", "inspect",
                "document", "HTML table of the same grid",
                media_type="text/html",
            )
        )

    summary = {
        "title": f"tubular-reform {recipe}",
        "headline": result.get("summary"),
        "is_clean": result.get("is_clean"),
        "nrows": result.get("nrows"),
        "ncols": result.get("ncols"),
        "recipe": recipe,
        "truth": (
            "Markdown and TSV artifacts are tubular_reform.render output "
            "from the current ReflowResult. HTML (when present) is the same "
            "grid with HTML-escaped cells — not a second reshape."
        ),
    }
    if not result.get("is_clean"):
        warnings.append(result.get("summary") or "ragged table")

    generator_cmd = command or f"{CLI_NAME} --json preview capture --recipe {recipe}"
    manifest = pb.finalize_bundle(
        bundle_dir=prepared["bundle_dir"],
        bundle_id=prepared["bundle_id"],
        bundle_kind="capture",
        software=SOFTWARE,
        recipe=recipe,
        source={
            "project_path": project_path,
            "project_fingerprint": fingerprint,
            "capture_fingerprint": fingerprint,
        },
        artifacts=artifacts,
        summary=summary,
        cache_key=prepared["cache_key"],
        generator={
            "entry_point": CLI_NAME,
            "harness_version": __version__,
            "backend": "tubular_reform.render",
            "command": generator_cmd,
        },
        status="ok",
        warnings=warnings or None,
        metrics={
            "nrows": result.get("nrows"),
            "ncols": result.get("ncols"),
            "is_clean": result.get("is_clean"),
        },
        labels=["table", recipe],
        context={"format": project.get("format")},
    )
    manifest["cached"] = False
    return _bundle_payload(manifest, cached=False)


def latest(
    project: dict[str, Any] | None = None,
    *,
    recipe: str | None = None,
) -> dict[str, Any] | None:
    project_path = (project or {}).get("path")
    manifest = pb.find_latest_manifest(
        SOFTWARE,
        recipe=recipe,
        project_path=project_path,
    )
    if manifest is None:
        return None
    return _bundle_payload(manifest, cached=False)


def diff_capture(
    project: dict[str, Any],
    other_tsv: str,
    *,
    command: str | None = None,
) -> dict[str, Any]:
    result = _require_result(project)
    current = backend.render(result, "tsv")
    fingerprint = pb.fingerprint_data({"left": current, "right": other_tsv})
    prepared = pb.prepare_bundle(
        software=SOFTWARE,
        recipe="diff-tsv",
        bundle_kind="diff",
        source_fingerprint=fingerprint,
        harness_version=__version__,
        project_path=project.get("path"),
        force=True,
    )
    artifacts_dir = prepared["artifacts_dir"]
    left_path = os.path.join(artifacts_dir, "left.tsv")
    right_path = os.path.join(artifacts_dir, "right.tsv")
    _write_text(left_path, current)
    _write_text(right_path, other_tsv)
    artifacts = [
        pb.artifact_record(
            prepared["bundle_dir"], left_path, "left-tsv", "hero",
            "document", "Current TSV", media_type="text/tab-separated-values",
        ),
        pb.artifact_record(
            prepared["bundle_dir"], right_path, "right-tsv", "gallery",
            "document", "Comparison TSV", media_type="text/tab-separated-values",
        ),
    ]
    changed = current.strip() != other_tsv.strip()
    summary = {
        "title": "TSV diff",
        "headline": "tables differ" if changed else "tables match",
        "changed": changed,
        "truth": "Both sides are TSV from tubular_reform.render or a native CLI dump.",
    }
    manifest = pb.finalize_bundle(
        bundle_dir=prepared["bundle_dir"],
        bundle_id=prepared["bundle_id"],
        bundle_kind="diff",
        software=SOFTWARE,
        recipe="diff-tsv",
        source={
            "project_path": project.get("path"),
            "project_fingerprint": fingerprint,
        },
        artifacts=artifacts,
        summary=summary,
        cache_key=prepared["cache_key"],
        generator={
            "entry_point": CLI_NAME,
            "harness_version": __version__,
            "command": command or f"{CLI_NAME} --json preview diff",
        },
        source_bundles=[],
        metrics={"changed": changed},
        labels=["diff", "tsv"],
    )
    return _bundle_payload(manifest, cached=False)


def live_session_dir(project: dict[str, Any]) -> str:
    path = project.get("path")
    if path:
        base = os.path.join(os.path.dirname(os.path.abspath(path)), ".cli-anything", "live")
    else:
        base = os.path.join(os.path.expanduser("~"), ".cli-anything", "live")
    dest = os.path.join(base, SOFTWARE)
    os.makedirs(dest, exist_ok=True)
    return dest


def live_status(project: dict[str, Any]) -> dict[str, Any]:
    session_dir = live_session_dir(project)
    session_path = os.path.join(session_dir, "session.json")
    exists = os.path.isfile(session_path)
    session = {}
    if exists:
        session = pb._load_json(Path(session_path))
    trajectory = pb.load_live_trajectory(session_dir)
    summary = pb.summarize_trajectory(trajectory)
    active = bool(session.get("active"))
    return {
        "exists": exists,
        "active": active,
        "session_dir": session_dir,
        "session_path": session_path,
        "session_id": session.get("session_id"),
        "bundle_id": session.get("bundle_id"),
        "bundle_dir": session.get("bundle_dir"),
        "publish_reason": session.get("publish_reason"),
        "trajectory_path": str(pb.live_trajectory_path(session_dir)),
        "trajectory_summary": summary,
        "viewer_hints": {
            "inspect": f"cli-hub previews inspect {session.get('bundle_dir') or session_dir}",
            "html": f"cli-hub previews html {session.get('bundle_dir') or session_dir}",
            "watch": f"cli-hub previews watch {session_dir}",
            "open": f"cli-hub previews open {session.get('bundle_dir') or session_dir}",
        },
    }


def live_start(project: dict[str, Any], *, recipe: str = "table-md") -> dict[str, Any]:
    bundle = capture(project, recipe=recipe, force=True, command=f"{CLI_NAME} preview live start")
    return _publish_live(project, bundle, publish_reason="live-start", recipe=recipe, active=True)


def live_push(project: dict[str, Any], *, recipe: str = "table-md") -> dict[str, Any]:
    status = live_status(project)
    if not status.get("active"):
        raise RuntimeError("no active live preview session; run preview live start")
    bundle = capture(project, recipe=recipe, force=True, command=f"{CLI_NAME} preview live push")
    return _publish_live(project, bundle, publish_reason="live-push", recipe=recipe, active=True)


def live_stop(project: dict[str, Any]) -> dict[str, Any]:
    status = live_status(project)
    session_path = status["session_path"]
    session = {}
    if os.path.isfile(session_path):
        session = pb._load_json(Path(session_path))
    session["active"] = False
    session["stopped_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    pb.write_json(session_path, session)
    status = live_status(project)
    status["ok"] = True
    return status


def _publish_live(
    project: dict[str, Any],
    bundle: dict[str, Any],
    *,
    publish_reason: str,
    recipe: str,
    active: bool,
) -> dict[str, Any]:
    session_dir = live_session_dir(project)
    trajectory = pb.append_live_trajectory(
        session_dir,
        software=SOFTWARE,
        recipe=recipe,
        bundle_manifest={
            **bundle,
            "_bundle_dir": bundle.get("_bundle_dir") or bundle.get("bundle_dir"),
            "_manifest_path": bundle.get("_manifest_path") or bundle.get("manifest_path"),
            "_summary_path": bundle.get("_summary_path") or bundle.get("summary_path"),
        },
        publish_reason=publish_reason,
        project_path=project.get("path"),
        project_name=project.get("name"),
        command=bundle.get("generator", {}).get("command") if isinstance(bundle.get("generator"), dict) else None,
        source_fingerprint=_source_fingerprint(project),
    )
    session = {
        "active": active,
        "session_dir": session_dir,
        "session_id": os.path.basename(session_dir),
        "recipe": recipe,
        "bundle_id": bundle.get("bundle_id"),
        "bundle_dir": bundle.get("bundle_dir") or bundle.get("_bundle_dir"),
        "manifest_path": bundle.get("manifest_path") or bundle.get("_manifest_path"),
        "summary_path": bundle.get("summary_path") or bundle.get("_summary_path"),
        "publish_reason": publish_reason,
        "trajectory_path": str(pb.live_trajectory_path(session_dir)),
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    pb.write_json(os.path.join(session_dir, "session.json"), session)
    payload = dict(bundle)
    payload["live"] = live_status(project)
    payload["trajectory"] = pb.summarize_trajectory(trajectory)
    return payload


def _bundle_payload(manifest: dict[str, Any], *, cached: bool) -> dict[str, Any]:
    bundle_dir = manifest.get("_bundle_dir")
    return {
        "ok": True,
        "cached": cached,
        "protocol_version": manifest.get("protocol_version"),
        "bundle_id": manifest.get("bundle_id"),
        "bundle_kind": manifest.get("bundle_kind"),
        "recipe": manifest.get("recipe"),
        "status": manifest.get("status"),
        "_bundle_dir": bundle_dir,
        "bundle_dir": bundle_dir,
        "_manifest_path": manifest.get("_manifest_path"),
        "manifest_path": manifest.get("_manifest_path"),
        "_summary_path": manifest.get("_summary_path"),
        "summary_path": manifest.get("_summary_path"),
        "artifacts": manifest.get("artifacts"),
        "generator": manifest.get("generator"),
        "metrics": manifest.get("metrics"),
        "warnings": manifest.get("warnings"),
        "viewer_hints": {
            "inspect": f"cli-hub previews inspect {bundle_dir}",
            "html": f"cli-hub previews html {bundle_dir}",
            "open": f"cli-hub previews open {bundle_dir}",
        },
    }
