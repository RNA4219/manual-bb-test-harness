#!/usr/bin/env python3
"""Check workflow-cookbook tier for a repository.

This tool analyzes a repository to determine its workflow-cookbook tier
(Tier 0-3) and reports which requirements are met and which are missing.

Usage:
    python tools/ci/check_workflow_cookbook_tier.py --repo /path/to/repo
    python tools/ci/check_workflow_cookbook_tier.py --repo . --json
    python tools/ci/check_workflow_cookbook_tier.py --repo . --expected-tier 2

Exit codes:
    0: Repository meets or exceeds expected tier
    1: Repository below expected tier or error occurred
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Tier definitions with required files/directories
TIER_REQUIREMENTS = {
    0: {
        "name": "Tier 0: Basic",
        "description": "Minimal documentation",
        "files": ["README.md"],
        "directories": [],
    },
    1: {
        "name": "Tier 1: Structured",
        "description": "Structured documentation with navigation",
        "files": ["README.md", "HUB.codex.md", "BLUEPRINT.md"],
        "directories": [],
    },
    2: {
        "name": "Tier 2: Operational",
        "description": "Operational procedures and evaluation criteria",
        "files": [
            "README.md",
            "HUB.codex.md",
            "BLUEPRINT.md",
            "RUNBOOK.md",
            "GUARDRAILS.md",
            "EVALUATION.md",
        ],
        "directories": [],
    },
    3: {
        "name": "Tier 3: Complete",
        "description": "Complete traceability with acceptance records and knowledge maps",
        "files": [
            "README.md",
            "HUB.codex.md",
            "BLUEPRINT.md",
            "RUNBOOK.md",
            "GUARDRAILS.md",
            "EVALUATION.md",
        ],
        "directories": ["docs/acceptance", "docs/tasks", "docs/workflow-cookbook"],
    },
}


def check_file_exists(repo_path: Path, file_path: str) -> bool:
    """Check if a file exists in the repository."""
    return (repo_path / file_path).is_file()


def check_directory_exists(repo_path: Path, dir_path: str) -> bool:
    """Check if a directory exists in the repository."""
    return (repo_path / dir_path).is_dir()


def analyze_tier(repo_path: Path) -> dict[str, Any]:
    """Analyze repository and determine adoption tier.

    Returns:
        Dictionary with tier analysis results
    """
    result = {
        "repo": str(repo_path),
        "tier": 0,
        "tier_name": TIER_REQUIREMENTS[0]["name"],
        "requirements": {},
        "missing": [],
        "recommendations": [],
    }

    # Check each tier from highest to lowest
    for tier_level in sorted(TIER_REQUIREMENTS.keys(), reverse=True):
        tier_reqs = TIER_REQUIREMENTS[tier_level]
        missing_files = []
        missing_dirs = []

        # Check required files
        for file_path in tier_reqs["files"]:
            if not check_file_exists(repo_path, file_path):
                missing_files.append(file_path)

        # Check required directories
        for dir_path in tier_reqs["directories"]:
            if not check_directory_exists(repo_path, dir_path):
                missing_dirs.append(dir_path)

        # Store requirements status
        result["requirements"][f"tier_{tier_level}"] = {
            "name": tier_reqs["name"],
            "description": tier_reqs["description"],
            "files": {
                f: check_file_exists(repo_path, f) for f in tier_reqs["files"]
            },
            "directories": {
                d: check_directory_exists(repo_path, d) for d in tier_reqs["directories"]
            },
            "missing_files": missing_files,
            "missing_directories": missing_dirs,
        }

        # If all requirements met, this is the tier
        if not missing_files and not missing_dirs:
            result["tier"] = tier_level
            result["tier_name"] = tier_reqs["name"]
            break

    # Determine what's missing for next tier
    current_tier = result["tier"]
    if current_tier < 3:
        next_tier = current_tier + 1
        next_reqs = TIER_REQUIREMENTS[next_tier]
        tier_reqs = result["requirements"][f"tier_{next_tier}"]

        result["missing"] = (
            tier_reqs["missing_files"] + tier_reqs["missing_directories"]
        )

        # Generate recommendations
        if tier_reqs["missing_files"]:
            result["recommendations"].append(
                f"Add missing files for {next_reqs['name']}: "
                + ", ".join(tier_reqs["missing_files"])
            )
        if tier_reqs["missing_directories"]:
            result["recommendations"].append(
                f"Create missing directories for {next_reqs['name']}: "
                + ", ".join(tier_reqs["missing_directories"])
            )

    # Additional checks for Tier 3
    if current_tier == 3:
        workflow_cookbook_dir = repo_path / "docs" / "workflow-cookbook"
        if workflow_cookbook_dir.exists():
            index_json = workflow_cookbook_dir / "index.json"
            hot_json = workflow_cookbook_dir / "hot.json"
            caps_dir = workflow_cookbook_dir / "caps"

            workflow_cookbook_status = {
                "index.json": index_json.is_file(),
                "hot.json": hot_json.is_file(),
                "caps/": caps_dir.is_dir(),
            }

            if caps_dir.is_dir():
                caps_count = len(list(caps_dir.glob("*.json")))
                workflow_cookbook_status["caps_count"] = caps_count

            result["workflow_cookbook_status"] = workflow_cookbook_status

            # Check if index.json is valid
            if index_json.is_file():
                try:
                    with open(index_json, encoding="utf-8") as f:
                        index_data = json.load(f)
                    result["workflow_cookbook_status"]["index_valid"] = True
                    result["workflow_cookbook_status"]["nodes"] = index_data.get(
                        "metadata", {}
                    ).get("total_nodes", 0)
                    result["workflow_cookbook_status"]["edges"] = index_data.get(
                        "metadata", {}
                    ).get("total_edges", 0)
                except (json.JSONDecodeError, KeyError):
                    result["workflow_cookbook_status"]["index_valid"] = False

    return result


def format_text_output(result: dict[str, Any]) -> str:
    """Format analysis result as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Workflow Cookbook Adoption Tier Check")
    lines.append("=" * 60)
    lines.append(f"Repository: {result['repo']}")
    lines.append(f"Current Tier: {result['tier_name']}")
    lines.append("")

    # Show requirements for each tier
    for tier_level in sorted(result["requirements"].keys()):
        tier_key = tier_level
        tier_data = result["requirements"][tier_key]
        tier_num = int(tier_key.split("_")[1])

        status = "[OK]" if tier_num <= result["tier"] else "[  ]"
        lines.append(f"{status} {tier_data['name']}: {tier_data['description']}")

        # Show file status for tiers above current
        if tier_num > result["tier"]:
            for file_path, exists in tier_data["files"].items():
                file_status = "[OK]" if exists else "[  ]"
                lines.append(f"    {file_status} {file_path}")

            for dir_path, exists in tier_data["directories"].items():
                dir_status = "[OK]" if exists else "[  ]"
                lines.append(f"    {dir_status} {dir_path}/")

    # Show missing items
    if result["missing"]:
        lines.append("")
        lines.append("Missing for Next Tier:")
        for item in result["missing"]:
            lines.append(f"  - {item}")

    # Show recommendations
    if result["recommendations"]:
        lines.append("")
        lines.append("Recommendations:")
        for rec in result["recommendations"]:
            lines.append(f"  - {rec}")

    # Show workflow cookbook status for Tier 3
    if "workflow_cookbook_status" in result:
        lines.append("")
        lines.append("Workflow Cookbook Status:")
        bs = result["workflow_cookbook_status"]
        lines.append(f"  index.json: {'[OK]' if bs.get('index.json') else '[  ]'}")
        lines.append(f"  hot.json: {'[OK]' if bs.get('hot.json') else '[  ]'}")
        lines.append(f"  caps/: {'[OK]' if bs.get('caps/') else '[  ]'}")

        if "caps_count" in bs:
            lines.append(f"  Capsule count: {bs['caps_count']}")

        if bs.get("index_valid"):
            lines.append(f"  Nodes: {bs.get('nodes', 0)}")
            lines.append(f"  Edges: {bs.get('edges', 0)}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check workflow-cookbook tier for a repository",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tools/ci/check_workflow_cookbook_tier.py --repo .
    python tools/ci/check_workflow_cookbook_tier.py --repo /path/to/repo --json
    python tools/ci/check_workflow_cookbook_tier.py --repo . --expected-tier 2

Exit codes:
    0: Repository meets or exceeds expected tier
    1: Repository below expected tier or error occurred
""",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="Path to repository to check",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--expected-tier",
        type=int,
        choices=[0, 1, 2, 3],
        default=0,
        help="Expected minimum tier (exit code 1 if not met)",
    )

    args = parser.parse_args()

    # Validate repository path
    if not args.repo.exists():
        print(f"Error: Repository path does not exist: {args.repo}", file=sys.stderr)
        return 1

    if not args.repo.is_dir():
        print(f"Error: Repository path is not a directory: {args.repo}", file=sys.stderr)
        return 1

    # Analyze repository
    try:
        result = analyze_tier(args.repo)
    except Exception as e:
        print(f"Error analyzing repository: {e}", file=sys.stderr)
        return 1

    # Output results
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_text_output(result))

    # Check expected tier
    if result["tier"] < args.expected_tier:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
