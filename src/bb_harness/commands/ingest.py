"""Ingest specification from external sources."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bb_harness.commands._invoke import invoke_tool
from bb_harness.tools.spec_ingest import main as ingest_main


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
    extra_args = ["--source", args.source, "--output", str(args.output)]

    if args.source == "markdown" and args.input:
        extra_args.extend(["--input", str(args.input)])
    elif args.source == "confluence" and args.url:
        extra_args.extend(["--url", args.url])
    elif args.source == "jira" and args.issue:
        extra_args.extend(["--issue", args.issue])
    else:
        print(f"Error: Missing required argument for source {args.source}", file=sys.stderr)
        return 1

    if getattr(args, "verbose", False):
        print(f"[verbose] Source: {args.source}", file=sys.stderr)

    return invoke_tool(ingest_main, extra_args, args)
