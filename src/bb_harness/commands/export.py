"""Export to external systems."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add export subparser with nested subcommands."""
    parser = subparsers.add_parser(
        "export",
        help="Export to external systems",
        description="Export artifacts to TestRail, Xray, or Notion",
    )

    export_subparsers = parser.add_subparsers(
        title="export targets",
        dest="target",
        help="Export target system",
    )

    # TestRail
    testrail_parser = export_subparsers.add_parser(
        "testrail",
        help="Export to TestRail",
    )
    testrail_parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input manual_case_set.json file",
    )
    testrail_parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format",
    )
    testrail_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file",
    )

    # Xray
    xray_parser = export_subparsers.add_parser(
        "xray",
        help="Export to Xray",
    )
    xray_parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input manual_case_set.json file",
    )
    xray_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file",
    )

    # Notion
    notion_parser = export_subparsers.add_parser(
        "notion",
        help="Export to Notion",
    )
    notion_parser.add_argument(
        "--input",
        type=Path,
        help="Input report JSON file",
    )
    notion_parser.add_argument(
        "--db",
        help="Notion database ID",
    )
    notion_parser.add_argument(
        "--title",
        default="Forward Test Report",
        help="Page title",
    )
    notion_parser.add_argument(
        "--score",
        type=int,
        help="Score (if creating without input)",
    )
    notion_parser.add_argument(
        "--status",
        choices=["pass", "conditional_pass", "fail"],
        help="Status (if creating without input)",
    )
    notion_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payload without sending",
    )


def run(args: argparse.Namespace) -> int:
    """Run export command."""
    if args.target is None:
        print("Error: export target required (testrail, xray, notion)", file=sys.stderr)
        return 1

    if args.target == "testrail":
        script_path = Path("scripts/export-testrail.py")
        cmd = [
            sys.executable,
            str(script_path),
            "--input", str(args.input),
            "--format", args.format,
            "--output", str(args.output),
        ]
    elif args.target == "xray":
        script_path = Path("scripts/export-xray.py")
        cmd = [
            sys.executable,
            str(script_path),
            "--input", str(args.input),
            "--output", str(args.output),
        ]
    elif args.target == "notion":
        script_path = Path("scripts/export-notion.py")
        cmd = [sys.executable, str(script_path)]
        if args.input:
            cmd.extend(["--input", str(args.input)])
        if args.db:
            cmd.extend(["--db", args.db])
        cmd.extend(["--title", args.title])
        if args.score:
            cmd.extend(["--score", str(args.score)])
        if args.status:
            cmd.extend(["--status", args.status])
        if args.dry_run:
            cmd.append("--dry-run")
    else:
        print(f"Error: Unknown export target: {args.target}", file=sys.stderr)
        return 1

    result = subprocess.run(cmd, check=False)
    return result.returncode