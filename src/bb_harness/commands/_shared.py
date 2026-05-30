"""Shared utilities for command modules."""

from __future__ import annotations

import argparse
import subprocess
import sys

from bb_harness._paths import PROJECT_ROOT


def run_script(
    script_name: str,
    extra_args: list[str],
    args: argparse.Namespace,
) -> int:
    """Run a script from scripts/ directory with common flags.

    Args:
        script_name: Script filename (e.g., "export-testrail.py")
        extra_args: Additional command-line arguments
        args: Parsed argparse namespace (checks for verbose, dry_run)

    Returns:
        Exit code from subprocess
    """
    script_path = PROJECT_ROOT / "scripts" / script_name
    cmd = [sys.executable, str(script_path)] + extra_args

    # Append --dry-run if set
    if getattr(args, "dry_run", False):
        cmd.append("--dry-run")

    # Print verbose output
    if getattr(args, "verbose", False):
        print(f"[verbose] Running: {' '.join(cmd)}", file=sys.stderr)

    result = subprocess.run(cmd, check=False)
    return result.returncode
