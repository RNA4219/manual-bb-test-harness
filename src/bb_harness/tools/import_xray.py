"""Import Xray (Jira) test results to execution_evidence format.

Usage:
    python scripts/import-xray.py --execution-key <key> --output <dir>
    python scripts/import-xray.py --project <key> --date-range <start> <end> --output <dir>
    python scripts/import-xray.py --version

Environment:
    JIRA_URL: Base URL (e.g., https://example.atlassian.net)
    JIRA_USER: Username or email
    JIRA_API_KEY: API token

Example:
    export JIRA_URL="https://example.atlassian.net"
    export JIRA_USER="qa_lead@example.com"
    export JIRA_API_KEY="xxx"

    python scripts/import-xray.py --execution-key PROJ-TE-123 --output execution_evidence/
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bb_harness import __version__

# Add scripts/ to path for _shared imports
from bb_harness.tools._shared.import_common import (
    create_import_stats,
    lazy_import_requests,
    print_dry_run_summary,
    print_import_summary,
    write_evidence_files,
)

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


def _identity_value(testrun: dict[str, Any], name: str) -> Any:
    """Read one exported identity field and reject conflicting Xray copies."""
    values = [testrun.get(name)]
    custom_fields = testrun.get("customFields")
    if isinstance(custom_fields, dict):
        values.append(custom_fields.get(name))
    present = [value for value in values if value not in (None, "", [])]
    if len({str(value) for value in present}) > 1:
        raise ValueError(f"ambiguous {name} mapping")
    return present[0] if present else None


def _oracle_refs(value: Any, fallback: str) -> list[str]:
    if value in (None, "", []):
        return [fallback]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value):
        return [item.strip() for item in value]
    raise ValueError("oracle_refs must be a string or an array of non-empty strings")


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


def fetch_test_execution(
    base_url: str, headers: dict[str, str], auth: tuple[str, str], exec_key: str
) -> dict[str, Any]:
    """Fetch Xray test execution details."""
    requests = lazy_import_requests()
    # Xray Cloud API
    url = f"{base_url}/rest/raven/2.0/api/testexec/{exec_key}"
    response = requests.get(url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_jira_issue(
    base_url: str, headers: dict[str, str], auth: tuple[str, str], issue_key: str
) -> dict[str, Any]:
    """Fetch Jira issue details."""
    requests = lazy_import_requests()
    url = f"{base_url}/rest/api/2/issue/{issue_key}"
    response = requests.get(url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()
    return response.json()


def convert_to_execution_evidence(
    testrun: dict[str, Any],
    exec_key: str,
    test_key: str,
    feature_id: str = "IMPORTED",
    *,
    require_original_mapping: bool = False,
) -> dict[str, Any]:
    """Convert Xray testrun to execution_evidence format."""
    status = testrun.get("status", "TODO")
    result_status = XRAY_STATUS_MAP.get(status, "unknown")

    source_case_id = _identity_value(testrun, "source_case_id")
    source_charter_id = _identity_value(testrun, "source_charter_id")
    if source_case_id and source_charter_id:
        raise ValueError("ambiguous original case/charter mapping")
    source_id = source_charter_id or source_case_id
    identity_field = "charter_id" if source_charter_id else "tc_id"
    if source_id is None:
        if require_original_mapping:
            raise ValueError("original case or charter mapping required")
        source_id = test_key
        identity_field = "tc_id"
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("original case or charter mapping must be a non-empty string")
    source_id = source_id.strip()

    source_feature_id = _identity_value(testrun, "source_feature_id")
    if source_feature_id and feature_id != "IMPORTED" and str(source_feature_id) != feature_id:
        raise ValueError("source feature mapping does not match requested feature")
    resolved_feature_id = str(source_feature_id or feature_id)
    case_revision = str(_identity_value(testrun, "case_revision") or f"xray-test-{test_key}")
    stable_fallback = f"xray:{source_id}:{case_revision}".encode()

    evidence: dict[str, Any] = {
        "run_id": f"XRAY-{exec_key}-{test_key}",
        **{identity_field: source_id},
        "feature_id": resolved_feature_id,
        "build_id": f"xray-exec-{exec_key}",
        "case_revision": case_revision,
        "spec_revision": str(_identity_value(testrun, "spec_revision") or f"xray-exec-{exec_key}"),
        "oracle_revision": str(_identity_value(testrun, "oracle_revision") or case_revision),
        "case_content_hash": str(
            _identity_value(testrun, "case_content_hash")
            or "sha256:" + hashlib.sha256(stable_fallback).hexdigest()
        ),
        "oracle_refs": _oracle_refs(_identity_value(testrun, "oracle_refs"), "xray:" + test_key),
        "timestamp": testrun.get("startedOn") or datetime.now(timezone.utc).isoformat(),
        "tester": testrun.get("executedBy", "unknown"),
        "result": result_status,
    }

    # Add timestamps
    started = testrun.get("startedOn", "")
    finished = testrun.get("finishedOn", "")
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
            from bb_harness.evidence_policy import imported_defect_reports

            reports = imported_defect_reports(defects)
            if reports:
                evidence["defect_stub"] = reports[0]
                evidence["defects"] = reports

    # Add evidences/attachments
    attachments = testrun.get("evidences", [])
    if attachments:
        evidence["attachments"] = [a.get("url", "") for a in attachments if isinstance(a, dict)]

    # Add comment
    comment = testrun.get("comment", "")
    if comment:
        evidence["anomaly_notes"] = [comment]

    return evidence


def import_xray_results(
    exec_key: str,
    dry_run: bool = False,
    feature_id: str = "IMPORTED",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Import Xray results and convert to execution_evidence.

    Args:
        exec_key: Xray test execution key
        dry_run: If True, skip API calls and return preview data
    """
    stats = create_import_stats("xray", execution_key=exec_key)

    if dry_run:
        # Return preview data without API calls
        stats["dry_run"] = True
        preview_results = [
            {
                "run_id": f"XRAY-{exec_key}-preview",
                "tc_id": "PROJ-TC-001",
                "feature_id": feature_id,
                "build_id": f"xray-exec-{exec_key}",
                "case_revision": "preview-v1",
                "spec_revision": f"xray-exec-{exec_key}",
                "oracle_revision": "preview-v1",
                "case_content_hash": "sha256:preview-xray-case",
                "oracle_refs": ["PROJ-TC-001"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tester": "preview",
                "result": "pass",
            }
        ]
        return preview_results, stats

    base_url, headers, auth = get_jira_client()

    # Fetch test execution
    exec_data = fetch_test_execution(base_url, headers, auth, exec_key)

    results: list[dict[str, Any]] = []

    tests = exec_data.get("tests", [])
    for testrun in tests:
        test_key = testrun.get("testKey", "")
        if not test_key:
            # Try alternate field
            test_key = testrun.get("test", {}).get("key", "")

        if not test_key:
            continue

        evidence = convert_to_execution_evidence(
            testrun,
            exec_key,
            test_key,
            feature_id,
            require_original_mapping=True,
        )
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
        dest="execution_key",
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
    parser.add_argument(
        "--feature-id",
        default="IMPORTED",
        help="Feature ID attached to imported evidence",
    )

    args = parser.parse_args()

    try:
        if args.feature_id == "IMPORTED":
            print(
                "Warning: --feature-id not specified; evidence uses IMPORTED",
                file=sys.stderr,
            )
        results, stats = import_xray_results(args.execution_key, args.dry_run, args.feature_id)

        if args.dry_run:
            print_dry_run_summary(f"Execution: {args.execution_key}", stats, results)
            return 0

        # Write output
        write_evidence_files(results, args.output)
        print_import_summary(args.output, stats)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
