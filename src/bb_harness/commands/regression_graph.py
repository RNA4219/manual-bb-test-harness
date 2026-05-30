"""Generate regression impact graph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.commands._shared import run_script


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add regression-graph subparser."""
    parser = subparsers.add_parser(
        "regression-graph",
        help="Generate regression impact graph",
        description="Generate GraphViz DOT or D3.js HTML from feature specs",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input directory or files",
    )
    parser.add_argument(
        "--format",
        choices=["dot", "html", "json"],
        default="html",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file",
    )


def run(args: argparse.Namespace) -> int:
    """Run regression-graph command."""
    extra_args = [
        "--input",
        str(args.input),
        "--format",
        args.format,
        "--output",
        str(args.output),
    ]

    if getattr(args, "verbose", False):
        print(f"[verbose] Input: {args.input}, Format: {args.format}", file=sys.stderr)

    return run_script("regression-graph.py", extra_args, args)
