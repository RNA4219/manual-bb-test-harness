"""Validate specification documents for acceptance.

Checks each spec document for required sections, quality criteria, and consistency.

Usage:
    python scripts/validate-spec.py --input docs/specs/*.md
    python scripts/validate-spec.py --input docs/specs/spec-01-ci-cd-enhancement.md
    python scripts/validate-spec.py --all

Example:
    python scripts/validate-spec.py --all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

__version__ = "0.1.0"


# Required sections for each spec
REQUIRED_SECTIONS = [
    ("overview", ["概要", "Overview"]),
    ("purpose", ["目的", "Purpose"]),
    ("requirements", ["要件", "Requirements"]),
    ("design", ["設計", "Design"]),
    ("interface", ["インターフェース", "Interface"]),
    ("constraints", ["制約", "Constraints"]),
    ("test_cases", ["テスト観点", "Test", "テスト"]),
    ("acceptance", ["受入基準", "Acceptance", "受入"]),
]

# Quality criteria
QUALITY_CRITERIA = [
    ("has_priority_table", r"P0.*優先度|優先度.*P0|P0.*P1.*P2|\|.*P0.*\|", "Requirements table with P0/P1/P2 priorities"),
    ("has_cli_example", r"```bash|# CLI|bb-harness|python scripts", "CLI usage examples"),
    ("has_checklist", r"\- \[ \]", "Acceptance criteria checklist"),
    ("has_table", r"\|.+\|.+\|", "Table format for requirements/design"),
]


def load_spec(path: Path) -> str:
    """Load spec document content."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e


def check_required_sections(content: str) -> list[dict[str, Any]]:
    """Check if all required sections are present."""
    errors: list[dict[str, Any]] = []

    for section_id, section_names in REQUIRED_SECTIONS:
        found = False
        for name in section_names:
            # Check for ## heading
            pattern = rf"^##+ .*{name}"
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                found = True
                break

        if not found:
            errors.append({
                "section": section_id,
                "expected": section_names[0],
                "status": "missing",
                "message": f"Section '{section_names[0]}' not found",
            })

    return errors


def check_quality_criteria(content: str) -> list[dict[str, Any]]:
    """Check quality criteria."""
    results: list[dict[str, Any]] = []

    for criterion_id, pattern, description in QUALITY_CRITERIA:
        found = bool(re.search(pattern, content, re.MULTILINE))
        results.append({
            "criterion": criterion_id,
            "description": description,
            "status": "pass" if found else "fail",
        })

    return results


def check_requirements_table(content: str) -> dict[str, Any]:
    """Extract and validate requirements table."""
    # Find requirements section
    req_match = re.search(r"^##+ .*要件.*\n(.*?)(?=^##+ |\Z)", content, re.DOTALL | re.MULTILINE)

    if not req_match:
        return {"status": "missing", "requirements": []}

    req_section = req_match.group(1)

    # Extract table rows with P0/P1/P2
    requirements: list[dict[str, str]] = []
    for line in req_section.split("\n"):
        if "|" in line and re.search(r"P[0-3]", line):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and not parts[0].startswith("id"):
                requirements.append({
                    "id": parts[0] if parts else "",
                    "content": parts[1] if len(parts) > 1 else "",
                    "priority": parts[2] if len(parts) > 2 else "unknown",
                })

    # Count by priority
    p0_count = sum(1 for r in requirements if "P0" in r.get("priority", ""))
    p1_count = sum(1 for r in requirements if "P1" in r.get("priority", ""))

    return {
        "status": "found",
        "total": len(requirements),
        "p0_count": p0_count,
        "p1_count": p1_count,
        "requirements": requirements[:5],  # First 5 for preview
    }


def check_acceptance_criteria(content: str) -> dict[str, Any]:
    """Extract and validate acceptance criteria checklist."""
    # Find acceptance section
    acc_match = re.search(r"^##+ .*受入基準.*\n(.*?)(?=^##+ |\Z)", content, re.DOTALL | re.MULTILINE)

    if not acc_match:
        return {"status": "missing", "items": []}

    acc_section = acc_match.group(1)

    # Extract checklist items
    items: list[dict[str, str]] = []
    for line in acc_section.split("\n"):
        if line.strip().startswith("- [ ]"):
            items.append({
                "text": line.strip()[5:].strip(),
                "checked": False,
            })
        elif line.strip().startswith("- [x]"):
            items.append({
                "text": line.strip()[5:].strip(),
                "checked": True,
            })

    return {
        "status": "found",
        "total": len(items),
        "checked": sum(1 for i in items if i["checked"]),
        "unchecked": sum(1 for i in items if not i["checked"]),
        "items": items,
    }


def validate_spec(path: Path) -> dict[str, Any]:
    """Validate a single spec document."""
    content = load_spec(path)

    result: dict[str, Any] = {
        "file": path.name,
        "path": str(path),
        "sections": check_required_sections(content),
        "quality": check_quality_criteria(content),
        "requirements": check_requirements_table(content),
        "acceptance": check_acceptance_criteria(content),
    }

    # Calculate overall status
    section_errors = [s for s in result["sections"] if s["status"] == "missing"]
    quality_fails = [q for q in result["quality"] if q["status"] == "fail"]

    critical_errors = len(section_errors)
    quality_score = len([q for q in result["quality"] if q["status"] == "pass"]) / len(QUALITY_CRITERIA) * 100

    result["summary"] = {
        "section_errors": critical_errors,
        "quality_score": quality_score,
        "has_requirements": result["requirements"]["status"] == "found",
        "has_acceptance": result["acceptance"]["status"] == "found",
        "acceptance_items": result["acceptance"].get("total", 0),
        "overall": "pass" if critical_errors == 0 and quality_score >= 75 else "fail",
    }

    return result


def print_report(results: list[dict[str, Any]]) -> int:
    """Print validation report."""
    print("=" * 60)
    print("SPEC VALIDATION REPORT")
    print("=" * 60)

    total_pass = 0
    total_fail = 0

    for result in results:
        print(f"\n## {result['file']}")
        print("-" * 40)

        # Summary
        summary = result["summary"]
        status_icon = "[OK]" if summary["overall"] == "pass" else "[FAIL]"
        print(f"Overall: {status_icon} {summary['overall'].upper()}")
        print(f"Quality Score: {summary['quality_score']:.0f}%")

        # Section errors
        if summary["section_errors"] > 0:
            print(f"\nMissing Sections ({summary['section_errors']}):")
            for s in result["sections"]:
                if s["status"] == "missing":
                    print(f"  - {s['expected']}")

        # Quality criteria
        print(f"\nQuality Criteria:")
        for q in result["quality"]:
            icon = "[OK]" if q["status"] == "pass" else "[X]"
            print(f"  {icon} {q['criterion']}: {q['status']}")

        # Requirements
        req = result["requirements"]
        if req["status"] == "found":
            print(f"\nRequirements: {req['total']} items (P0: {req['p0_count']}, P1: {req['p1_count']})")
        else:
            print(f"\nRequirements: MISSING")

        # Acceptance criteria
        acc = result["acceptance"]
        if acc["status"] == "found":
            print(f"Acceptance Criteria: {acc['total']} items ({acc['unchecked']} unchecked)")
        else:
            print(f"Acceptance Criteria: MISSING")

        if summary["overall"] == "pass":
            total_pass += 1
        else:
            total_fail += 1

    # Final summary
    print("\n" + "=" * 60)
    print(f"TOTAL: {total_pass} PASS, {total_fail} FAIL")
    print("=" * 60)

    return 0 if total_fail == 0 else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate specification documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        nargs="+",
        help="Spec files to validate",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all specs in docs/specs/",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Output JSON report to file",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"validate-spec {__version__}",
    )

    args = parser.parse_args()

    try:
        # Determine input files
        if args.all:
            spec_dir = Path("docs/specs")
            if not spec_dir.exists():
                print(f"Error: {spec_dir} not found", file=sys.stderr)
                return 1
            input_files = list(spec_dir.glob("spec-*.md"))
        elif args.input:
            input_files = args.input
        else:
            print("Error: --input or --all required", file=sys.stderr)
            return 1

        if not input_files:
            print("Error: No spec files found", file=sys.stderr)
            return 1

        # Validate each spec
        results: list[dict[str, Any]] = []
        for path in input_files:
            print(f"Validating: {path}")
            result = validate_spec(path)
            results.append(result)

        # Print report
        exit_code = print_report(results)

        # Output JSON if requested
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(
                json.dumps(results, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            print(f"\nJSON report: {args.json}")

        return exit_code

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())