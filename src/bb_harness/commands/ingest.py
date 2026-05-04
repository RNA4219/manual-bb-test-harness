"""Ingest specification from external sources."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add ingest subparser."""
    parser = subparsers.add_parser(
        "ingest",
        help="Ingest specification from external sources",
        description="Convert Markdown/Confluence/Jira specs to feature_spec.json",
    )
    parser.add_argument(
        "--source",
        choices=["markdown", "confluence", "jira"],
        required=True,
        help="Source type",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input file (for markdown)",
    )
    parser.add_argument(
        "--url",
        help="Confluence page URL (for confluence)",
    )
    parser.add_argument(
        "--issue",
        help="Jira issue key (for jira)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSON file",
    )


def run(args: argparse.Namespace) -> int:
    """Run ingest command."""
    script_path = Path("scripts/spec-ingest.py")

    cmd = [sys.executable, str(script_path), "--source", args.source, "--output", str(args.output)]

    if args.source == "markdown" and args.input:
        cmd.extend(["--input", str(args.input)])
    elif args.source == "confluence" and args.url:
        cmd.extend(["--url", args.url])
    elif args.source == "jira" and args.issue:
        cmd.extend(["--issue", args.issue])
    else:
        print(f"Error: Missing required argument for source {args.source}", file=sys.stderr)
        return 1

    result = subprocess.run(cmd, check=False)
    return result.returncode