"""Unit tests for import status conversion (PLAN-IMPORT-01).

Covers TestRail and Xray status/priority maps and convert_to_execution_evidence.
Also validates import output against execution_evidence.schema.json (PLAN-IMPORT-04).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Load import-testrail.py dynamically
_spec_tr = importlib.util.spec_from_file_location(
    "import_testrail", Path(__file__).parent.parent / "scripts" / "import-testrail.py"
)
import_testrail = importlib.util.module_from_spec(_spec_tr)
sys.modules["import_testrail"] = import_testrail
_spec_tr.loader.exec_module(import_testrail)

# Load import-xray.py dynamically
_spec_xr = importlib.util.spec_from_file_location(
    "import_xray", Path(__file__).parent.parent / "scripts" / "import-xray.py"
)
import_xray = importlib.util.module_from_spec(_spec_xr)
sys.modules["import_xray"] = import_xray
_spec_xr.loader.exec_module(import_xray)

# ========== TestRail status maps ==========


class TestTestRailStatusMap:
    """TestRail STATUS_MAP covers all documented status IDs."""

    def test_passed(self) -> None:
        assert import_testrail.STATUS_MAP[1] == "pass"

    def test_blocked(self) -> None:
        assert import_testrail.STATUS_MAP[2] == "blocked"

    def test_untested(self) -> None:
        assert import_testrail.STATUS_MAP[3] == "skip"

    def test_failed(self) -> None:
        assert import_testrail.STATUS_MAP[4] == "fail"

    def test_retest(self) -> None:
        assert import_testrail.STATUS_MAP[5] == "skip"

    def test_unknown_defaults_to_unknown(self) -> None:
        assert import_testrail.STATUS_MAP.get(99, "unknown") == "unknown"


class TestTestRailPriorityMap:
    """TestRail PRIORITY_MAP maps priority IDs to severity strings."""

    def test_low(self) -> None:
        assert import_testrail.PRIORITY_MAP[1] == "low"

    def test_medium(self) -> None:
        assert import_testrail.PRIORITY_MAP[2] == "medium"

    def test_high(self) -> None:
        assert import_testrail.PRIORITY_MAP[3] == "high"

    def test_critical(self) -> None:
        assert import_testrail.PRIORITY_MAP[4] == "critical"

    def test_blocker(self) -> None:
        assert import_testrail.PRIORITY_MAP[5] == "blocker"


class TestTestRailConversion:
    """TestRail convert_to_execution_evidence produces valid evidence."""

    def _make_test(self, status_id: int = 1, case_id: int = 42) -> dict:
        return {"id": 100, "case_id": case_id, "status_id": status_id}

    def test_pass_result(self) -> None:
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(status_id=1), {}, "tester_a", 999
        )
        assert evidence["result"] == "pass"
        assert evidence["run_id"] == "TR-RUN-999-100"
        assert evidence["tc_id"] == "TC-042"
        assert evidence["tester"] == "tester_a"

    def test_fail_result_with_defect(self) -> None:
        result = {"defects": ["BUG-123"]}
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(status_id=4), result, "tester_b", 999
        )
        assert evidence["result"] == "fail"
        assert evidence["defect_stub"]["title"] == "Defect BUG-123"
        assert evidence["defect_stub"]["severity"] == "high"

    def test_blocked_result(self) -> None:
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(status_id=2), {}, "tester_a", 999
        )
        assert evidence["result"] == "blocked"

    def test_skip_result(self) -> None:
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(status_id=3), {}, "tester_a", 999
        )
        assert evidence["result"] == "skip"

    def test_custom_prefix(self) -> None:
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(case_id=7), {}, "tester_a", 999, tc_prefix="TR"
        )
        assert evidence["tc_id"] == "TR-007"

    def test_elapsed_time(self) -> None:
        result = {"elapsed": "2m 30s"}
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(), result, "tester_a", 999
        )
        assert evidence["time_spent_minutes"] == pytest.approx(2.5)

    def test_elapsed_seconds_only(self) -> None:
        result = {"elapsed": "45s"}
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(), result, "tester_a", 999
        )
        assert evidence["time_spent_minutes"] == pytest.approx(0.75)

    def test_custom_fields_device_env(self) -> None:
        result = {"custom_fields": {"device": "Pixel 8", "env": "staging"}}
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(), result, "tester_a", 999
        )
        assert evidence["device"] == "Pixel 8"
        assert evidence["env"] == "staging"

    def test_comment_becomes_anomaly_notes(self) -> None:
        result = {"comment": "Flaky on retry"}
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(), result, "tester_a", 999
        )
        assert evidence["anomaly_notes"] == ["Flaky on retry"]

    def test_feature_id_is_imported_placeholder(self) -> None:
        evidence = import_testrail.convert_to_execution_evidence(
            self._make_test(), {}, "tester_a", 999
        )
        assert evidence["feature_id"] == "IMPORTED"


# ========== Xray status maps ==========


class TestXrayStatusMap:
    """Xray XRAY_STATUS_MAP covers all documented statuses."""

    def test_pass(self) -> None:
        assert import_xray.XRAY_STATUS_MAP["PASS"] == "pass"

    def test_fail(self) -> None:
        assert import_xray.XRAY_STATUS_MAP["FAIL"] == "fail"

    def test_aborted(self) -> None:
        assert import_xray.XRAY_STATUS_MAP["ABORTED"] == "blocked"

    def test_todo(self) -> None:
        assert import_xray.XRAY_STATUS_MAP["TODO"] == "skip"

    def test_executing(self) -> None:
        assert import_xray.XRAY_STATUS_MAP["EXECUTING"] == "unknown"

    def test_pending(self) -> None:
        assert import_xray.XRAY_STATUS_MAP["PENDING"] == "skip"

    def test_unknown_defaults_to_unknown(self) -> None:
        assert import_xray.XRAY_STATUS_MAP.get("CUSTOM", "unknown") == "unknown"


class TestXrayPriorityMap:
    """Xray JIRA_PRIORITY_MAP maps Jira priorities to severity strings."""

    def test_highest(self) -> None:
        assert import_xray.JIRA_PRIORITY_MAP["Highest"] == "blocker"

    def test_high(self) -> None:
        assert import_xray.JIRA_PRIORITY_MAP["High"] == "critical"

    def test_medium(self) -> None:
        assert import_xray.JIRA_PRIORITY_MAP["Medium"] == "high"

    def test_low(self) -> None:
        assert import_xray.JIRA_PRIORITY_MAP["Low"] == "medium"

    def test_lowest(self) -> None:
        assert import_xray.JIRA_PRIORITY_MAP["Lowest"] == "low"


class TestXrayConversion:
    """Xray convert_to_execution_evidence produces valid evidence."""

    def _make_testrun(self, status: str = "PASS") -> dict:
        return {
            "status": status,
            "executedBy": "qa_lead",
        }

    def test_pass_result(self) -> None:
        evidence = import_xray.convert_to_execution_evidence(
            self._make_testrun("PASS"), "PROJ-TE-1", "PROJ-TC-10"
        )
        assert evidence["result"] == "pass"
        assert evidence["run_id"] == "XRAY-PROJ-TE-1-PROJ-TC-10"
        assert evidence["tc_id"] == "PROJ-TC-10"
        assert evidence["tester"] == "qa_lead"

    def test_fail_result_with_defect(self) -> None:
        testrun = self._make_testrun("FAIL")
        testrun["defects"] = ["PROJ-BUG-5"]
        evidence = import_xray.convert_to_execution_evidence(testrun, "PROJ-TE-1", "PROJ-TC-10")
        assert evidence["result"] == "fail"
        assert evidence["defect_stub"]["title"] == "Defect PROJ-BUG-5"

    def test_blocked_result(self) -> None:
        evidence = import_xray.convert_to_execution_evidence(
            self._make_testrun("ABORTED"), "TE-1", "TC-1"
        )
        assert evidence["result"] == "blocked"

    def test_skip_result(self) -> None:
        evidence = import_xray.convert_to_execution_evidence(
            self._make_testrun("TODO"), "TE-1", "TC-1"
        )
        assert evidence["result"] == "skip"

    def test_unknown_result(self) -> None:
        evidence = import_xray.convert_to_execution_evidence(
            self._make_testrun("EXECUTING"), "TE-1", "TC-1"
        )
        assert evidence["result"] == "unknown"

    def test_attachments(self) -> None:
        testrun = self._make_testrun("PASS")
        testrun["evidences"] = [{"url": "https://evidence/screenshot.png"}]
        evidence = import_xray.convert_to_execution_evidence(testrun, "TE-1", "TC-1")
        assert evidence["attachments"] == ["https://evidence/screenshot.png"]

    def test_comment_becomes_anomaly_notes(self) -> None:
        testrun = self._make_testrun("FAIL")
        testrun["comment"] = "Unexpected timeout"
        evidence = import_xray.convert_to_execution_evidence(testrun, "TE-1", "TC-1")
        assert evidence["anomaly_notes"] == ["Unexpected timeout"]

    def test_feature_id_is_imported_placeholder(self) -> None:
        evidence = import_xray.convert_to_execution_evidence(
            self._make_testrun("PASS"), "TE-1", "TC-1"
        )
        assert evidence["feature_id"] == "IMPORTED"

    def test_missing_executed_by_defaults_to_unknown(self) -> None:
        testrun = {"status": "PASS"}
        evidence = import_xray.convert_to_execution_evidence(testrun, "TE-1", "TC-1")
        assert evidence["tester"] == "unknown"


# ========== Schema validation (PLAN-IMPORT-04) ==========


def _load_evidence_schema() -> dict:
    """Load execution_evidence schema with $ref resolution."""
    schema_path = Path(__file__).parent.parent / "schemas" / "execution_evidence.schema.json"
    shared_path = Path(__file__).parent.parent / "schemas" / "shared_defs.schema.json"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if shared_path.exists():
        shared = json.loads(shared_path.read_text(encoding="utf-8"))
        schema.setdefault("$defs", {}).update(shared.get("$defs", {}))

    return schema


def _validate_schema(data: dict, schema: dict) -> list[str]:
    """Validate data against schema, return list of error messages."""
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed")

    errors = []
    validator = jsonschema.Draft202012Validator(schema)
    for error in validator.iter_errors(data):
        errors.append(f"{'/'.join(str(p) for p in error.path)}: {error.message}")
    return errors


class TestTestRailEvidenceSchema:
    """TestRail import output validates against execution_evidence schema."""

    def test_basic_pass(self) -> None:
        schema = _load_evidence_schema()
        evidence = import_testrail.convert_to_execution_evidence(
            {"id": 1, "case_id": 42, "status_id": 1}, {}, "tester_a", 999
        )
        errors = _validate_schema(evidence, schema)
        assert errors == []

    def test_fail_with_defect(self) -> None:
        schema = _load_evidence_schema()
        result = {"defects": ["BUG-1"]}
        evidence = import_testrail.convert_to_execution_evidence(
            {"id": 1, "case_id": 42, "status_id": 4}, result, "tester_a", 999
        )
        errors = _validate_schema(evidence, schema)
        assert errors == []

    def test_with_elapsed_and_custom_fields(self) -> None:
        schema = _load_evidence_schema()
        result = {
            "elapsed": "5m 30s",
            "custom_fields": {"device": "Pixel 8", "env": "staging"},
        }
        evidence = import_testrail.convert_to_execution_evidence(
            {"id": 1, "case_id": 42, "status_id": 1}, result, "tester_a", 999
        )
        errors = _validate_schema(evidence, schema)
        assert errors == []


class TestXrayEvidenceSchema:
    """Xray import output validates against execution_evidence schema."""

    def test_basic_pass(self) -> None:
        schema = _load_evidence_schema()
        evidence = import_xray.convert_to_execution_evidence(
            {"status": "PASS", "executedBy": "qa_lead"}, "TE-1", "TC-10"
        )
        errors = _validate_schema(evidence, schema)
        assert errors == []

    def test_fail_with_defect(self) -> None:
        schema = _load_evidence_schema()
        testrun = {"status": "FAIL", "executedBy": "qa_lead", "defects": ["BUG-5"]}
        evidence = import_xray.convert_to_execution_evidence(testrun, "TE-1", "TC-10")
        errors = _validate_schema(evidence, schema)
        assert errors == []

    def test_with_timestamp(self) -> None:
        schema = _load_evidence_schema()
        testrun = {
            "status": "PASS",
            "executedBy": "qa_lead",
            "startedOn": "2026-05-30T10:00:00Z",
        }
        evidence = import_xray.convert_to_execution_evidence(testrun, "TE-1", "TC-10")
        errors = _validate_schema(evidence, schema)
        assert errors == []

    def test_dry_run_preview_validates(self) -> None:
        """Dry-run preview data must also pass schema validation."""
        schema = _load_evidence_schema()
        results, _ = import_xray.import_xray_results("TEST-1", dry_run=True)
        for evidence in results:
            errors = _validate_schema(evidence, schema)
            assert errors == []

    def test_testrail_dry_run_preview_validates(self) -> None:
        """TestRail dry-run preview data must also pass schema validation."""
        schema = _load_evidence_schema()
        results, _ = import_testrail.import_testrail_results(12, 1234, dry_run=True)
        for evidence in results:
            errors = _validate_schema(evidence, schema)
            assert errors == []
