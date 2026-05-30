"""Evaluate gate decision."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.commands._shared import run_script


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
    extra_args = [
        "--output",
        str(args.output),
        "--profile",
        args.profile,
    ]

    if args.input:
        extra_args.extend(["--input", str(args.input)])
    elif args.evidence and args.risk and args.cases:
        extra_args.extend(
            [
                "--evidence",
                str(args.evidence),
                "--risk",
                str(args.risk),
                "--cases",
                str(args.cases),
            ]
        )
    else:
        print("Error: --input or (--evidence, --risk, --cases) required", file=sys.stderr)
        return 1

    if getattr(args, "verbose", False):
        print(f"[verbose] Profile: {args.profile}", file=sys.stderr)

    return run_script("evaluate-gate.py", extra_args, args)
