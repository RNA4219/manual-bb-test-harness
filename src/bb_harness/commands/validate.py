"""Validate skill structure."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add validate subparser."""
    parser = subparsers.add_parser(
        "validate",
        help="Validate skill structure",
        description="Run quick-validate-skill.py to validate skill structure",
    )
    parser.add_argument(
        "skill_path",
        type=Path,
        nargs="?",
        default=Path("skills/manual-bb-test-harness"),
        help="Path to skill directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON format",
    )


def run(args: argparse.Namespace) -> int:
    """Run validate command."""
    script_path = Path("scripts/quick-validate-skill.py")

    cmd = [sys.executable, str(script_path), str(args.skill_path)]
    if args.json:
        # Future: add JSON output support
        pass

    result = subprocess.run(cmd, check=False)
    return result.returncode