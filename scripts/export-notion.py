"""Export forward-test results to Notion database.

Creates a Notion page with test run results, rubric scores, and findings.

Usage:
    python scripts/export-notion.py --input <forward_test_report.json> --db <database_id>
    python scripts/export-notion.py --input <report.json> --db <database_id> --title "Test Run 2026-05-04"
    python scripts/export-notion.py --version

Environment variables:
    NOTION_API_TOKEN: Notion integration token (required)
    NOTION_DATABASE_ID: Database ID (optional, can be passed via --db)

Example:
    python scripts/export-notion.py \
        --input docs/forward-test-reports/2026-05-04-order-cancel.json \
        --db abc123def456 \
        --title "Order Cancel Forward Test 2026-05-04"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

__version__ = "0.1.0"


def load_report(path: Path) -> dict[str, Any]:
    """Load and parse forward-test report JSON."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e


def create_notion_page(
    database_id: str,
    title: str,
    report: dict[str, Any],
    api_token: str,
) -> dict[str, Any]:
    """Create Notion page with test results.

    Uses Notion API v2022-06-28.

    Args:
        database_id: Notion database ID
        title: Page title
        report: Forward-test report data
        api_token: Notion integration token

    Returns:
        API response with created page ID
    """
    try:
        import requests
    except ImportError:
        raise ValueError("requests library required. Install: pip install requests")

    # Notion API endpoint
    url = "https://api.notion.com/v1/pages"

    # Headers
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # Extract report data
    feature_id = report.get("feature_id", "UNKNOWN")
    skill_name = report.get("skill_name", "manual-bb-test-harness")
    input_file = report.get("input_file", "")
    score = report.get("score", 0)
    pass_status = report.get("pass_status", "unknown")
    rubric_breakdown = report.get("rubric_breakdown", {})
    findings = report.get("findings", [])
    notes = report.get("notes", "")

    # Build page properties
    properties: dict[str, Any] = {
        "Title": {
            "title": [
                {
                    "text": {
                        "content": title,
                    },
                },
            ],
        },
    }

    # Add select/rich_text properties based on database schema
    # Common properties for forward-test database
    if database_id:
        properties["Status"] = {
            "select": {
                "name": pass_status.capitalize(),
            },
        }
        properties["Score"] = {
            "number": score,
        }
        properties["Feature"] = {
            "rich_text": [
                {
                    "text": {
                        "content": feature_id,
                    },
                },
            ],
        }
        properties["Skill"] = {
            "rich_text": [
                {
                    "text": {
                        "content": skill_name,
                    },
                },
            ],
        }

    # Build page content (children blocks)
    children: list[dict[str, Any]] = []

    # Summary header
    children.append({
        "object": "block",
        "type": "header",
        "header": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": "Forward Test Summary",
                    },
                },
            ],
        },
    })

    # Score summary
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": f"Total Score: {score} / 100 | Status: {pass_status}",
                    },
                },
            ],
        },
    })

    # Rubric breakdown table
    if rubric_breakdown:
        children.append({
            "object": "block",
            "type": "header",
            "header": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "Rubric Breakdown",
                        },
                    },
                ],
            },
        })

        # Create table rows as bullet list
        for category, data in rubric_breakdown.items():
            cat_score = data.get("score", 0)
            cat_weight = data.get("weight", 0)
            cat_checks = data.get("checks", [])

            children.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": f"{category}: {cat_score}/{cat_weight}",
                            },
                        },
                    ],
                },
            })

            # Add check items
            for check in cat_checks[:5]:  # Limit to 5 checks per category
                children.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": f"  - {check}",
                                },
                            },
                        ],
                    },
                })

    # Findings
    if findings:
        children.append({
            "object": "block",
            "type": "header",
            "header": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "Findings",
                        },
                    },
                ],
            },
        })

        for finding in findings:
            finding_type = finding.get("type", "observation")
            finding_text = finding.get("text", "")
            finding_priority = finding.get("priority", "")

            children.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": f"[{finding_type}] {finding_text}",
                            },
                        },
                    ],
                },
            })

    # Notes
    if notes:
        children.append({
            "object": "block",
            "type": "header",
            "header": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "Notes",
                        },
                    },
                ],
            },
        })

        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": notes,
                        },
                    },
                ],
            },
        })

    # Build request body
    body: dict[str, Any] = {
        "parent": {
            "database_id": database_id,
        },
        "properties": properties,
        "children": children,
    }

    # Make API request
    response = requests.post(url, headers=headers, json=body, timeout=30)
    response.raise_for_status()

    return response.json()


def create_report_from_evaluation(
    feature_id: str,
    skill_name: str,
    input_file: str,
    score: int,
    rubric_breakdown: dict[str, Any],
    findings: list[str],
    pass_status: str,
    notes: str,
) -> dict[str, Any]:
    """Create forward-test report structure."""
    return {
        "feature_id": feature_id,
        "skill_name": skill_name,
        "input_file": input_file,
        "score": score,
        "pass_status": pass_status,
        "rubric_breakdown": rubric_breakdown,
        "findings": [{"type": "observation", "text": f} for f in findings],
        "notes": notes,
        "timestamp": "2026-05-04T00:00:00Z",
    }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export forward-test results to Notion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to forward-test report JSON file",
    )
    parser.add_argument(
        "--db",
        help="Notion database ID (or use NOTION_DATABASE_ID env var)",
    )
    parser.add_argument(
        "--title",
        default="Forward Test Report",
        help="Title for the Notion page",
    )
    parser.add_argument(
        "--score",
        type=int,
        help="Total score (if creating without input file)",
    )
    parser.add_argument(
        "--status",
        choices=["pass", "conditional_pass", "fail"],
        help="Pass status (if creating without input file)",
    )
    parser.add_argument(
        "--feature",
        help="Feature ID (if creating without input file)",
    )
    parser.add_argument(
        "--notes",
        help="Additional notes (if creating without input file)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payload without sending to Notion",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"export-notion {__version__}",
    )

    args = parser.parse_args()

    try:
        # Get API token
        api_token = os.environ.get("NOTION_API_TOKEN", "")
        if not api_token:
            print("Error: NOTION_API_TOKEN environment variable required", file=sys.stderr)
            return 1

        # Get database ID
        database_id = args.db or os.environ.get("NOTION_DATABASE_ID", "")
        if not database_id:
            print("Error: Database ID required via --db or NOTION_DATABASE_ID env var", file=sys.stderr)
            return 1

        # Load or create report
        if args.input:
            report = load_report(args.input)
        else:
            # Create from arguments
            if not args.score:
                print("Error: --score required when not using --input", file=sys.stderr)
                return 1

            pass_status = args.status or "unknown"
            if pass_status == "conditional_pass":
                pass_status = "conditional pass"

            report = create_report_from_evaluation(
                feature_id=args.feature or "UNKNOWN",
                skill_name="manual-bb-test-harness",
                input_file="",
                score=args.score,
                rubric_breakdown={},
                findings=[],
                pass_status=pass_status,
                notes=args.notes or "",
            )

        if args.dry_run:
            # Print payload without sending
            print("=== DRY RUN ===")
            print(f"Database ID: {database_id}")
            print(f"Title: {args.title}")
            print(f"Report: {json.dumps(report, indent=2, ensure_ascii=False)}")
            return 0

        # Create Notion page
        result = create_notion_page(database_id, args.title, report, api_token)

        page_id = result.get("id", "")
        page_url = result.get("url", "")

        print(f"Created Notion page: {page_url}")
        print(f"  Page ID: {page_id}")
        print(f"  Title: {args.title}")
        print(f"  Score: {report.get('score', 0)}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())