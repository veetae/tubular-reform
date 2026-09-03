"""Ensure user-local console scripts are on PATH for E2E native-CLI checks."""

from __future__ import annotations

import os
from pathlib import Path

_LOCAL_BIN = str(Path.home() / ".local" / "bin")
if _LOCAL_BIN not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = _LOCAL_BIN + os.pathsep + os.environ.get("PATH", "")
