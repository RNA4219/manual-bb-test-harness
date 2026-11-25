"""Locate an installed Rust helper or run its locked, packaged source with Cargo."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def native_command(binary: str, crate: str) -> list[str] | None:
    installed = shutil.which(binary)
    if installed:
        return [installed]
    cargo = shutil.which("cargo")
    if cargo is None:
        return None
    if target := os.environ.get("CARGO_TARGET_DIR"):
        target_dir = Path(target)
    else:
        if sys.platform == "win32":
            cache = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        elif sys.platform == "darwin":
            cache = Path.home() / "Library" / "Caches"
        else:
            cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        target_dir = cache / "bb-harness" / binary.removeprefix("bb-") / "target"
    manifest = Path(__file__).resolve().parent / "native" / crate / "Cargo.toml"
    return [
        cargo,
        "run",
        "--quiet",
        "--locked",
        "--manifest-path",
        str(manifest),
        "--target-dir",
        str(target_dir),
        "--",
    ]
