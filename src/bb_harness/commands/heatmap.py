"""Generate risk heatmap visualization."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.commands._shared import run_script


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add heatmap subparser."""
    parser = subparsers.add_parser(
        "heatmap",
        help="Generate risk heatmap",
        description="Generate HTML/SVG heatmap from risk_register.json",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input risk_register.json file",
    )
    parser.add_argument(
        "--format",
        choices=["html", "svg"],
        default="html",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file",
    )
    parser.add_argument(
        "--title",
        default="Risk Heatmap",
        help="Title for visualization",
    )


def run(args: argparse.Namespace) -> int:
    """Run heatmap command."""
    extra_args = [
        "--input",
        str(args.input),
        "--format",
        args.format,
        "--output",
        str(args.output),
        "--title",
        args.title,
    ]

    if getattr(args, "verbose", False):
        print(f"[verbose] Input: {args.input}", file=sys.stderr)

    return run_script("risk-heatmap.py", extra_args, args)
