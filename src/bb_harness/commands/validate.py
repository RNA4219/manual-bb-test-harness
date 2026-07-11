"""Validate skill structure."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.commands._invoke import invoke_tool
from bb_harness.tools.quick_validate_skill import main as validate_main


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


def run(args: argparse.Namespace) -> int:
    """Run validate command."""
    extra_args = [str(args.skill_path)]

    if getattr(args, "verbose", False):
        print(f"[verbose] Skill path: {args.skill_path}", file=sys.stderr)

    return invoke_tool(validate_main, extra_args, args)
