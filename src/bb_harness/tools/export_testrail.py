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
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from bb_harness import __version__
from bb_harness.tools._shared.io_common import load_json


def _case_identity(case_set: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Build the immutable identity fields carried through external execution."""
    case_id = str(case.get("tc_id") or "UNKNOWN")
    case_revision = str(case.get("revision") or "unversioned")
    canonical_case = {key: value for key, value in case.items() if key != "content_hash"}
    content_hash = case.get("content_hash") or "sha256:" + hashlib.sha256(
        json.dumps(canonical_case, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    oracle = case.get("oracle")
    oracle_refs = (
        case.get("oracle_refs")
        or (oracle.get("refs") if isinstance(oracle, dict) else None)
        or case.get("trace_to")
        or [case_id]
    )
    return {
        "case_revision": case_revision,
        "spec_revision": str(case.get("spec_revision") or case_set.get("spec_revision") or "unversioned"),
        "oracle_revision": str(case.get("oracle_revision") or case_revision),
        "case_content_hash": str(content_hash),
        "oracle_refs": [str(ref) for ref in oracle_refs],
    }


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

        identity = _case_identity(case_set, case)
        testrail_case: dict[str, Any] = {
            "id": i,
            "section_id": 1,
            "source_case_id": case.get("tc_id", ""),
            "source_feature_id": feature_id,
            **identity,
            "title": case.get("title", f"Test Case {i}"),
            "priority_id": priority_int,
            "estimate": f"{case.get('estimate_minutes', 10)}m",
            "custom_steps": "\n".join(f"{j + 1}. {s}" for j, s in enumerate(steps)),
            "custom_expected": "\n".join(expected),
            "custom_preconds": "\n".join(case.get("preconditions", [])),
            "refs": ",".join(case.get("trace_to", [])),
            "custom_status": case.get("status", "active"),
            "custom_retired_reason": case.get("retired_reason", ""),
            "custom_replacement_refs": ",".join(case.get("replacement_refs", [])),
            "custom_placement_change_ref": case.get("placement_change_ref", ""),
        }

        testrail_data["cases"].append(testrail_case)

    return testrail_data


def export_testrail_csv(testrail_data: dict[str, Any], output: Path) -> None:
    """Export to TestRail CSV import format."""
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(
            [
                "Section",
                "Title",
                "Priority",
                "Estimate",
                "Preconditions",
                "Steps",
                "Expected Result",
                "Refs",
                "Status",
                "Retired Reason",
                "Replacement Refs",
                "Placement Change Ref",
                "Source Case ID",
                "Source Feature ID",
                "Case Revision",
                "Spec Revision",
                "Oracle Revision",
                "Case Content Hash",
                "Oracle Refs",
            ]
        )

        # Cases
        section_name = testrail_data["sections"][0]["name"]
        for case in testrail_data["cases"]:
            writer.writerow(
                [
                    section_name,
                    case["title"],
                    f"P{5 - case['priority_id']}",  # Convert back to P0-P4
                    case["estimate"],
                    case.get("custom_preconds", ""),
                    case["custom_steps"],
                    case["custom_expected"],
                    case.get("refs", ""),
                    case.get("custom_status", "active"),
                    case.get("custom_retired_reason", ""),
                    case.get("custom_replacement_refs", ""),
                    case.get("custom_placement_change_ref", ""),
                    case.get("source_case_id", ""),
                    case.get("source_feature_id", ""),
                    case.get("case_revision", ""),
                    case.get("spec_revision", ""),
                    case.get("oracle_revision", ""),
                    case.get("case_content_hash", ""),
                    ",".join(case.get("oracle_refs", [])),
                ]
            )


def export_testrail_json(testrail_data: dict[str, Any], output: Path) -> None:
    """Export to TestRail JSON format."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(testrail_data, indent=2, ensure_ascii=False), encoding="utf-8")


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
        case_set = load_json(args.input)
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
