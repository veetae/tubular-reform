"""Shared JSON / human output helpers."""

from __future__ import annotations

import json

import click


def emit(ctx: click.Context, payload: dict, human_lines: list[str] | None = None) -> None:
    """Write machine JSON or human lines. Payload always includes ``ok``."""
    if "ok" not in payload:
        payload = {"ok": True, **payload}
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return
    for line in human_lines or []:
        click.echo(line)


def fail(
    ctx: click.Context,
    message: str,
    *,
    code: int = 1,
    extra: dict | None = None,
) -> None:
    payload = {"ok": False, "error": message}
    if extra:
        payload.update(extra)
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        click.echo(f"error: {message}", err=True)
    ctx.exit(code)
