"""Evaluate Gate 2.0 decision."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.gate_engine import main as evaluate_gate_main


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "gate",
        help="Evaluate gate decision",
        description="Evaluate go/conditional_go/no_go from release evidence",
    )
    parser.add_argument("--input", type=Path, help="Input directory containing artifacts")
    parser.add_argument("--evidence", type=Path, help="Execution evidence file or directory")
    parser.add_argument("--risk", type=Path, help="Risk register JSON file")
    parser.add_argument("--cases", type=Path, help="Manual case set JSON file")
    parser.add_argument("--feature", type=Path, help="Feature spec JSON file")
    parser.add_argument("--observations", type=Path, help="Observation set JSON file")
    parser.add_argument("--automation", type=Path, help="Automation evidence JSON file")
    parser.add_argument("--waivers", type=Path, help="Waiver set JSON file")
    parser.add_argument("--build-id", help="Build identifier to evaluate")
    parser.add_argument("--output", type=Path, required=True, help="Output gate decision file")
    parser.add_argument(
        "--profile",
        choices=["strict", "standard", "lean"],
        default="standard",
        help="Gate quality profile",
    )


def run(args: argparse.Namespace) -> int:
    extra_args = ["--output", str(args.output), "--profile", args.profile]
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

    for option, value in (
        ("--feature", args.feature),
        ("--observations", args.observations),
        ("--automation", args.automation),
        ("--waivers", args.waivers),
        ("--build-id", args.build_id),
    ):
        if value is not None:
            extra_args.extend([option, str(value)])

    if getattr(args, "verbose", False):
        print(f"[verbose] Profile: {args.profile}", file=sys.stderr)
    return evaluate_gate_main(extra_args)
