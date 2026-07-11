"""Generate state diagram from test_model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.commands._invoke import invoke_tool
from bb_harness.tools.state_diagram import main as state_diagram_main


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add state-diagram subparser."""
    parser = subparsers.add_parser(
        "state-diagram",
        help="Generate Mermaid state diagram",
        description="Generate Mermaid stateDiagram from test_model.json",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input test_model.json file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output Mermaid file (.mmd)",
    )


def run(args: argparse.Namespace) -> int:
    """Run state-diagram command."""
    extra_args = [
        "--input",
        str(args.input),
        "--output",
        str(args.output),
    ]

    if getattr(args, "verbose", False):
        print(f"[verbose] Input: {args.input}", file=sys.stderr)

    return invoke_tool(state_diagram_main, extra_args, args)
