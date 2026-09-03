"""Unit tests for cli-anything-tubular-reform core (synthetic + real library)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli_anything.tubular_reform.core.export import render_project, write_project
from cli_anything.tubular_reform.core.preview import RECIPES, capture, latest
from cli_anything.tubular_reform.core.project import (
    load_project,
    new_project,
    project_info,
    save_project,
)
from cli_anything.tubular_reform.core.session import Session, _locked_save_json
from cli_anything.tubular_reform.core.table import (
    apply_settings,
    detect_project,
    load_text,
    reflow_project,
    tokenize_project,
)
from cli_anything.tubular_reform.utils import tubular_reform_backend as backend

PRODUCE = "Apple\n3\n0.50\nBanana\n6\n0.25\nCherry\n12\n2.00\nDate\n4\n5.75\n"


def test_new_project_defaults() -> None:
    project = new_project("demo")
    assert project["name"] == "demo"
    assert project["cells"] == []
    assert project["ncols"] is None
    assert project["format"] == "tsv"
    assert project["modified"] is False


def test_save_load_roundtrip(tmp_path: Path) -> None:
    project = new_project("round")
    project["source_text"] = "a\nb\n"
    dest = tmp_path / "proj.json"
    save_project(project, str(dest))
    loaded = load_project(str(dest))
    assert loaded["name"] == "round"
    assert loaded["source_text"] == "a\nb\n"
    assert loaded["path"] == str(dest.resolve())
    assert loaded["modified"] is False


def test_project_info_cell_count() -> None:
    project = new_project()
    load_text(project, PRODUCE)
    tokenize_project(project)
    info = project_info(project)
    assert info["cell_count"] == 12


def test_load_non_object_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a JSON object"):
        load_project(str(path))


def test_session_undo_redo() -> None:
    sess = Session()
    load_text(sess.project, "one")
    sess.snapshot()
    load_text(sess.project, "two")
    sess.undo()
    assert sess.project["source_text"] == "one"
    sess.redo()
    assert sess.project["source_text"] == "two"


def test_session_undo_empty_raises() -> None:
    with pytest.raises(RuntimeError, match="nothing to undo"):
        Session().undo()


def test_session_redo_empty_raises() -> None:
    with pytest.raises(RuntimeError, match="nothing to redo"):
        Session().redo()


def test_locked_save_json(tmp_path: Path) -> None:
    path = tmp_path / "lock.json"
    _locked_save_json(str(path), {"a": 1})
    _locked_save_json(str(path), {"a": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 2}


def test_session_save_writes_sidecar(tmp_path: Path) -> None:
    sess = Session()
    sess.snapshot()
    dest = tmp_path / "p.json"
    sess.save(str(dest))
    sidecar = dest.with_suffix(".session.json")
    assert sidecar.is_file()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert "undo_stack" in data


def test_tokenize_produce() -> None:
    project = new_project()
    load_text(project, PRODUCE)
    cells = tokenize_project(project)
    assert len(cells) == 12
    assert cells[0] == "Apple"


def test_detect_produce_three_cols() -> None:
    project = new_project()
    load_text(project, PRODUCE)
    tokenize_project(project)
    detected = detect_project(project)
    assert detected["ncols"] == 3
    assert detected["method"] in {"type-period", "tab-width"}


def test_detect_all_text_refuses() -> None:
    project = new_project()
    load_text(project, "alpha\nbeta\ngamma\ndelta\n")
    tokenize_project(project)
    with pytest.raises(backend.DetectFailed):
        detect_project(project)


def test_reflow_clean() -> None:
    project = new_project()
    load_text(project, PRODUCE)
    apply_settings(project, ncols=3)
    result = reflow_project(project)
    assert result["is_clean"] is True
    assert result["nrows"] == 4
    assert result["rows"][0][0] == "Apple"


def test_reflow_ragged_pads() -> None:
    project = new_project()
    load_text(project, "a\nb\nc\nd\ne\n")
    apply_settings(project, ncols=3, pad="-")
    result = reflow_project(project)
    assert result["is_clean"] is False
    assert result["padded"] is True
    assert result["rows"][-1] == ["d", "e", "-"]


def test_reflow_strict_raises() -> None:
    project = new_project()
    load_text(project, "a\nb\nc\nd\ne\n")
    apply_settings(project, ncols=3, strict=True)
    with pytest.raises(backend.RaggedFailed):
        reflow_project(project)


def test_apply_settings_rejects_bad_ncols() -> None:
    with pytest.raises(ValueError, match="ncols"):
        apply_settings(new_project(), ncols=0)


def test_render_matches_library() -> None:
    import tubular_reform as lib

    project = new_project()
    load_text(project, PRODUCE)
    apply_settings(project, ncols=3, fmt="tsv")
    output = render_project(project)
    cells = lib.tokenize(PRODUCE)
    expected = lib.render(lib.reflow(cells, 3), "tsv")
    assert output == expected


def test_write_project_creates_file(tmp_path: Path) -> None:
    project = new_project()
    load_text(project, PRODUCE)
    apply_settings(project, ncols=3, fmt="md")
    dest = tmp_path / "out.md"
    written = write_project(project, str(dest), "md", overwrite=True)
    assert dest.is_file()
    assert written["file_size"] > 0
    assert "Apple" in dest.read_text(encoding="utf-8")
    print(f"\n  Markdown: {dest} ({written['file_size']:,} bytes)")


def test_write_project_no_overwrite(tmp_path: Path) -> None:
    dest = tmp_path / "out.tsv"
    dest.write_text("keep\n", encoding="utf-8")
    project = new_project()
    load_text(project, PRODUCE)
    apply_settings(project, ncols=3)
    reflow_project(project)
    with pytest.raises(FileExistsError):
        write_project(project, str(dest), overwrite=False)


def test_preview_recipes() -> None:
    assert "table-md" in RECIPES
    assert "table-tsv" in RECIPES
    assert "table-html" in RECIPES


def test_preview_capture_bundle(tmp_path: Path) -> None:
    import tubular_reform as lib

    project = new_project("cap")
    project["path"] = str(tmp_path / "cap.json")
    save_project(project, project["path"])
    load_text(project, PRODUCE)
    apply_settings(project, ncols=3)
    reflow_project(project)
    payload = capture(project, recipe="table-md", force=True)
    bundle = Path(payload["bundle_dir"])
    manifest_path = bundle / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "preview-bundle/v1"
    md_path = bundle / "artifacts" / "table.md"
    assert md_path.stat().st_size > 0
    expected = lib.render(lib.reflow(lib.tokenize(PRODUCE), 3), "md")
    assert md_path.read_text(encoding="utf-8").strip() == expected.strip()
    found = latest(project, recipe="table-md")
    assert found is not None
    assert found["bundle_id"] == payload["bundle_id"]
    print(f"\n  Preview bundle: {bundle}")


def test_preview_unknown_recipe() -> None:
    project = new_project()
    load_text(project, PRODUCE)
    apply_settings(project, ncols=3)
    reflow_project(project)
    with pytest.raises(ValueError, match="unknown recipe"):
        capture(project, recipe="nope")


def test_backend_require_library() -> None:
    lib = backend.require_library()
    assert hasattr(lib, "reflow")
