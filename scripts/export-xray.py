"""Export manual_case_set.json to Xray JSON format for Jira import.

Usage:
    python scripts/export-xray.py --input <manual_case_set.json> --output <file.json>

Example:
    python scripts/export-xray.py \
        --input examples/artifacts/order-cancel.manual_case_set.json \
        --output exports/xray-order-cancel.json
"""

from __future__ import annotations

import argparse
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


def convert_to_xray(case_set: dict[str, Any]) -> dict[str, Any]:
    """Convert manual_case_set to Xray JSON format.

    Xray format for Jira import:
    - tests: list of test issues
    - Each test has: summary, steps, labels, priority
    """
    feature_id = case_set.get("feature_id", "UNKNOWN")
    cases = case_set.get("manual_cases", [])
    charters = case_set.get("exploratory_charters", [])

    xray_data: dict[str, Any] = {
        "tests": [],
        "preconditions": [],
    }

    # Add precondition as separate element if present
    all_preconds: set[str] = set()
    for case in cases:
        for cond in case.get("preconditions", []):
            all_preconds.add(cond)

    if all_preconds:
        xray_data["preconditions"] = [
            {"summary": cond, "tests": []} for cond in sorted(all_preconds)
        ]

    # Convert manual cases to Xray tests
    for case in cases:
        # Map priority
        priority_map = {"P0": "Highest", "P1": "High", "P2": "Medium", "P3": "Low", "P4": "Lowest"}
        priority_str = case.get("priority", "P2")
        priority_xray = priority_map.get(priority_str, "Medium")

        # Build step definitions
        steps = case.get("steps", [])
        expected = case.get("expected_results", [])

        # Xray expects steps as action-result pairs
        xray_steps: list[dict[str, Any]] = []
        for i, action in enumerate(steps):
            step: dict[str, Any] = {
                "action": action,
                "result": expected[i] if i < len(expected) else "",
            }
            xray_steps.append(step)

        # If more expected than steps, add to last step
        if len(expected) > len(steps) and steps:
            xray_steps[-1]["result"] = "\n".join(expected[len(steps)-1:])

        xray_test: dict[str, Any] = {
            "summary": case.get("title", case.get("tc_id", "Test")),
            "steps": xray_steps,
            "labels": [feature_id] + case.get("trace_to", []),
            "priority": priority_xray,
            "testType": "Manual",
        }

        # Link precondition if present
        preconds = case.get("preconditions", [])
        if preconds:
            xray_test["preconditions"] = preconds

        xray_data["tests"].append(xray_test)

    # Add exploratory charters as tests with special type
    for charter in charters:
        charter_test: dict[str, Any] = {
            "summary": charter.get("title", charter.get("id", "Exploratory")),
            "steps": [
                {
                    "action": f"Explore: {charter.get('scope', '')}",
                    "result": f"Questions: {', '.join(charter.get('questions', []))}",
                }
            ],
            "labels": [feature_id, "exploratory"] + charter.get("trace_to", []),
            "priority": "Medium",
            "testType": "Exploratory",
            "estimate": f"{charter.get('estimate_minutes', 30)}m",
        }
        xray_data["tests"].append(charter_test)

    return xray_data


def export_xray_json(xray_data: dict[str, Any], output: Path) -> None:
    """Export to Xray JSON format."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(xray_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export manual_case_set to Xray format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to manual_case_set.json file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"export-xray {__version__}",
    )

    args = parser.parse_args()

    try:
        case_set = load_case_set(args.input)
        xray_data = convert_to_xray(case_set)
        export_xray_json(xray_data, args.output)

        print(f"Exported: {args.output}")
        print(f"  Tests: {len(xray_data['tests'])}")
        print(f"  Preconditions: {len(xray_data['preconditions'])}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())