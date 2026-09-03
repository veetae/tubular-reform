"""E2E tests: real example files, native tubular-reform CLI, installed harness."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_anything.tubular_reform.tubular_reform_cli import cli

REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLES = REPO_ROOT / "examples"
PRODUCE = EXAMPLES / "1-clean-produce.in.txt"
RAGGED = EXAMPLES / "2-ragged-missing-cell.in.txt"
HEADER = EXAMPLES / "4-markdown-header.in.txt"


def _resolve_cli(name: str) -> list[str]:
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m cli_anything.tubular_reform")
    return [sys.executable, "-m", "cli_anything.tubular_reform"]


def _native_cli() -> str:
    path = shutil.which("tubular-reform")
    if not path:
        raise RuntimeError("tubular-reform not on PATH; install the real backend")
    return path


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_produce_markdown_file(tmp_path: Path, runner: CliRunner) -> None:
    out = tmp_path / "produce.md"
    result = runner.invoke(
        cli,
        [
            "--json", "table", "reform",
            "--file", str(PRODUCE),
            "-c", "3", "-f", "md",
            "-o", str(out), "--overwrite",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["result"]["is_clean"] is True
    text = out.read_text(encoding="utf-8")
    assert out.stat().st_size > 0
    assert "| Apple" in text
    assert "---" in text
    print(f"\n  Markdown: {out} ({out.stat().st_size:,} bytes)")


def test_native_cli_tsv_parity(tmp_path: Path, runner: CliRunner) -> None:
    harness_out = tmp_path / "harness.tsv"
    result = runner.invoke(
        cli,
        [
            "--json", "table", "reform",
            "--file", str(PRODUCE),
            "-c", "3", "-f", "tsv",
            "-o", str(harness_out), "--overwrite",
        ],
    )
    assert result.exit_code == 0, result.output
    native = subprocess.run(
        [_native_cli(), "--stdin", "-q", "-c", "3", "-f", "tsv"],
        input=PRODUCE.read_text(encoding="utf-8"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert native.returncode == 0, native.stderr
    assert harness_out.read_text(encoding="utf-8").strip() == native.stdout.strip()
    print(f"\n  Native TSV matched harness: {harness_out}")


def test_ragged_pad(runner: CliRunner) -> None:
    result = runner.invoke(
        cli,
        ["--json", "table", "reform", "--file", str(RAGGED), "-c", "3", "-f", "tsv"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"]["is_clean"] is False
    assert "-" in payload["output"]


def test_ragged_strict_refuses(tmp_path: Path, runner: CliRunner) -> None:
    out = tmp_path / "should-not-exist.tsv"
    result = runner.invoke(
        cli,
        [
            "--json", "table", "reform",
            "--file", str(RAGGED),
            "-c", "3", "--strict",
            "-o", str(out), "--overwrite",
        ],
    )
    assert result.exit_code != 0
    assert not out.exists()
    payload = json.loads(result.output)
    assert payload["ok"] is False


def test_header_markdown(runner: CliRunner) -> None:
    result = runner.invoke(
        cli,
        [
            "--json", "table", "reform",
            "--file", str(HEADER),
            "-c", "3", "--header", "-f", "md",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "Country" in payload["output"]
    assert "Paris" in payload["output"]


def test_auto_detect_header_table(runner: CliRunner) -> None:
    result = runner.invoke(
        cli,
        ["--json", "table", "reform", "--file", str(HEADER), "-f", "tsv"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"]["ncols"] == 3
    assert payload["detect"]["ncols"] == 3


def test_project_save_open_second_runner(tmp_path: Path, runner: CliRunner) -> None:
    proj = tmp_path / "table.json"
    created = runner.invoke(
        cli,
        ["--json", "project", "new", "-o", str(proj), "--name", "produce"],
    )
    assert created.exit_code == 0, created.output
    loaded = runner.invoke(
        cli,
        [
            "--json", "-p", str(proj),
            "table", "reform", "--file", str(PRODUCE), "-c", "3",
        ],
    )
    assert loaded.exit_code == 0, loaded.output
    saved = runner.invoke(cli, ["--json", "-p", str(proj), "project", "save"])
    assert saved.exit_code == 0, saved.output
    info = runner.invoke(cli, ["--json", "-p", str(proj), "project", "info"])
    assert info.exit_code == 0, info.output
    payload = json.loads(info.output)
    assert payload["project"]["cell_count"] == 12
    assert payload["project"]["ncols"] == 3


def test_undo_restores_source(tmp_path: Path, runner: CliRunner) -> None:
    proj = tmp_path / "undo.json"
    runner.invoke(cli, ["--json", "project", "new", "-o", str(proj), "--name", "u"])
    runner.invoke(
        cli,
        ["--json", "-p", str(proj), "table", "load", "--file", str(PRODUCE)],
    )
    runner.invoke(
        cli,
        ["--json", "-p", str(proj), "table", "load", "--file", str(HEADER)],
    )
    undone = runner.invoke(cli, ["--json", "-p", str(proj), "session", "undo"])
    assert undone.exit_code == 0, undone.output
    data = json.loads(proj.read_text(encoding="utf-8"))
    assert "Apple" in data["source_text"]
    assert "France" not in data["source_text"]


def test_preview_capture_and_latest(tmp_path: Path, runner: CliRunner) -> None:
    proj = tmp_path / "prev.json"
    runner.invoke(cli, ["--json", "project", "new", "-o", str(proj), "--name", "p"])
    runner.invoke(
        cli,
        ["--json", "-p", str(proj), "table", "reform", "--file", str(PRODUCE), "-c", "3"],
    )
    cap = runner.invoke(
        cli,
        ["--json", "-p", str(proj), "preview", "capture", "--recipe", "table-md", "--force"],
    )
    assert cap.exit_code == 0, cap.output
    payload = json.loads(cap.output)
    bundle = Path(payload["bundle_dir"])
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "artifacts" / "table.md").stat().st_size > 0
    latest = runner.invoke(cli, ["--json", "-p", str(proj), "preview", "latest"])
    assert latest.exit_code == 0, latest.output
    assert json.loads(latest.output)["bundle_id"] == payload["bundle_id"]
    print(f"\n  Preview: {bundle}")


def test_preview_live_status_json(tmp_path: Path, runner: CliRunner) -> None:
    proj = tmp_path / "live.json"
    runner.invoke(cli, ["--json", "project", "new", "-o", str(proj), "--name", "live"])
    runner.invoke(
        cli,
        ["--json", "-p", str(proj), "table", "reform", "--file", str(PRODUCE), "-c", "3"],
    )
    start = runner.invoke(cli, ["--json", "-p", str(proj), "preview", "live", "start"])
    assert start.exit_code == 0, start.output
    status = runner.invoke(cli, ["--json", "-p", str(proj), "preview", "live", "status"])
    assert status.exit_code == 0, status.output
    payload = json.loads(status.output)
    assert payload["active"] is True
    assert "trajectory_summary" in payload
    push = runner.invoke(cli, ["--json", "-p", str(proj), "preview", "live", "push"])
    assert push.exit_code == 0, push.output
    stop = runner.invoke(cli, ["--json", "-p", str(proj), "preview", "live", "stop"])
    assert stop.exit_code == 0, stop.output
    stopped = json.loads(stop.output)
    assert stopped["active"] is False


def test_preview_diff(tmp_path: Path, runner: CliRunner) -> None:
    proj = tmp_path / "diff.json"
    other = tmp_path / "other.tsv"
    other.write_text("x\ty\n", encoding="utf-8")
    runner.invoke(cli, ["--json", "project", "new", "-o", str(proj), "--name", "d"])
    runner.invoke(
        cli,
        ["--json", "-p", str(proj), "table", "reform", "--file", str(PRODUCE), "-c", "3"],
    )
    result = runner.invoke(
        cli,
        ["--json", "-p", str(proj), "preview", "diff", "--file", str(other)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["bundle_kind"] == "diff"


def test_export_write_dry_run(tmp_path: Path, runner: CliRunner) -> None:
    dest = tmp_path / "nope.tsv"
    result = runner.invoke(
        cli,
        [
            "--json", "--dry-run",
            "table", "reform",
            "--file", str(PRODUCE), "-c", "3",
            "-o", str(dest), "--overwrite",
        ],
    )
    assert result.exit_code == 0, result.output
    # reform -o still writes the export file; dry-run applies to project autosave.
    # Explicit export write --dry-run must not create the export path.
    dest2 = tmp_path / "dry.tsv"
    runner.invoke(
        cli,
        [
            "--json", "--dry-run", "-p", str(tmp_path / "p.json"),
            "table", "reform", "--file", str(PRODUCE), "-c", "3",
        ],
    )
    written = runner.invoke(
        cli,
        ["--json", "--dry-run", "export", "write", str(dest2), "--overwrite"],
    )
    # No project loaded with a result in this second isolated invoke — expect failure
    # unless we chain. Re-run as one memory session via a loaded project:
    proj = tmp_path / "dryproj.json"
    runner.invoke(cli, ["--json", "project", "new", "-o", str(proj)])
    runner.invoke(
        cli,
        ["--json", "-p", str(proj), "table", "reform", "--file", str(PRODUCE), "-c", "3"],
    )
    dry = runner.invoke(
        cli,
        ["--json", "--dry-run", "-p", str(proj), "export", "write", str(dest2)],
    )
    assert dry.exit_code == 0, dry.output
    assert not dest2.exists()
    assert written.exit_code != 0 or not dest2.exists()


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-tubular-reform")

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            env=env,
        )

    def test_help(self) -> None:
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "table" in result.stdout
        assert "preview" in result.stdout

    def test_project_new_json(self, tmp_path: Path) -> None:
        out = tmp_path / "test.json"
        result = self._run(["--json", "project", "new", "-o", str(out), "--name", "sub"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert out.is_file()

    def test_full_reform_workflow(self, tmp_path: Path) -> None:
        out = tmp_path / "sub.tsv"
        result = self._run(
            [
                "--json", "table", "reform",
                "--file", str(PRODUCE),
                "-c", "3", "-f", "tsv",
                "-o", str(out), "--overwrite",
            ]
        )
        assert result.returncode == 0, result.stderr + result.stdout
        data = json.loads(result.stdout)
        assert data["result"]["is_clean"] is True
        assert out.is_file()
        assert "Apple" in out.read_text(encoding="utf-8")
        print(f"\n  Subprocess TSV: {out} ({out.stat().st_size:,} bytes)")
