"""Import TestRail test results to execution_evidence format.

Usage:
    python scripts/import-testrail.py --project <id> --run <id> --output <dir>
    python scripts/import-testrail.py --project <id> --date-range <start> <end> --output <dir>
    python scripts/import-testrail.py --version

Environment:
    TESTRAIL_URL: Base URL (e.g., https://example.testrail.io)
    TESTRAIL_USER: Username or email
    TESTRAIL_API_KEY: API token

Example:
    export TESTRAIL_URL="https://example.testrail.io"
    export TESTRAIL_USER="qa_lead"
    export TESTRAIL_API_KEY="xxx"

    python scripts/import-testrail.py --project 12 --run 1234 --output execution_evidence/
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

# TestRail status ID mapping
STATUS_MAP = {
    1: "pass",  # Passed
    2: "blocked",  # Blocked
    3: "skip",  # Untested
    4: "skip",  # Retest
    5: "fail",  # Failed
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


def _collection_items(payload: Any, key: str) -> list[dict[str, Any]]:
    """現行のページ応答と旧形式の配列を共通のレコード列にする。"""
    items = payload.get(key) if isinstance(payload, dict) else payload
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError(f"Invalid TestRail {key} response: expected an array of objects")
    return items


def fetch_tests(
    base_url: str, headers: dict[str, str], auth: tuple[str, str], run_id: int
) -> list[dict[str, Any]]:
    """同じ run の全ページを取得し、途中で失敗した場合は結果を返さない。"""
    requests = lazy_import_requests()
    endpoint = f"/api/v2/get_tests/{run_id}"
    api_url = f"{base_url.rstrip('/')}/index.php?"
    url = api_url + endpoint
    visited: set[str] = set()
    tests: list[dict[str, Any]] = []
    while True:
        if url in visited:
            raise ValueError(f"Repeated TestRail pagination link for run {run_id}")
        visited.add(url)
        response = requests.get(url, headers=headers, auth=auth, timeout=30)
        response.raise_for_status()
        payload = response.json()
        tests.extend(_collection_items(payload, "tests"))
        if isinstance(payload, list):
            return tests

        links = payload.get("_links")
        if not isinstance(links, dict) or "next" not in links:
            raise ValueError("Invalid TestRail tests response: missing pagination links")
        next_link = links["next"]
        if next_link is None:
            return tests
        # API が返す相対リンクだけを使い、別の run や接続先を取得しない。
        if not isinstance(next_link, str) or not (
            next_link == endpoint or next_link.startswith(endpoint + "&")
        ):
            raise ValueError(f"Invalid TestRail pagination link for run {run_id}")
        url = api_url + next_link


def fetch_test_results(
    base_url: str, headers: dict[str, str], auth: tuple[str, str], test_id: int
) -> dict[str, Any]:
    """新しい順に並ぶ結果から最新1件を取得する。正常な空配列は許容する。"""
    requests = lazy_import_requests()
    url = f"{base_url}/index.php?/api/v2/get_results/{test_id}"
    response = requests.get(url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()
    results = _collection_items(response.json(), "results")
    return results[0] if results else {}


def fetch_user(
    base_url: str, headers: dict[str, str], auth: tuple[str, str], user_id: int
) -> dict[str, Any]:
    """Fetch user info."""
    requests = lazy_import_requests()
    url = f"{base_url}/index.php?/api/v2/get_user/{user_id}"
    response = requests.get(url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()
    return response.json()


def map_tc_id(case_id: int, case_prefix: str = "TC") -> str:
    """Map TestRail case ID to TC-XXX format."""
    return f"{case_prefix}-{case_id:03d}"


def original_case_id(test: dict[str, Any], *, allow_synthesized: bool = False) -> str:
    """Return the single harness case ID carried by the external mapping."""
    single = _identity_value(test, "source_case_id")
    candidates = test.get("source_case_ids", [])
    if candidates and (
        not isinstance(candidates, list)
        or len(candidates) != 1
        or not isinstance(candidates[0], str)
        or not candidates[0].strip()
    ):
        raise ValueError("ambiguous original case mapping")
    if candidates:
        if single and single != candidates[0]:
            raise ValueError("ambiguous original case mapping")
        single = candidates[0]
    if not isinstance(single, str) or not single.strip():
        if allow_synthesized:
            return map_tc_id(test.get("case_id", 0))
        raise ValueError("original case mapping required")
    return single.strip()


def _identity_value(test: dict[str, Any], name: str) -> Any:
    """Read one exported identity field from TestRail's supported custom-field shapes."""
    values = [test.get(name), test.get(f"custom_{name}")]
    custom_fields = test.get("custom_fields")
    if isinstance(custom_fields, dict):
        values.extend([custom_fields.get(name), custom_fields.get(f"custom_{name}")])
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


def convert_to_execution_evidence(
    test: dict[str, Any],
    result: dict[str, Any],
    tester_name: str,
    run_id: int,
    tc_prefix: str = "TC",
    feature_id: str = "IMPORTED",
    *,
    require_original_mapping: bool = False,
) -> dict[str, Any]:
    """Convert TestRail test/result to execution_evidence format."""
    status_id = test.get("status_id", 3)
    result_status = STATUS_MAP.get(status_id, "unknown")

    case_id = (
        original_case_id(test)
        if require_original_mapping
        else test.get("source_case_id") or map_tc_id(test.get("case_id", 0), tc_prefix)
    )
    source_feature_id = _identity_value(test, "source_feature_id")
    if source_feature_id and feature_id != "IMPORTED" and str(source_feature_id) != feature_id:
        raise ValueError("source feature mapping does not match requested feature")
    resolved_feature_id = str(source_feature_id or feature_id)
    case_revision = str(_identity_value(test, "case_revision") or f"testrail-test-{test['id']}")
    stable_fallback = f"testrail:{case_id}:{case_revision}".encode()

    evidence: dict[str, Any] = {
        "run_id": f"TR-RUN-{run_id}-{test['id']}",
        "tc_id": case_id,
        "feature_id": resolved_feature_id,
        "build_id": f"testrail-run-{run_id}",
        "case_revision": case_revision,
        "spec_revision": str(_identity_value(test, "spec_revision") or f"testrail-run-{run_id}"),
        "oracle_revision": str(_identity_value(test, "oracle_revision") or case_revision),
        "case_content_hash": str(
            _identity_value(test, "case_content_hash")
            or "sha256:" + hashlib.sha256(stable_fallback).hexdigest()
        ),
        "oracle_refs": _oracle_refs(
            _identity_value(test, "oracle_refs"), "testrail:" + str(test["id"])
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
            from bb_harness.evidence_policy import imported_defect_reports

            reports = imported_defect_reports(defects)
            if reports:
                evidence["defect_stub"] = reports[0]
                evidence["defects"] = reports

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


def import_testrail_results(
    project_id: int,
    run_id: int,
    tc_prefix: str = "TC",
    dry_run: bool = False,
    feature_id: str = "IMPORTED",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Import TestRail results and convert to execution_evidence.

    Args:
        project_id: TestRail project ID
        run_id: TestRail run ID
        tc_prefix: Prefix for test case IDs
        dry_run: If True, skip API calls and return preview data
    """
    stats = create_import_stats("testrail", project_id=project_id, run_id=run_id)

    if dry_run:
        # Return preview data without API calls
        stats["dry_run"] = True
        preview_results = [
            {
                "run_id": f"TR-RUN-{run_id}-preview",
                "tc_id": f"{tc_prefix}-001",
                "feature_id": feature_id,
                "build_id": f"testrail-run-{run_id}",
                "case_revision": "preview-v1",
                "spec_revision": f"testrail-run-{run_id}",
                "oracle_revision": "preview-v1",
                "case_content_hash": "sha256:preview-testrail-case",
                "oracle_refs": [f"{tc_prefix}-001"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tester": "preview",
                "result": "pass",
            }
        ]
        return preview_results, stats

    base_url, headers, auth = get_testrail_client()

    # Fetch tests
    tests = fetch_tests(base_url, headers, auth, run_id)

    results: list[dict[str, Any]] = []

    # Cache users
    user_cache: dict[int, str] = {}

    for test in tests:
        _case_id = test.get("case_id", 0)
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
        try:
            test_result = fetch_test_results(base_url, headers, auth, test["id"])
        except Exception as exc:
            raise ValueError(f"Cannot fetch results for TestRail test {test['id']}") from exc

        evidence = convert_to_execution_evidence(
            test,
            test_result,
            tester_name,
            run_id,
            tc_prefix,
            feature_id,
            require_original_mapping=True,
        )
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
        "--feature-id",
        default="IMPORTED",
        help="Feature ID attached to imported evidence",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"import-testrail {__version__}",
    )

    args = parser.parse_args()

    try:
        if args.feature_id == "IMPORTED":
            print(
                "Warning: --feature-id not specified; evidence uses IMPORTED",
                file=sys.stderr,
            )
        results, stats = import_testrail_results(
            args.project, args.run, args.tc_prefix, args.dry_run, args.feature_id
        )

        if args.dry_run:
            print_dry_run_summary(f"Project: {args.project}, Run: {args.run}", stats, results)
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
