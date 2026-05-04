"""Export manual_case_set.json to TestRail CSV/JSON format.

Usage:
    python scripts/export-testrail.py --input <manual_case_set.json> --format <csv|json> --output <file>

Example:
    python scripts/export-testrail.py \
        --input examples/artifacts/order-cancel.manual_case_set.json \
        --format csv \
        --output exports/testrail-order-cancel.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

__version__ = "0.2.0"


def load_case_set(path: Path) -> dict[str, Any]:
    """Load and parse manual_case_set.json."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e


def convert_to_testrail(case_set: dict[str, Any]) -> dict[str, Any]:
    """Convert manual_case_set to TestRail format.

    TestRail import format:
    - Sections (by feature_id)
    - Cases with: title, section_id, steps, expected, priority, estimate
    """
    feature_id = case_set.get("feature_id", "UNKNOWN")
    cases = case_set.get("manual_cases", [])

    testrail_data: dict[str, Any] = {
        "sections": [
            {
                "id": 1,
                "name": feature_id,
                "description": f"Feature: {feature_id}",
            }
        ],
        "cases": [],
    }

    for i, case in enumerate(cases, start=1):
        # Map priority
        priority_map = {"P0": 5, "P1": 4, "P2": 3, "P3": 2, "P4": 1}
        priority_str = case.get("priority", "P2")
        priority_int = priority_map.get(priority_str, 3)

        # Build steps with expected results
        steps = case.get("steps", [])
        expected = case.get("expected_results", [])

        testrail_case: dict[str, Any] = {
            "id": i,
            "section_id": 1,
            "title": case.get("title", f"Test Case {i}"),
            "priority_id": priority_int,
            "estimate": f"{case.get('estimate_minutes', 10)}m",
            "custom_steps": "\n".join(f"{j+1}. {s}" for j, s in enumerate(steps)),
            "custom_expected": "\n".join(expected),
            "custom_preconds": "\n".join(case.get("preconditions", [])),
            "refs": ",".join(case.get("trace_to", [])),
        }

        testrail_data["cases"].append(testrail_case)

    return testrail_data


def export_testrail_csv(testrail_data: dict[str, Any], output: Path) -> None:
    """Export to TestRail CSV import format."""
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            "Section", "Title", "Priority", "Estimate",
            "Preconditions", "Steps", "Expected Result", "Refs"
        ])

        # Cases
        section_name = testrail_data["sections"][0]["name"]
        for case in testrail_data["cases"]:
            writer.writerow([
                section_name,
                case["title"],
                f"P{5 - case['priority_id']}",  # Convert back to P0-P4
                case["estimate"],
                case.get("custom_preconds", ""),
                case["custom_steps"],
                case["custom_expected"],
                case.get("refs", ""),
            ])


def export_testrail_json(testrail_data: dict[str, Any], output: Path) -> None:
    """Export to TestRail JSON format."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(testrail_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export manual_case_set to TestRail format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to manual_case_set.json file",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        required=True,
        help="Output format: csv (import) or json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file path",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"export-testrail {__version__}",
    )

    args = parser.parse_args()

    try:
        case_set = load_case_set(args.input)
        testrail_data = convert_to_testrail(case_set)

        if args.format == "csv":
            export_testrail_csv(testrail_data, args.output)
        else:
            export_testrail_json(testrail_data, args.output)

        print(f"Exported: {args.output}")
        print(f"  Cases: {len(testrail_data['cases'])}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())