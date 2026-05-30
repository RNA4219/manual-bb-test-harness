"""Ingest specification from external sources (Markdown, Confluence, Jira).

Generates feature_spec.json from various spec sources.

Usage:
    python scripts/spec-ingest.py --source markdown --input <file.md> --output <file.json>
    python scripts/spec-ingest.py --source confluence --url <url> --api-key <key> --output <dir>
    python scripts/spec-ingest.py --source jira --issue <key> --api-key <key> --output <file.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _shared.spec_ingest_confluence import (
    extract_confluence_page_id,
    generate_feature_id,
    ingest_confluence_spec,
    parse_confluence_html,
)
from _shared.spec_ingest_jira import ingest_jira_issue, parse_jira_description
from _shared.spec_ingest_markdown import (
    extract_markdown_sections,
    ingest_markdown_spec,
    normalize_section_name,
    parse_yaml_frontmatter,
)

__version__ = "0.2.0"

__all__ = [
    "create_parser",
    "extract_confluence_page_id",
    "extract_markdown_sections",
    "generate_feature_id",
    "ingest_confluence_spec",
    "ingest_jira_issue",
    "ingest_markdown_spec",
    "main",
    "normalize_section_name",
    "parse_confluence_html",
    "parse_jira_description",
    "parse_yaml_frontmatter",
    "run_ingest",
]


def create_parser() -> argparse.ArgumentParser:
    """Create the spec-ingest CLI parser."""
    parser = argparse.ArgumentParser(
        description="Ingest specification from external sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=["markdown", "confluence", "jira"],
        required=True,
        help="Source type: markdown, confluence, or jira",
    )
    parser.add_argument("--input", type=Path, help="Input file path (for markdown)")
    parser.add_argument("--url", help="Confluence page URL (for confluence)")
    parser.add_argument("--issue", help="Jira issue key (for jira)")
    parser.add_argument(
        "--api-key",
        help="API key for Confluence/Jira (optional, uses env var if not provided)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path (file or directory)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"spec-ingest {__version__}",
    )
    return parser


def run_ingest(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch CLI args to the selected ingestion source."""
    if args.source == "markdown":
        if not args.input:
            raise ValueError("--input required for markdown source")
        return ingest_markdown_spec(args.input)

    if args.source == "confluence":
        if not args.url:
            raise ValueError("--url required for confluence source")
        return ingest_confluence_spec(args.url, args.api_key or "")

    if args.source == "jira":
        if not args.issue:
            raise ValueError("--issue required for jira source")
        return ingest_jira_issue(args.issue, args.api_key or "")

    raise ValueError(f"Unknown source type: {args.source}")


def main() -> int:
    """Main entry point."""
    args = create_parser().parse_args()
    try:
        result = run_ingest(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Generated: {args.output}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
