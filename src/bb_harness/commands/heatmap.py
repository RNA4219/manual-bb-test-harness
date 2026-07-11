"""Generate risk heatmap visualization."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.commands._invoke import invoke_tool
from bb_harness.tools.risk_heatmap import main as risk_heatmap_main


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

    return invoke_tool(risk_heatmap_main, extra_args, args)
