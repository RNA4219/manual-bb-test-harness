"""Evaluate gate decision."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add gate subparser."""
    parser = subparsers.add_parser(
        "gate",
        help="Evaluate gate decision",
        description="Evaluate go/conditional_go/no_go from execution evidence",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input directory containing artifacts",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Execution evidence file or directory",
    )
    parser.add_argument(
        "--risk",
        type=Path,
        help="Risk register JSON file",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        help="Manual case set JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output gate_decision.json file",
    )
    parser.add_argument(
        "--profile",
        choices=["strict", "standard", "lean"],
        default="standard",
        help="Gate quality profile",
    )


def run(args: argparse.Namespace) -> int:
    """Run gate command."""
    script_path = Path("scripts/evaluate-gate.py")

    cmd = [
        sys.executable,
        str(script_path),
        "--output", str(args.output),
        "--profile", args.profile,
    ]

    if args.input:
        cmd.extend(["--input", str(args.input)])
    elif args.evidence and args.risk and args.cases:
        cmd.extend([
            "--evidence", str(args.evidence),
            "--risk", str(args.risk),
            "--cases", str(args.cases),
        ])
    else:
        print("Error: --input or (--evidence, --risk, --cases) required", file=sys.stderr)
        return 1

    result = subprocess.run(cmd, check=False)
    return result.returncode