"""Validate skill structure."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.commands._shared import run_script


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
    extra_args = [str(args.skill_path)]
    if args.json:
        # Future: add JSON output support
        pass

    if getattr(args, "verbose", False):
        print(f"[verbose] Skill path: {args.skill_path}", file=sys.stderr)

    return run_script("quick-validate-skill.py", extra_args, args)
