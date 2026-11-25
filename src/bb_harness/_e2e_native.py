"""Public Python interface for the reviewed Rust E2E exporter."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from bb_harness.e2e_export import E2EExportError


def native_export(
    command: list[str],
    feature_spec: str | Path,
    case_set: str | Path,
    binding_path: str | Path,
    output: str | Path,
    *,
    approved_binding_sha256: str,
) -> list[str]:
    """Export reviewed, active scripted cases to new-only deterministic directories."""
    pin = approved_binding_sha256 if isinstance(approved_binding_sha256, str) else ""
    response = subprocess.run(
        [
            *command,
            f"--feature-spec={os.fspath(feature_spec)}",
            f"--manual-case-set={os.fspath(case_set)}",
            f"--binding={os.fspath(binding_path)}",
            f"--out={os.fspath(output)}",
            f"--approved-binding-sha256={pin}",
        ],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if response.returncode:
        raise E2EExportError(
            response.stderr.strip() or f"native exporter exited {response.returncode}"
        )
    try:
        ids = json.loads(response.stdout)
    except ValueError as exc:
        raise E2EExportError("invalid response from native exporter") from exc
    if not isinstance(ids, list) or not ids or not all(isinstance(value, str) for value in ids):
        raise E2EExportError("invalid response from native exporter")
    return ids
