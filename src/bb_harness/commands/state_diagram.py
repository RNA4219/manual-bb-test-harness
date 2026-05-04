"""Generate state diagram from test_model."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


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
    script_path = Path("scripts/state-diagram.py")

    cmd = [
        sys.executable,
        str(script_path),
        "--input", str(args.input),
        "--output", str(args.output),
    ]

    result = subprocess.run(cmd, check=False)
    return result.returncode