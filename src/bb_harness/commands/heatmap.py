"""Generate risk heatmap visualization."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


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
    script_path = Path("scripts/risk-heatmap.py")

    cmd = [
        sys.executable,
        str(script_path),
        "--input", str(args.input),
        "--format", args.format,
        "--output", str(args.output),
        "--title", args.title,
    ]

    result = subprocess.run(cmd, check=False)
    return result.returncode