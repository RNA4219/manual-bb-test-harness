"""Import Xray (Jira) test results to execution_evidence format.

Usage:
    python scripts/import-xray.py --exec <key> --output <dir>
    python scripts/import-xray.py --project <key> --date-range <start> <end> --output <dir>
    python scripts/import-xray.py --version

Environment:
    JIRA_URL: Base URL (e.g., https://company.atlassian.net)
    JIRA_USER: Username or email
    JIRA_API_KEY: API token

Example:
    export JIRA_URL="https://company.atlassian.net"
    export JIRA_USER="qa_lead@company.com"
    export JIRA_API_KEY="xxx"

    python scripts/import-xray.py --exec PROJ-TE-123 --output execution_evidence/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

__version__ = "0.1.0"

# Xray status mapping
XRAY_STATUS_MAP = {
    "PASS": "pass",
    "FAIL": "fail",
    "ABORTED": "blocked",
    "TODO": "skip",
    "EXECUTING": "unknown",
    "PENDING": "skip",
}

# Jira priority to severity mapping
JIRA_PRIORITY_MAP = {
    "Highest": "blocker",
    "High": "critical",
    "Medium": "high",
    "Low": "medium",
    "Lowest": "low",
}


def get_jira_client() -> tuple[str, dict[str, str], tuple[str, str] | None]:
    """Get Jira/Xray API credentials from environment."""
    base_url = os.environ.get("JIRA_URL", "")
    if not base_url:
        raise ValueError("JIRA_URL environment variable required")

    user = os.environ.get("JIRA_USER", "")
    api_key = os.environ.get("JIRA_API_KEY", "")

    if not user or not api_key:
        raise ValueError("JIRA_USER and JIRA_API_KEY environment variables required")

    headers = {"Content-Type": "application/json"}
    auth = (user, api_key)

    return base_url.rstrip("/"), headers, auth


def fetch_test_execution(base_url: str, headers: dict[str, str], auth: tuple[str, str], exec_key: str) -> dict[str, Any]:
    """Fetch Xray test execution details."""
    try:
        import requests
    except ImportError:
        raise ValueError("requests library required: pip install requests")

    # Xray Cloud API
    url = f"{base_url}/rest/raven/2.0/api/testexec/{exec_key}"
    response = requests.get(url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_jira_issue(base_url: str, headers: dict[str, str], auth: tuple[str, str], issue_key: str) -> dict[str, Any]:
    """Fetch Jira issue details."""
    try:
        import requests
    except ImportError:
        raise ValueError("requests library required: pip install requests")

    url = f"{base_url}/rest/api/2/issue/{issue_key}"
    response = requests.get(url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()
    return response.json()


def convert_to_execution_evidence(
    testrun: dict[str, Any],
    exec_key: str,
    test_key: str,
) -> dict[str, Any]:
    """Convert Xray testrun to execution_evidence format."""
    status = testrun.get("status", "TODO")
    result_status = XRAY_STATUS_MAP.get(status, "unknown")

    evidence: dict[str, Any] = {
        "run_id": f"XRAY-{exec_key}-{test_key}",
        "tc_id": test_key,
        "feature_id": "IMPORTED",  # User should set this
        "tester": testrun.get("executedBy", "unknown"),
        "result": result_status,
    }

    # Add timestamps
    started = testrun.get("startedOn", "")
    finished = testrun.get("finishedOn", "")
    if started:
        evidence["timestamp"] = started
    if started and finished:
        # Calculate duration
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            finish_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            duration_min = (finish_dt - start_dt).total_seconds() / 60
            evidence["time_spent_minutes"] = duration_min
        except Exception:
            pass

    # Add defect stub if failed
    if result_status == "fail":
        defects = testrun.get("defects", [])
        if defects:
            defect_key = defects[0] if isinstance(defects, list) else defects
            evidence["defect_stub"] = {
                "title": f"Defect {defect_key}",
                "severity": "high",  # Default
            }

    # Add evidences/attachments
    attachments = testrun.get("evidences", [])
    if attachments:
        evidence["attachments"] = [a.get("url", "") for a in attachments if isinstance(a, dict)]

    # Add comment
    comment = testrun.get("comment", "")
    if comment:
        evidence["anomaly_notes"] = [comment]

    return evidence


def import_xray_results(exec_key: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Import Xray results and convert to execution_evidence."""
    base_url, headers, auth = get_jira_client()

    # Fetch test execution
    exec_data = fetch_test_execution(base_url, headers, auth, exec_key)

    results: list[dict[str, Any]] = []
    stats = {
        "source": "xray",
        "execution_key": exec_key,
        "imported_count": 0,
        "pass_count": 0,
        "fail_count": 0,
        "skip_count": 0,
        "blocked_count": 0,
    }

    tests = exec_data.get("tests", [])
    for testrun in tests:
        test_key = testrun.get("testKey", "")
        if not test_key:
            # Try alternate field
            test_key = testrun.get("test", {}).get("key", "")

        if not test_key:
            continue

        evidence = convert_to_execution_evidence(testrun, exec_key, test_key)
        results.append(evidence)

        # Update stats
        stats["imported_count"] += 1
        mapped_status = XRAY_STATUS_MAP.get(testrun.get("status", "TODO"), "unknown")
        if mapped_status == "pass":
            stats["pass_count"] += 1
        elif mapped_status == "fail":
            stats["fail_count"] += 1
        elif mapped_status == "skip":
            stats["skip_count"] += 1
        elif mapped_status == "blocked":
            stats["blocked_count"] += 1

    stats["import_timestamp"] = datetime.now().isoformat()

    return results, stats


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import Xray (Jira) test results to execution_evidence format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--exec",
        required=True,
        help="Xray test execution key, e.g., PROJ-TE-123",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for execution_evidence files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results without writing files",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"import-xray {__version__}",
    )

    args = parser.parse_args()

    try:
        results, stats = import_xray_results(args.exec)

        if args.dry_run:
            print("=== DRY RUN ===")
            print(f"Execution: {args.exec}")
            print(f"Stats: {json.dumps(stats, indent=2)}")
            print(f"Results: {len(results)} tests")
            for r in results[:5]:
                print(f"  - {r['tc_id']}: {r['result']}")
            return 0

        # Write output
        args.output.mkdir(parents=True, exist_ok=True)

        for evidence in results:
            filename = f"{evidence['tc_id']}.json"
            file_path = args.output / filename
            file_path.write_text(
                json.dumps(evidence, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

        # Write summary
        summary_path = args.output / "summary.json"
        summary_path.write_text(
            json.dumps(stats, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        print(f"Imported: {args.output}")
        print(f"  Total: {stats['imported_count']} tests")
        print(f"  Pass: {stats['pass_count']}, Fail: {stats['fail_count']}")
        print(f"  Skip: {stats['skip_count']}, Blocked: {stats['blocked_count']}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())