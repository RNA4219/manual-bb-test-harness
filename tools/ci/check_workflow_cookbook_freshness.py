#!/usr/bin/env python3
"""Check workflow-cookbook freshness for a repository.

This tool verifies that the workflow-cookbook knowledge map (index.json,
hot.json, caps/*.json) is fresh and consistent with the actual documents.

It checks:
1. All nodes in index.json have corresponding files
2. All nodes in index.json have corresponding caps/*.json files
3. metadata counts match actual counts
4. Tracked files changed in Git after last_verified are flagged as stale
   (non-Git files fall back to filesystem modification time)

Usage:
    python tools/ci/check_workflow_cookbook_freshness.py --repo /path/to/repo
    python tools/ci/check_workflow_cookbook_freshness.py --repo . --json
    python tools/ci/check_workflow_cookbook_freshness.py --repo . --strict

Exit codes:
    0: All checks passed
    1: Freshness issues detected or error occurred
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


def get_file_mtime_date(file_path: Path) -> str | None:
    """Get file modification time as date string (YYYY-MM-DD)."""
    if not file_path.exists():
        return None
    mtime = file_path.stat().st_mtime
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


def run_git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """Run Git in ``repo_path`` and return None when Git is unavailable."""
    try:
        return subprocess.run(
            ["git", "-C", str(repo_path), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def is_git_repository(repo_path: Path) -> bool:
    """Return whether ``repo_path`` is inside a Git work tree."""
    result = run_git(repo_path, "rev-parse", "--is-inside-work-tree")
    return result is not None and result.returncode == 0 and result.stdout.strip() == "true"


def is_git_tracked(repo_path: Path, file_path: Path) -> bool:
    """Return whether ``file_path`` is tracked by Git in ``repo_path``."""
    try:
        relative_path = file_path.relative_to(repo_path).as_posix()
    except ValueError:
        return False
    result = run_git(repo_path, "ls-files", "--error-unmatch", "--", relative_path)
    return result is not None and result.returncode == 0


def get_git_last_change_date(repo_path: Path, file_path: Path) -> str | None:
    """Return a tracked file's latest committed change date (YYYY-MM-DD)."""
    try:
        relative_path = file_path.relative_to(repo_path).as_posix()
    except ValueError:
        return None
    result = run_git(repo_path, "log", "-1", "--format=%cs", "--", relative_path)
    if result is None or result.returncode != 0:
        return None
    change_date = result.stdout.strip()
    return change_date or None


def load_json(file_path: Path) -> dict[str, Any] | None:
    """Load JSON file safely."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def normalize_node_id_to_caps_name(node_id: str) -> str:
    """Convert node ID to caps filename.

    Example:
        "skills/manual-bb-test-harness/SKILL.md" ->
        "skills.manual-bb-test-harness.SKILL.md.json"
    Example: "docs/specs/spec-01.md" -> "docs.specs.spec-01.md.json"
    """
    # Replace path separators with dots
    return node_id.replace("/", ".").replace("\\", ".") + ".json"


def get_short_caps_name(node_id: str) -> str:
    """Get short caps filename (last component only).

    Example: "skills/manual-bb-test-harness/SKILL.md" -> "SKILL.md.json"
    Example: "README.md" -> "README.md.json"
    """
    # Get last component (filename)
    parts = node_id.replace("\\", "/").split("/")
    return parts[-1] + ".json"


def find_caps_file(caps_dir: Path, node_id: str) -> Path | None:
    """Find caps file for a node, accepting both full and short names.

    Returns:
        Path to caps file if found, None otherwise
    """
    full_name = normalize_node_id_to_caps_name(node_id)
    short_name = get_short_caps_name(node_id)

    # Try full name first
    full_path = caps_dir / full_name
    if full_path.exists():
        return full_path

    # Try short name (for top-level docs in skills subdirectory)
    short_path = caps_dir / short_name
    if short_path.exists():
        return short_path

    return None


def check_freshness(repo_path: Path) -> dict[str, Any]:
    """Check workflow-cookbook freshness.

    Returns:
        Dictionary with freshness check results
    """
    result = {
        "repo": str(repo_path),
        "passed": True,
        "checks": {},
        "missing_files": [],
        "missing_caps": [],
        "stale_caps": [],
        "hot_node_issues": [],
        "date_issues": [],
        "overdue_reviews": [],
        "metadata_mismatch": [],
        "errors": [],
    }

    workflow_cookbook_dir = repo_path / "docs" / "workflow-cookbook"
    caps_dir = workflow_cookbook_dir / "caps"
    git_repository = is_git_repository(repo_path)

    # Check directory exists
    if not workflow_cookbook_dir.exists():
        result["passed"] = False
        result["errors"].append("docs/workflow-cookbook directory not found")
        return result

    # Load index.json
    index_json = workflow_cookbook_dir / "index.json"
    index_data = load_json(index_json)

    if index_data is None:
        result["passed"] = False
        result["errors"].append("index.json not found or invalid JSON")
        return result

    # Check metadata counts
    metadata = index_data.get("metadata", {})
    nodes = index_data.get("nodes", [])
    edges = index_data.get("edges", [])

    actual_node_count = len(nodes)
    actual_edge_count = len(edges)
    metadata_node_count = metadata.get("total_nodes", 0)
    metadata_edge_count = metadata.get("total_edges", 0)

    # Check caps count
    actual_caps_count = 0
    if caps_dir.exists():
        actual_caps_count = len(list(caps_dir.glob("*.json")))
    metadata_caps_count = metadata.get("total_capsules", 0)

    def require_iso(label: str, value: object) -> None:
        if not isinstance(value, str):
            result["date_issues"].append(f"{label}: missing ISO 8601 value")
            result["passed"] = False
            return
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            result["date_issues"].append(f"{label}: {value!r} is not ISO 8601")
            result["passed"] = False

    require_iso("index.generated_at", index_data.get("generated_at"))
    require_iso("index.metadata.last_updated", metadata.get("last_updated"))
    result["checks"]["metadata"] = {
        "nodes": {
            "actual": actual_node_count,
            "metadata": metadata_node_count,
            "match": actual_node_count == metadata_node_count,
        },
        "edges": {
            "actual": actual_edge_count,
            "metadata": metadata_edge_count,
            "match": actual_edge_count == metadata_edge_count,
        },
        "capsules": {
            "actual": actual_caps_count,
            "metadata": metadata_caps_count,
            "match": actual_caps_count == metadata_caps_count,
        },
    }

    if actual_node_count != metadata_node_count:
        result["passed"] = False
        result["metadata_mismatch"].append(
            f"total_nodes: metadata={metadata_node_count}, actual={actual_node_count}"
        )

    if actual_caps_count != metadata_caps_count:
        result["passed"] = False
        result["metadata_mismatch"].append(
            f"total_capsules: metadata={metadata_caps_count}, actual={actual_caps_count}"
        )

    readme_path = repo_path / "README.md"
    readme_test_count: int | None = None
    if readme_path.exists():
        readme = readme_path.read_text(encoding="utf-8")
        count_match = re.search(r"\((\d+) nodes,\s*(\d+) edges\)", readme)
        if not count_match:
            result["metadata_mismatch"].append("README knowledge-map counts not found")
            result["passed"] = False
        else:
            readme_nodes, readme_edges = map(int, count_match.groups())
            if (readme_nodes, readme_edges) != (actual_node_count, actual_edge_count):
                result["metadata_mismatch"].append(
                    "README counts: "
                    f"nodes={readme_nodes}, edges={readme_edges}; "
                    f"index nodes={actual_node_count}, edges={actual_edge_count}"
                )
                result["passed"] = False
        test_count_match = re.search(r"検証済みテスト:\s*\*\*(\d+)件\*\*", readme)
        if test_count_match:
            readme_test_count = int(test_count_match.group(1))
        else:
            result["metadata_mismatch"].append("README test-count marker not found")
            result["passed"] = False

    hot_data = load_json(workflow_cookbook_dir / "hot.json")
    hot_test_count: int | None = None
    if hot_data is None:
        result["hot_node_issues"].append("hot.json not found or invalid JSON")
        result["passed"] = False
    else:
        require_iso("hot.generated_at", hot_data.get("generated_at"))
        project_status = hot_data.get("project_status", {})
        hot_test_count = project_status.get("test_count")
        require_iso("hot.project_status.last_updated", project_status.get("last_updated"))
        if project_status.get("total_capsules") != actual_caps_count:
            result["metadata_mismatch"].append(
                "hot total_capsules: "
                f"metadata={project_status.get('total_capsules')}, actual={actual_caps_count}"
            )
            result["passed"] = False
        if readme_test_count is None or project_status.get("test_count") != readme_test_count:
            result["metadata_mismatch"].append(
                "test_count mismatch: "
                f"README={readme_test_count}, hot={project_status.get('test_count')}"
            )
            result["passed"] = False
        node_ids = {node.get("id") for node in nodes}
        for hot_node in hot_data.get("hot_nodes", []):
            hot_id = hot_node.get("id", "")
            hot_path = hot_node.get("path", "")
            if hot_id not in node_ids:
                result["hot_node_issues"].append(f"hot node not in index: {hot_id}")
                result["passed"] = False
            resolved = repo_path / hot_path.removeprefix("./")
            if not resolved.exists():
                result["hot_node_issues"].append(f"hot node path missing: {hot_path}")
                result["passed"] = False

    result["checks"]["metadata"]["test_count"] = {
        "actual": readme_test_count,
        "metadata": hot_test_count,
        "match": readme_test_count is not None and readme_test_count == hot_test_count,
    }

    for document in repo_path.glob("*.md"):
        content = document.read_text(encoding="utf-8")
        for value in re.findall(
            r"^next_review_due:\s*[\"']?([^\"'\s]+)", content, re.MULTILINE
        ):
            try:
                due = date.fromisoformat(value)
            except ValueError:
                result["date_issues"].append(
                    f"{document.name}.next_review_due: {value!r} is not ISO 8601"
                )
                result["passed"] = False
                continue
            if due < date.today():
                result["overdue_reviews"].append(
                    f"{document.name}: next_review_due={value}"
                )
                result["passed"] = False
    # Check each node
    for node in nodes:
        node_id = node.get("id", "")
        node_path = node.get("path", "")

        # Convert path to absolute
        if node_path.startswith("./"):
            file_path = repo_path / node_path[2:]
        else:
            file_path = repo_path / node_path

        # Check file exists
        if not file_path.exists():
            result["passed"] = False
            result["missing_files"].append(node_id)
            continue

        # Check caps file exists (accept both full and short names)
        caps_file = find_caps_file(caps_dir, node_id)

        if caps_file is None:
            result["passed"] = False
            result["missing_caps"].append(node_id)
            continue

        # Check freshness against Git history for tracked files. GitHub Actions
        # assigns checkout time as mtime to every file, so mtime alone is not a
        # reliable change signal in CI. Non-Git fixture repositories retain the
        # original mtime fallback for standalone use.
        caps_data = load_json(caps_file)
        if caps_data is None:
            result["passed"] = False
            result["errors"].append(
                f"Caps file invalid JSON: {caps_file.name}"
            )
            continue

        change_source = "mtime"
        if git_repository and is_git_tracked(repo_path, file_path):
            file_change_date = get_git_last_change_date(repo_path, file_path)
            change_source = "git"
            if file_change_date is None:
                result["passed"] = False
                result["errors"].append(
                    f"Git history unavailable for tracked file: {node_id}"
                )
                continue
        else:
            file_change_date = get_file_mtime_date(file_path)
        last_verified = caps_data.get("last_verified", "")

        if file_change_date and last_verified:
            # Compare dates
            try:
                file_date = datetime.strptime(file_change_date, "%Y-%m-%d")
                verified_date = datetime.strptime(last_verified, "%Y-%m-%d")

                if file_date > verified_date:
                    result["stale_caps"].append({
                        "node_id": node_id,
                        "file_change_date": file_change_date,
                        "change_source": change_source,
                        "last_verified": last_verified,
                    })
                    # Note: stale doesn't cause failure unless --strict
            except (TypeError, ValueError):
                msg = f"Invalid date format for {node_id}: "
                msg += f"changed={file_change_date}, verified={last_verified}"
                result["errors"].append(msg)

    # Check for orphan caps files (caps without corresponding nodes)
    if caps_dir.exists():
        existing_caps = set(c.name for c in caps_dir.glob("*.json"))

        # Build expected caps names (both full and short)
        expected_caps = set()
        for n in nodes:
            node_id = n.get("id", "")
            expected_caps.add(normalize_node_id_to_caps_name(node_id))
            expected_caps.add(get_short_caps_name(node_id))

        orphan_caps = existing_caps - expected_caps
        if orphan_caps:
            result["checks"]["orphan_caps"] = list(orphan_caps)

    result["checks"]["summary"] = {
        "total_nodes": actual_node_count,
        "total_caps": actual_caps_count,
        "missing_files_count": len(result["missing_files"]),
        "missing_caps_count": len(result["missing_caps"]),
        "stale_caps_count": len(result["stale_caps"]),
    }

    return result


def format_text_output(result: dict[str, Any], strict: bool = False) -> str:
    """Format freshness check result as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Workflow Cookbook Freshness Check")
    lines.append("=" * 60)
    lines.append(f"Repository: {result['repo']}")

    status = "[PASS]" if result["passed"] else "[FAIL]"
    lines.append(f"Overall Status: {status}")
    lines.append("")

    # Metadata checks
    if "metadata" in result.get("checks", {}):
        lines.append("Metadata Consistency:")
        meta = result["checks"]["metadata"]

        for key in ["nodes", "edges", "capsules", "test_count"]:
            data = meta.get(key, {})
            match = data.get("match", False)
            status = "[OK]" if match else "[!!]"
            meta_val = data.get("metadata", 0)
            actual_val = data.get("actual", 0)
            lines.append(f"  {status} {key}: metadata={meta_val}, actual={actual_val}")
        lines.append("")

    # Missing files
    if result["missing_files"]:
        lines.append("Missing Files (nodes without actual files):")
        for node_id in result["missing_files"]:
            lines.append(f"  [!!] {node_id}")
        lines.append("")

    # Missing caps
    if result["missing_caps"]:
        lines.append("Missing Capsules (nodes without caps/*.json):")
        for node_id in result["missing_caps"]:
            lines.append(f"  [!!] {node_id}")
        lines.append("")

    # Stale caps
    if result["stale_caps"]:
        lines.append("Stale Capsules (file changed after last_verified):")
        for stale in result["stale_caps"]:
            stale_msg = f"  [STALE] {stale['node_id']}: "
            stale_msg += (
                f"changed={stale['file_change_date']} ({stale['change_source']}), "
                f"verified={stale['last_verified']}"
            )
            lines.append(stale_msg)
        if strict:
            lines.append("  (Strict mode: treating as FAIL)")
        lines.append("")

    # Orphan caps
    if result["checks"].get("orphan_caps"):
        lines.append("Orphan Capsules (caps without corresponding nodes):")
        for caps_name in result["checks"]["orphan_caps"]:
            lines.append(f"  [ORPHAN] {caps_name}")
        lines.append("")

    # Errors
    if result["errors"]:
        lines.append("Errors:")
        for error in result["errors"]:
            lines.append(f"  [ERR] {error}")
        lines.append("")

    for heading, key in (
        ("Knowledge-map Metadata Issues", "metadata_mismatch"),
        ("Hot Node Issues", "hot_node_issues"),
        ("Date Issues", "date_issues"),
        ("Overdue Reviews", "overdue_reviews"),
    ):
        if result.get(key):
            lines.append(f"{heading}:")
            lines.extend(f"  [!!] {item}" for item in result[key])
            lines.append("")
    # Summary
    summary = result.get("checks", {}).get("summary", {})
    if summary:
        lines.append("Summary:")
        lines.append(f"  Nodes: {summary.get('total_nodes', 0)}")
        lines.append(f"  Capsules: {summary.get('total_caps', 0)}")
        lines.append(f"  Missing Files: {summary.get('missing_files_count', 0)}")
        lines.append(f"  Missing Capsules: {summary.get('missing_caps_count', 0)}")
        lines.append(f"  Stale Capsules: {summary.get('stale_caps_count', 0)}")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check workflow-cookbook freshness for a repository",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tools/ci/check_workflow_cookbook_freshness.py --repo .
    python tools/ci/check_workflow_cookbook_freshness.py --repo /path/to/repo --json
    python tools/ci/check_workflow_cookbook_freshness.py --repo . --strict

Exit codes:
    0: All checks passed
    1: Freshness issues detected or error occurred
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
        "--strict",
        action="store_true",
        help="Treat stale capsules as failures (file changed after last_verified)",
    )

    args = parser.parse_args()

    # Validate repository path
    if not args.repo.exists():
        print(f"Error: Repository path does not exist: {args.repo}", file=sys.stderr)
        return 1

    if not args.repo.is_dir():
        print(f"Error: Repository path is not a directory: {args.repo}", file=sys.stderr)
        return 1

    # Check freshness
    try:
        result = check_freshness(args.repo)
    except Exception as e:
        print(f"Error checking freshness: {e}", file=sys.stderr)
        return 1

    # Apply strict mode
    if args.strict and result["stale_caps"]:
        result["passed"] = False

    # Output results
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_text_output(result, args.strict))

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
