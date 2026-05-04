"""Import TestRail test results to execution_evidence format.

Usage:
    python scripts/import-testrail.py --project <id> --run <id> --output <dir>
    python scripts/import-testrail.py --project <id> --date-range <start> <end> --output <dir>
    python scripts/import-testrail.py --version

Environment:
    TESTRAIL_URL: Base URL (e.g., https://company.testrail.io)
    TESTRAIL_USER: Username or email
    TESTRAIL_API_KEY: API token

Example:
    export TESTRAIL_URL="https://company.testrail.io"
    export TESTRAIL_USER="qa_lead"
    export TESTRAIL_API_KEY="xxx"

    python scripts/import-testrail.py --project 12 --run 1234 --output execution_evidence/
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

# TestRail status ID mapping
STATUS_MAP = {
    1: "pass",       # Passed
    2: "blocked",    # Blocked
    3: "skip",       # Untested
    4: "fail",       # Failed
    5: "skip",       # Retest
}

# Priority ID to severity mapping
PRIORITY_MAP = {
    1: "low",
    2: "medium",
    3: "high",
    4: "critical",
    5: "blocker",
}


def get_testrail_client() -> tuple[str, dict[str, str], tuple[str, str] | None]:
    """Get TestRail API credentials from environment."""
    base_url = os.environ.get("TESTRAIL_URL", "")
    if not base_url:
        raise ValueError("TESTRAIL_URL environment variable required")

    user = os.environ.get("TESTRAIL_USER", "")
    api_key = os.environ.get("TESTRAIL_API_KEY", "")

    if not user or not api_key:
        raise ValueError("TESTRAIL_USER and TESTRAIL_API_KEY environment variables required")

    headers = {"Content-Type": "application/json"}
    auth = (user, api_key)

    return base_url.rstrip("/"), headers, auth


def fetch_tests(base_url: str, headers: dict[str, str], auth: tuple[str, str], run_id: int) -> list[dict[str, Any]]:
    """Fetch tests from TestRail run."""
    try:
        import requests
    except ImportError:
        raise ValueError("requests library required: pip install requests")

    url = f"{base_url}/index.php?/api/v2/get_tests/{run_id}"
    response = requests.get(url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_test_results(base_url: str, headers: dict[str, str], auth: tuple[str, str], test_id: int) -> dict[str, Any]:
    """Fetch results for a single test."""
    try:
        import requests
    except ImportError:
        raise ValueError("requests library required: pip install requests")

    url = f"{base_url}/index.php?/api/v2/get_results/{test_id}"
    response = requests.get(url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()
    results = response.json()
    return results[0] if results else {}


def fetch_user(base_url: str, headers: dict[str, str], auth: tuple[str, str], user_id: int) -> dict[str, Any]:
    """Fetch user info."""
    try:
        import requests
    except ImportError:
        raise ValueError("requests library required: pip install requests")

    url = f"{base_url}/index.php?/api/v2/get_user/{user_id}"
    response = requests.get(url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()
    return response.json()


def map_tc_id(case_id: int, case_prefix: str = "TC") -> str:
    """Map TestRail case ID to TC-XXX format."""
    return f"{case_prefix}-{case_id:03d}"


def convert_to_execution_evidence(
    test: dict[str, Any],
    result: dict[str, Any],
    tester_name: str,
    run_id: int,
    tc_prefix: str = "TC",
) -> dict[str, Any]:
    """Convert TestRail test/result to execution_evidence format."""
    status_id = test.get("status_id", 3)
    result_status = STATUS_MAP.get(status_id, "unknown")

    evidence: dict[str, Any] = {
        "run_id": f"TR-RUN-{run_id}-{test['id']}",
        "tc_id": map_tc_id(test.get("case_id", 0), tc_prefix),
        "feature_id": "IMPORTED",  # User should set this
        "tester": tester_name,
        "result": result_status,
    }

    # Add elapsed time if available
    elapsed = result.get("elapsed", "")
    if elapsed:
        # Parse elapsed format like "1m 30s" or "30s"
        minutes = 0
        seconds = 0
        if "m" in elapsed:
            parts = elapsed.split("m")
            minutes = int(parts[0].strip())
            if "s" in parts[1]:
                seconds = int(parts[1].replace("s", "").strip())
        elif "s" in elapsed:
            seconds = int(elapsed.replace("s", "").strip())
        evidence["time_spent_minutes"] = minutes + seconds / 60

    # Add defect stub if failed
    if result_status == "fail":
        defects = result.get("defects", [])
        if defects:
            # Get first defect
            defect_id = defects[0] if isinstance(defects, list) else defects
            evidence["defect_stub"] = {
                "title": f"Defect {defect_id}",
                "severity": "high",  # Default, could fetch from Jira
            }

    # Add custom fields
    custom_fields = result.get("custom_fields", {})
    if custom_fields:
        if "device" in custom_fields:
            evidence["device"] = custom_fields["device"]
        if "env" in custom_fields:
            evidence["env"] = custom_fields["env"]
        if "network_profile" in custom_fields:
            evidence["network_profile"] = custom_fields["network_profile"]

    # Add comments as notes
    comment = result.get("comment", "")
    if comment:
        evidence["anomaly_notes"] = [comment]

    return evidence


def import_testrail_results(project_id: int, run_id: int, tc_prefix: str = "TC") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Import TestRail results and convert to execution_evidence."""
    base_url, headers, auth = get_testrail_client()

    # Fetch tests
    tests = fetch_tests(base_url, headers, auth, run_id)

    results: list[dict[str, Any]] = []
    stats = {
        "source": "testrail",
        "project_id": project_id,
        "run_id": run_id,
        "imported_count": 0,
        "pass_count": 0,
        "fail_count": 0,
        "skip_count": 0,
        "blocked_count": 0,
    }

    # Cache users
    user_cache: dict[int, str] = {}

    for test in tests:
        case_id = test.get("case_id", 0)
        status_id = test.get("status_id", 3)

        # Get assigned user
        assigned_to_id = test.get("assigned_to_id", 0)
        if assigned_to_id and assigned_to_id not in user_cache:
            try:
                user = fetch_user(base_url, headers, auth, assigned_to_id)
                user_cache[assigned_to_id] = user.get("name", f"User_{assigned_to_id}")
            except Exception:
                user_cache[assigned_to_id] = f"User_{assigned_to_id}"

        tester_name = user_cache.get(assigned_to_id, "unknown")

        # Get latest result for this test
        test_result: dict[str, Any] = {}
        try:
            test_result = fetch_test_results(base_url, headers, auth, test["id"])
        except Exception:
            pass  # Use empty result

        evidence = convert_to_execution_evidence(test, test_result, tester_name, run_id, tc_prefix)
        results.append(evidence)

        # Update stats
        stats["imported_count"] += 1
        mapped_status = STATUS_MAP.get(status_id, "unknown")
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
        description="Import TestRail test results to execution_evidence format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project",
        type=int,
        required=True,
        help="TestRail project ID",
    )
    parser.add_argument(
        "--run",
        type=int,
        required=True,
        help="TestRail test run ID",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for execution_evidence files",
    )
    parser.add_argument(
        "--tc-prefix",
        default="TC",
        help="Prefix for test case IDs (default: TC)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results without writing files",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"import-testrail {__version__}",
    )

    args = parser.parse_args()

    try:
        results, stats = import_testrail_results(args.project, args.run, args.tc_prefix)

        if args.dry_run:
            print("=== DRY RUN ===")
            print(f"Project: {args.project}, Run: {args.run}")
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