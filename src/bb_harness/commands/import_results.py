"""Import test results from external systems."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.commands._invoke import invoke_tool
from bb_harness.tools.import_testrail import main as import_testrail_main
from bb_harness.tools.import_xray import main as import_xray_main


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add import subparser with nested subcommands."""
    parser = subparsers.add_parser(
        "import",
        help="Import test results from external systems",
        description="Import test results from TestRail or Xray",
    )

    import_subparsers = parser.add_subparsers(
        title="import sources",
        dest="source",
        help="Import source system",
    )

    # TestRail
    testrail_parser = import_subparsers.add_parser(
        "testrail",
        help="Import from TestRail",
    )
    testrail_parser.add_argument(
        "--project",
        type=int,
        required=True,
        help="TestRail project ID",
    )
    testrail_parser.add_argument(
        "--run",
        type=int,
        required=True,
        help="TestRail test run ID",
    )
    testrail_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for execution_evidence files",
    )
    testrail_parser.add_argument(
        "--tc-prefix",
        default="TC",
        help="Prefix for test case IDs (default: TC)",
    )
    testrail_parser.add_argument(
        "--feature-id",
        default="IMPORTED",
        help="Feature ID attached to imported evidence",
    )
    testrail_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results without writing files",
    )

    # Xray
    xray_parser = import_subparsers.add_parser(
        "xray",
        help="Import from Xray (Jira)",
    )
    xray_parser.add_argument(
        "--exec",
        required=True,
        help="Xray test execution key, e.g., PROJ-TE-123",
    )
    xray_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for execution_evidence files",
    )
    xray_parser.add_argument(
        "--feature-id",
        default="IMPORTED",
        help="Feature ID attached to imported evidence",
    )
    xray_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results without writing files",
    )


def run(args: argparse.Namespace) -> int:
    """Run import command."""
    if args.source is None:
        print("Error: import source required (testrail, xray)", file=sys.stderr)
        return 1

    if args.source == "testrail":
        extra_args = [
            "--project",
            str(args.project),
            "--run",
            str(args.run),
            "--output",
            str(args.output),
            "--feature-id",
            args.feature_id,
        ]
        if args.tc_prefix != "TC":
            extra_args.extend(["--tc-prefix", args.tc_prefix])
        return invoke_tool(import_testrail_main, extra_args, args)
    elif args.source == "xray":
        extra_args = [
            "--exec",
            args.exec,
            "--output",
            str(args.output),
            "--feature-id",
            args.feature_id,
        ]
        return invoke_tool(import_xray_main, extra_args, args)
    else:
        print(f"Error: Unknown import source: {args.source}", file=sys.stderr)
        return 1
