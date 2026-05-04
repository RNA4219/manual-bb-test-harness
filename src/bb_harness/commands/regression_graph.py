"""Generate regression impact graph."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


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
    script_path = Path("scripts/regression-graph.py")

    cmd = [
        sys.executable,
        str(script_path),
        "--input", str(args.input),
        "--format", args.format,
        "--output", str(args.output),
    ]

    result = subprocess.run(cmd, check=False)
    return result.returncode