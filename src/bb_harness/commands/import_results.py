"""Import test results from external systems."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Resolve project root from this file's location:
# src/bb_harness/commands/import_results.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


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
        script_path = PROJECT_ROOT / "scripts" / "import-testrail.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--project",
            str(args.project),
            "--run",
            str(args.run),
            "--output",
            str(args.output),
        ]
        if args.tc_prefix != "TC":
            cmd.extend(["--tc-prefix", args.tc_prefix])
        # Check both top-level --dry-run and subcommand --dry-run
        if getattr(args, "dry_run", False):
            cmd.append("--dry-run")
    elif args.source == "xray":
        script_path = PROJECT_ROOT / "scripts" / "import-xray.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--exec",
            args.exec,
            "--output",
            str(args.output),
        ]
        # Check both top-level --dry-run and subcommand --dry-run
        if getattr(args, "dry_run", False):
            cmd.append("--dry-run")
    else:
        print(f"Error: Unknown import source: {args.source}", file=sys.stderr)
        return 1

    if getattr(args, "verbose", False):
        print(f"[verbose] Running: {' '.join(cmd)}", file=sys.stderr)

    result = subprocess.run(cmd, check=False)
    return result.returncode
