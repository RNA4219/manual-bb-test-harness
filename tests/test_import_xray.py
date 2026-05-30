"""Comprehensive tests for scripts/import-xray.py.

Tests all major branches and functions:
- get_jira_client (credential loading)
- XRAY_STATUS_MAP, JIRA_PRIORITY_MAP (constants)
- convert_to_execution_evidence (conversion logic)
- import_xray_results (dry-run and error handling)
- main (CLI execution)

# TRACE: scripts/import-xray.py (role: operations)
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def load_import_xray_module() -> object:
    """Load import-xray.py module dynamically."""
    spec = importlib.util.spec_from_file_location(
        "import_xray", REPO_ROOT / "scripts" / "import-xray.py"
    )
    if spec is None or spec.loader is None:
        pytest.skip("Cannot load import-xray.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["import_xray"] = module
    spec.loader.exec_module(module)
    return module


class TestXrayStatusMap:
    """Tests for XRAY_STATUS_MAP constant.

    # TRACE: scripts/import-xray.py:42-50 (role: constants)
    """

    def test_status_map_defined(self) -> None:
        """Status map is defined."""
        module = load_import_xray_module()
        status_map = module.XRAY_STATUS_MAP

        assert status_map["PASS"] == "pass"
        assert status_map["FAIL"] == "fail"
        assert status_map["ABORTED"] == "blocked"
        assert status_map["TODO"] == "skip"
        assert status_map["PENDING"] == "skip"


class TestJiraPriorityMap:
    """Tests for JIRA_PRIORITY_MAP constant.

    # TRACE: scripts/import-xray.py:52-59 (role: constants)
    """

    def test_priority_map_defined(self) -> None:
        """Priority map is defined."""
        module = load_import_xray_module()
        priority_map = module.JIRA_PRIORITY_MAP

        assert priority_map["Highest"] == "blocker"
        assert priority_map["High"] == "critical"
        assert priority_map["Low"] == "medium"
        assert priority_map["Lowest"] == "low"


class TestGetJiraClient:
    """Tests for get_jira_client function.

    # TRACE: scripts/import-xray.py:62-77 (role: credential_loading)
    """

    def test_missing_url(self) -> None:
        """Missing JIRA_URL raises ValueError."""
        module = load_import_xray_module()

        os.environ.pop("JIRA_URL", None)

        with pytest.raises(ValueError, match="JIRA_URL"):
            module.get_jira_client()

    def test_missing_credentials(self) -> None:
        """Missing user/api_key raises ValueError."""
        module = load_import_xray_module()

        os.environ["JIRA_URL"] = "https://test.atlassian.net"
        os.environ.pop("JIRA_USER", None)
        os.environ.pop("JIRA_API_KEY", None)

        with pytest.raises(ValueError, match="JIRA_USER"):
            module.get_jira_client()

    def test_valid_credentials(self) -> None:
        """Valid credentials return client info."""
        module = load_import_xray_module()

        os.environ["JIRA_URL"] = "https://test.atlassian.net"
        os.environ["JIRA_USER"] = "test_user"
        os.environ["JIRA_API_KEY"] = "test_key"

        base_url, headers, auth = module.get_jira_client()

        assert base_url == "https://test.atlassian.net"
        assert auth == ("test_user", "test_key")


class TestConvertToExecutionEvidence:
    """Tests for convert_to_execution_evidence function.

    # TRACE: scripts/import-xray.py:103-155 (role: conversion)
    """

    def test_convert_passed_testrun(self) -> None:
        """Convert passed testrun."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "PASS",
            "executedBy": "tester1",
            "startedOn": "2024-01-01T10:00:00Z",
            "finishedOn": "2024-01-01T10:05:00Z",
            "comment": "Passed test",
        }
        exec_key = "PROJ-TE-123"

        evidence = module.convert_to_execution_evidence(testrun, exec_key, "PROJ-TC-001")

        assert evidence["result"] == "pass"
        assert evidence["tc_id"] == "PROJ-TC-001"
        assert evidence["run_id"] == "XRAY-PROJ-TE-123-PROJ-TC-001"
        assert evidence["tester"] == "tester1"
        assert evidence["time_spent_minutes"] == 5.0
        assert evidence["anomaly_notes"] == ["Passed test"]

    def test_convert_failed_testrun_with_defect(self) -> None:
        """Convert failed testrun with defect."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "FAIL",
            "executedBy": "tester1",
            "defects": ["BUG-001"],
        }
        exec_key = "PROJ-TE-123"

        evidence = module.convert_to_execution_evidence(testrun, exec_key, "PROJ-TC-001")

        assert evidence["result"] == "fail"
        assert evidence["defect_stub"]["title"] == "Defect BUG-001"

    def test_convert_aborted_testrun(self) -> None:
        """Convert aborted testrun."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "ABORTED",
            "executedBy": "tester1",
        }
        exec_key = "PROJ-TE-123"

        evidence = module.convert_to_execution_evidence(testrun, exec_key, "PROJ-TC-001")

        assert evidence["result"] == "blocked"

    def test_convert_with_attachments(self) -> None:
        """Convert with attachments."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "PASS",
            "executedBy": "tester1",
            "evidences": [{"url": "https://example.com/file.png"}],
        }
        exec_key = "PROJ-TE-123"

        evidence = module.convert_to_execution_evidence(testrun, exec_key, "PROJ-TC-001")

        assert evidence["attachments"] == ["https://example.com/file.png"]

    def test_convert_unknown_status(self) -> None:
        """Unknown status defaults to 'unknown'."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "UNKNOWN_STATUS",
            "executedBy": "tester1",
        }
        exec_key = "PROJ-TE-123"

        evidence = module.convert_to_execution_evidence(testrun, exec_key, "PROJ-TC-001")

        assert evidence["result"] == "unknown"


class TestImportXrayResults:
    """Tests for import_xray_results function.

    # TRACE: scripts/import-xray.py:158-218 (role: import_logic)
    """

    def test_dry_run_preview(self, tmp_path: Path) -> None:
        """Dry-run returns preview data."""
        module = load_import_xray_module()

        results, stats = module.import_xray_results(exec_key="PROJ-TE-123", dry_run=True)

        assert stats["dry_run"] is True
        assert len(results) >= 1
        assert results[0]["result"] == "pass"


class TestImportXrayMain:
    """Tests for main function (CLI execution).

    # TRACE: scripts/import-xray.py:221-266 (role: cli_entry)
    """

    def test_main_version(self, tmp_path: Path) -> None:
        """Version flag works."""
        import subprocess

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "import-xray.py"), "--version"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "import-xray" in result.stdout

    def test_main_dry_run(self, tmp_path: Path) -> None:
        """Dry-run mode works."""
        import subprocess

        output_dir = tmp_path / "output"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "import-xray.py"),
                "--exec",
                "PROJ-TE-123",
                "--output",
                str(output_dir),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        # Output contains "dry run" or "DRY RUN"
        assert "dry" in result.stdout.lower()

    def test_main_missing_exec(self, tmp_path: Path) -> None:
        """Missing --exec returns error."""
        import subprocess

        output_dir = tmp_path / "output"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "import-xray.py"),
                "--output",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode != 0

    def test_main_missing_output(self, tmp_path: Path) -> None:
        """Missing --output returns error."""
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "import-xray.py"),
                "--exec",
                "PROJ-TE-123",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode != 0


class TestCliWrapper:
    """Tests for CLI wrapper (bb-harness import xray).

    # TRACE: src/bb_harness/commands/import_results.py (role: wrapper)
    """

    def test_cli_import_xray_dry_run(self, tmp_path: Path) -> None:
        """CLI import xray dry-run."""
        import subprocess

        output_dir = tmp_path / "output"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "import",
                "xray",
                "--dry-run",
                "--exec",
                "PROJ-TE-123",
                "--output",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0


class TestFetchFunctions:
    """Tests for fetch functions (mocked).

    # TRACE: scripts/import-xray.py:80-100 (role: api_calls)
    """

    def test_fetch_test_execution_exists(self) -> None:
        """Fetch test execution function exists."""
        module = load_import_xray_module()

        assert hasattr(module, "fetch_test_execution")

    def test_fetch_jira_issue_exists(self) -> None:
        """Fetch Jira issue function exists."""
        module = load_import_xray_module()

        assert hasattr(module, "fetch_jira_issue")


class TestTimestampHandling:
    """Tests for timestamp handling.

    # TRACE: scripts/import-xray.py:121-133 (role: parsing)
    """

    def test_timestamp_present(self) -> None:
        """Timestamp is extracted."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "PASS",
            "executedBy": "tester1",
            "startedOn": "2024-01-01T10:00:00Z",
        }
        evidence = module.convert_to_execution_evidence(testrun, "PROJ-TE-123", "PROJ-TC-001")

        assert evidence["timestamp"] == "2024-01-01T10:00:00Z"

    def test_duration_calculation(self) -> None:
        """Duration is calculated."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "PASS",
            "executedBy": "tester1",
            "startedOn": "2024-01-01T10:00:00Z",
            "finishedOn": "2024-01-01T10:05:00Z",
        }
        evidence = module.convert_to_execution_evidence(testrun, "PROJ-TE-123", "PROJ-TC-001")

        assert evidence["time_spent_minutes"] == 5.0

    def test_no_timestamp(self) -> None:
        """No timestamp when missing."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "PASS",
            "executedBy": "tester1",
        }
        evidence = module.convert_to_execution_evidence(testrun, "PROJ-TE-123", "PROJ-TC-001")

        assert "timestamp" not in evidence


class TestAttachmentsHandling:
    """Tests for attachments handling.

    # TRACE: scripts/import-xray.py:145-148 (role: attachments)
    """

    def test_attachments_empty(self) -> None:
        """Empty attachments."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "PASS",
            "executedBy": "tester1",
            "evidences": [],
        }
        evidence = module.convert_to_execution_evidence(testrun, "PROJ-TE-123", "PROJ-TC-001")

        assert "attachments" not in evidence

    def test_attachments_invalid_format(self) -> None:
        """Attachments with invalid format - non-dict items produce empty URL."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "PASS",
            "executedBy": "tester1",
            "evidences": ["invalid"],  # String, not dict
        }
        evidence = module.convert_to_execution_evidence(testrun, "PROJ-TE-123", "PROJ-TC-001")

        # When item is not dict, a.get("url", "") returns empty string
        # resulting in attachments list with empty string
        # This tests that the function doesn't crash on invalid format
        assert isinstance(evidence.get("attachments", []), list)


class TestTestKeyExtraction:
    """Tests for test key extraction.

    # TRACE: scripts/import-xray.py:192-199 (role: key_extraction)
    """

    def test_test_key_from_testrun(self) -> None:
        """Test key from testrun."""
        module = load_import_xray_module()

        testrun = {
            "testKey": "PROJ-TC-001",
            "status": "PASS",
        }
        evidence = module.convert_to_execution_evidence(testrun, "PROJ-TE-123", "PROJ-TC-001")

        assert evidence["tc_id"] == "PROJ-TC-001"

    def test_test_key_from_nested_test(self) -> None:
        """Test key from nested test field."""
        module = load_import_xray_module()

        testrun = {
            "test": {"key": "PROJ-TC-002"},
            "status": "PASS",
        }
        evidence = module.convert_to_execution_evidence(testrun, "PROJ-TE-123", "PROJ-TC-002")

        assert evidence["tc_id"] == "PROJ-TC-002"


class TestFetchFunctionsMocked:
    """Tests for fetch functions with mocked requests.

    # TRACE: scripts/import-xray.py:80-100 (role: api_calls)
    """

    def test_fetch_test_execution_exists(self) -> None:
        """Fetch test execution function exists."""
        module = load_import_xray_module()

        assert hasattr(module, "fetch_test_execution")
        assert callable(module.fetch_test_execution)

    def test_fetch_jira_issue_exists(self) -> None:
        """Fetch Jira issue function exists."""
        module = load_import_xray_module()

        assert hasattr(module, "fetch_jira_issue")
        assert callable(module.fetch_jira_issue)


class TestImportXrayResultsMocked:
    """Tests for import_xray_results with mocked API.

    # TRACE: scripts/import-xray.py:158-218 (role: import_logic)
    """

    def test_import_with_mocked_functions(self, tmp_path: Path) -> None:
        """Import with mocked internal function calls."""
        from unittest import mock

        module = load_import_xray_module()

        mock_client = (
            "https://test.atlassian.net",
            {"Content-Type": "application/json"},
            ("user", "key"),
        )

        mock_exec_data = {
            "tests": [
                {"testKey": "PROJ-TC-001", "status": "PASS", "executedBy": "tester1"},
                {"testKey": "PROJ-TC-002", "status": "FAIL", "executedBy": "tester2", "defects": ["BUG-1"]},
            ]
        }

        with mock.patch.object(module, "get_jira_client", return_value=mock_client):
            with mock.patch.object(module, "fetch_test_execution", return_value=mock_exec_data):
                results, stats = module.import_xray_results(
                    exec_key="PROJ-TE-123", dry_run=False
                )

                assert len(results) == 2
                assert stats["imported_count"] == 2
                assert stats["pass_count"] == 1
                assert stats["fail_count"] == 1


class TestImportXrayResultsErrorPaths:
    """Tests for error handling paths in import_xray_results.

    # TRACE: scripts/import-xray.py:188-214 (role: error_handling)
    """

    def test_import_with_empty_tests(self) -> None:
        """Import with empty tests list."""
        from unittest import mock

        module = load_import_xray_module()

        mock_client = (
            "https://test.atlassian.net",
            {"Content-Type": "application/json"},
            ("user", "key"),
        )

        mock_exec_data = {"tests": []}

        with mock.patch.object(module, "get_jira_client", return_value=mock_client):
            with mock.patch.object(module, "fetch_test_execution", return_value=mock_exec_data):
                results, stats = module.import_xray_results(
                    exec_key="PROJ-TE-123", dry_run=False
                )

                assert len(results) == 0
                assert stats["imported_count"] == 0

    def test_import_with_missing_test_key(self) -> None:
        """Import with tests missing testKey."""
        from unittest import mock

        module = load_import_xray_module()

        mock_client = (
            "https://test.atlassian.net",
            {"Content-Type": "application/json"},
            ("user", "key"),
        )

        mock_exec_data = {
            "tests": [
                {"status": "PASS", "executedBy": "tester1"},  # No testKey
            ]
        }

        with mock.patch.object(module, "get_jira_client", return_value=mock_client):
            with mock.patch.object(module, "fetch_test_execution", return_value=mock_exec_data):
                results, stats = module.import_xray_results(
                    exec_key="PROJ-TE-123", dry_run=False
                )

                # Should skip test without testKey
                assert len(results) == 0

    def test_import_with_skip_status(self) -> None:
        """Import with TODO/PENDING status increments skip_count."""
        from unittest import mock

        module = load_import_xray_module()

        mock_client = (
            "https://test.atlassian.net",
            {"Content-Type": "application/json"},
            ("user", "key"),
        )

        mock_exec_data = {
            "tests": [
                {"testKey": "PROJ-TC-001", "status": "TODO", "executedBy": "tester1"},
            ]
        }

        with mock.patch.object(module, "get_jira_client", return_value=mock_client):
            with mock.patch.object(module, "fetch_test_execution", return_value=mock_exec_data):
                results, stats = module.import_xray_results(
                    exec_key="PROJ-TE-123", dry_run=False
                )

                assert stats["skip_count"] == 1

    def test_import_with_blocked_status(self) -> None:
        """Import with ABORTED status increments blocked_count."""
        from unittest import mock

        module = load_import_xray_module()

        mock_client = (
            "https://test.atlassian.net",
            {"Content-Type": "application/json"},
            ("user", "key"),
        )

        mock_exec_data = {
            "tests": [
                {"testKey": "PROJ-TC-001", "status": "ABORTED", "executedBy": "tester1"},
            ]
        }

        with mock.patch.object(module, "get_jira_client", return_value=mock_client):
            with mock.patch.object(module, "fetch_test_execution", return_value=mock_exec_data):
                results, stats = module.import_xray_results(
                    exec_key="PROJ-TE-123", dry_run=False
                )

                assert stats["blocked_count"] == 1


class TestConvertToExecutionEvidenceEdgeCases:
    """Tests for edge cases in convert_to_execution_evidence.

    # TRACE: scripts/import-xray.py:103-155 (role: conversion_edge_cases)
    """

    def test_duration_calculation_with_valid_timestamps(self) -> None:
        """Duration calculation with valid ISO timestamps."""
        module = load_import_xray_module()

        testrun = {
            "status": "PASS",
            "executedBy": "tester",
            "startedOn": "2026-05-30T10:00:00Z",
            "finishedOn": "2026-05-30T10:05:00Z",
        }
        evidence = module.convert_to_execution_evidence(testrun, "TE-1", "TC-1")

        assert evidence["time_spent_minutes"] == 5.0

    def test_duration_calculation_exception_invalid_format(self) -> None:
        """Duration calculation exception with invalid timestamp format."""
        module = load_import_xray_module()

        testrun = {
            "status": "PASS",
            "executedBy": "tester",
            "startedOn": "invalid-date",
            "finishedOn": "2026-05-30T10:05:00Z",
        }
        evidence = module.convert_to_execution_evidence(testrun, "TE-1", "TC-1")

        # Exception caught, no time_spent_minutes
        assert "time_spent_minutes" not in evidence

    def test_duration_calculation_only_started(self) -> None:
        """Duration calculation with only started timestamp."""
        module = load_import_xray_module()

        testrun = {
            "status": "PASS",
            "executedBy": "tester",
            "startedOn": "2026-05-30T10:00:00Z",
        }
        evidence = module.convert_to_execution_evidence(testrun, "TE-1", "TC-1")

        assert evidence["timestamp"] == "2026-05-30T10:00:00Z"
        assert "time_spent_minutes" not in evidence

    def test_defects_as_string(self) -> None:
        """Defects as string instead of list."""
        module = load_import_xray_module()

        testrun = {
            "status": "FAIL",
            "executedBy": "tester",
            "defects": "BUG-001",
        }
        evidence = module.convert_to_execution_evidence(testrun, "TE-1", "TC-1")

        assert evidence["defect_stub"]["title"] == "Defect BUG-001"

    def test_attachments_empty_list(self) -> None:
        """Attachments empty list."""
        module = load_import_xray_module()

        testrun = {
            "status": "PASS",
            "executedBy": "tester",
            "evidences": [],
        }
        evidence = module.convert_to_execution_evidence(testrun, "TE-1", "TC-1")

        assert "attachments" not in evidence

    def test_attachments_non_dict_items(self) -> None:
        """Attachments with non-dict items skipped."""
        module = load_import_xray_module()

        testrun = {
            "status": "PASS",
            "executedBy": "tester",
            "evidences": ["invalid", {"url": "https://valid.url"}],
        }
        evidence = module.convert_to_execution_evidence(testrun, "TE-1", "TC-1")

        assert evidence["attachments"] == ["https://valid.url"]


class TestImportXrayResultsAllStatuses:
    """Tests for all status types in import_xray_results.

    # TRACE: scripts/import-xray.py:205-214 (role: status_counting)
    """

    def test_import_with_all_status_types(self) -> None:
        """Import tests with all status types."""
        from unittest import mock

        module = load_import_xray_module()

        mock_client = (
            "https://test.atlassian.net",
            {"Content-Type": "application/json"},
            ("user", "key"),
        )

        mock_exec_data = {
            "tests": [
                {"testKey": "TC-001", "status": "PASS", "executedBy": "tester"},
                {"testKey": "TC-002", "status": "FAIL", "executedBy": "tester"},
                {"testKey": "TC-003", "status": "TODO", "executedBy": "tester"},
                {"testKey": "TC-004", "status": "ABORTED", "executedBy": "tester"},
                {"testKey": "TC-005", "status": "PENDING", "executedBy": "tester"},
                {"testKey": "TC-006", "status": "EXECUTING", "executedBy": "tester"},
            ]
        }

        with mock.patch.object(module, "get_jira_client", return_value=mock_client):
            with mock.patch.object(module, "fetch_test_execution", return_value=mock_exec_data):
                results, stats = module.import_xray_results(
                    exec_key="PROJ-TE-123", dry_run=False
                )

                assert stats["pass_count"] == 1
                assert stats["fail_count"] == 1
                assert stats["skip_count"] == 2  # TODO + PENDING
                assert stats["blocked_count"] == 1

    def test_import_with_nested_test_key(self) -> None:
        """Import with nested test.key field."""
        from unittest import mock

        module = load_import_xray_module()

        mock_client = (
            "https://test.atlassian.net",
            {"Content-Type": "application/json"},
            ("user", "key"),
        )

        mock_exec_data = {
            "tests": [
                {"test": {"key": "PROJ-TC-001"}, "status": "PASS", "executedBy": "tester1"},
            ]
        }

        with mock.patch.object(module, "get_jira_client", return_value=mock_client):
            with mock.patch.object(module, "fetch_test_execution", return_value=mock_exec_data):
                results, stats = module.import_xray_results(
                    exec_key="PROJ-TE-123", dry_run=False
                )

                assert len(results) == 1
                assert results[0]["tc_id"] == "PROJ-TC-001"


class TestImportXrayMainErrorPaths:
    """Tests for main function error handling.

    # TRACE: scripts/import-xray.py:259-266 (role: main_error)
    """

    def test_main_exception_handling(self, tmp_path: Path) -> None:
        """Main catches exceptions and returns 1."""
        from unittest import mock

        module = load_import_xray_module()

        output_dir = tmp_path / "output"

        with mock.patch.object(
            sys,
            "argv",
            [
                "import-xray",
                "--exec", "PROJ-TE-123",
                "--output", str(output_dir),
            ],
        ):
            with mock.patch.object(
                module,
                "import_xray_results",
                side_effect=Exception("Test error"),
            ):
                result = module.main()
                assert result == 1
