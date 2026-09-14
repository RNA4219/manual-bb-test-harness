"""Unit tests for export-testrail.py and export-xray.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest
from jsonschema import Draft202012Validator

from bb_harness.tools import export_notion, export_testrail, export_xray
from bb_harness.tools.import_testrail import convert_to_execution_evidence as import_testrail_case
from bb_harness.tools.import_xray import convert_to_execution_evidence as import_xray_case

# ============== TestRail Tests ==============

load_json_tr = export_testrail.load_json
convert_to_testrail = export_testrail.convert_to_testrail
export_testrail_csv = export_testrail.export_testrail_csv
main_testrail = export_testrail.main


class TestLoadCaseSet:
    """Tests for case set loading."""

    def test_valid_json(self, tmp_path: Path) -> None:
        file = tmp_path / "test.manual_case_set.json"
        file.write_text(json.dumps({"feature_id": "TEST", "manual_cases": []}), encoding="utf-8")
        result = load_json_tr(file)
        assert result["feature_id"] == "TEST"

    def test_invalid_json(self, tmp_path: Path) -> None:
        file = tmp_path / "test.json"
        file.write_text("{invalid}", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_json_tr(file)


class TestConvertToTestrail:
    """Tests for TestRail conversion."""

    def test_basic_conversion(self) -> None:
        case_set = {
            "feature_id": "TEST-01",
            "manual_cases": [
                {
                    "title": "Test Case 1",
                    "priority": "P1",
                    "steps": ["Step 1"],
                    "expected_results": ["Result 1"],
                }
            ],
        }
        result = convert_to_testrail(case_set)
        assert len(result["sections"]) == 1
        assert len(result["cases"]) == 1
        assert result["cases"][0]["title"] == "Test Case 1"

    def test_priority_mapping(self) -> None:
        case_set = {
            "feature_id": "TEST",
            "manual_cases": [
                {"priority": "P0"},
                {"priority": "P4"},
            ],
        }
        result = convert_to_testrail(case_set)
        assert result["cases"][0]["priority_id"] == 5  # P0 -> 5
        assert result["cases"][1]["priority_id"] == 1  # P4 -> 1

    def test_estimate_conversion(self) -> None:
        case_set = {"feature_id": "TEST", "manual_cases": [{"estimate_minutes": 15}]}
        result = convert_to_testrail(case_set)
        assert result["cases"][0]["estimate"] == "15m"

    def test_empty_cases(self) -> None:
        case_set = {"feature_id": "TEST", "manual_cases": []}
        result = convert_to_testrail(case_set)
        assert result["cases"] == []

    def test_retired_status_preserved(self) -> None:
        case_set = {
            "feature_id": "TEST",
            "manual_cases": [
                {
                    "title": "Retired Case",
                    "status": "retired",
                    "retired_reason": "自動テストへ移管済み",
                    "replacement_refs": ["hate:AETE-001"],
                    "placement_change_ref": "qeg:PLC-001",
                }
            ],
        }
        result = convert_to_testrail(case_set)
        exported = result["cases"][0]
        assert exported["custom_status"] == "retired"
        assert exported["custom_retired_reason"] == "自動テストへ移管済み"
        assert exported["custom_replacement_refs"] == "hate:AETE-001"
        assert exported["custom_placement_change_ref"] == "qeg:PLC-001"

    def test_evidence_identity_round_trip(self) -> None:
        case_set = {
            "feature_id": "TEST-01",
            "spec_revision": "spec-7",
            "manual_cases": [
                {
                    "tc_id": "TC-101",
                    "title": "Identity contract",
                    "revision": "case-3",
                    "oracle_revision": "oracle-2",
                    "content_hash": "sha256:manual-case-101",
                    "oracle": {"type": "specified", "refs": ["AC-101"]},
                    "trace_to": ["OBS-101"],
                }
            ],
        }

        exported = convert_to_testrail(case_set)["cases"][0]
        exported.update({"id": 501, "case_id": 101, "status_id": 1})
        evidence = import_testrail_case(
            exported,
            {},
            "tester",
            12,
            require_original_mapping=True,
        )

        assert evidence["tc_id"] == "TC-101"
        assert evidence["feature_id"] == "TEST-01"
        assert evidence["case_revision"] == "case-3"
        assert evidence["spec_revision"] == "spec-7"
        assert evidence["oracle_revision"] == "oracle-2"
        assert evidence["case_content_hash"] == "sha256:manual-case-101"
        assert evidence["oracle_refs"] == ["AC-101"]


class TestExportTestrailCsv:
    """Tests for CSV export."""

    def test_csv_structure(self, tmp_path: Path) -> None:
        testrail_data = {
            "sections": [{"name": "TEST-01"}],
            "cases": [
                {
                    "title": "Test",
                    "priority_id": 4,
                    "estimate": "10m",
                    "custom_steps": "Step",
                    "custom_expected": "Result",
                }
            ],
        }
        output = tmp_path / "output.csv"
        export_testrail_csv(testrail_data, output)

        content = output.read_text(encoding="utf-8")
        assert "Section" in content
        assert "TEST-01" in content
        assert "Test" in content

    def test_csv_includes_retired_columns(self, tmp_path: Path) -> None:
        testrail_data = {
            "sections": [{"name": "TEST-01"}],
            "cases": [
                {
                    "title": "Retired",
                    "priority_id": 4,
                    "estimate": "0m",
                    "custom_steps": "",
                    "custom_expected": "",
                    "custom_status": "retired",
                    "custom_retired_reason": "自動テストへ移管済み",
                    "custom_replacement_refs": "hate:AETE-001",
                    "custom_placement_change_ref": "qeg:PLC-001",
                }
            ],
        }
        output = tmp_path / "output.csv"
        export_testrail_csv(testrail_data, output)

        content = output.read_text(encoding="utf-8")
        assert "Status" in content
        assert "retired" in content
        assert "hate:AETE-001" in content


class TestMainTestrail:
    """Tests for main() entry point."""

    def test_version(self) -> None:
        with mock.patch.object(sys, "argv", ["script", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main_testrail()
            assert exc_info.value.code == 0

    def test_csv_export(self, tmp_path: Path) -> None:
        input_file = tmp_path / "test.manual_case_set.json"
        input_file.write_text(
            json.dumps({"feature_id": "TEST", "manual_cases": [{"title": "TC"}]}), encoding="utf-8"
        )
        output_file = tmp_path / "output.csv"

        with mock.patch.object(
            sys,
            "argv",
            [
                "script",
                "--input",
                str(input_file),
                "--format",
                "csv",
                "--output",
                str(output_file),
            ],
        ):
            assert main_testrail() == 0
            assert output_file.exists()

    def test_json_export(self, tmp_path: Path) -> None:
        input_file = tmp_path / "test.manual_case_set.json"
        input_file.write_text(
            json.dumps({"feature_id": "TEST", "manual_cases": []}), encoding="utf-8"
        )
        output_file = tmp_path / "output.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "script",
                "--input",
                str(input_file),
                "--format",
                "json",
                "--output",
                str(output_file),
            ],
        ):
            assert main_testrail() == 0
            assert output_file.exists()


# ============== Xray Tests ==============

convert_to_xray = export_xray.convert_to_xray
main_xray = export_xray.main


class TestConvertToXray:
    """Tests for Xray conversion."""

    def test_basic_conversion(self) -> None:
        case_set = {
            "feature_id": "TEST-01",
            "manual_cases": [
                {"title": "Test", "steps": ["Action"], "expected_results": ["Result"]}
            ],
        }
        result = convert_to_xray(case_set)
        assert len(result["tests"]) == 1
        assert result["tests"][0]["summary"] == "Test"
        assert result["tests"][0]["steps"][0]["action"] == "Action"

    def test_priority_mapping(self) -> None:
        case_set = {"feature_id": "TEST", "manual_cases": [{"priority": "P0"}]}
        result = convert_to_xray(case_set)
        assert result["tests"][0]["priority"] == "Highest"

    def test_labels_include_feature_id(self) -> None:
        case_set = {"feature_id": "FEATURE-X", "manual_cases": [{"trace_to": ["OBS-1"]}]}
        result = convert_to_xray(case_set)
        assert "FEATURE-X" in result["tests"][0]["labels"]
        assert "OBS-1" in result["tests"][0]["labels"]

    def test_exploratory_charters(self) -> None:
        case_set = {
            "feature_id": "TEST",
            "manual_cases": [],
            "exploratory_charters": [{"title": "Explore", "scope": "network", "questions": ["Q1"]}],
        }
        result = convert_to_xray(case_set)
        assert len(result["tests"]) == 1
        assert result["tests"][0]["testType"] == "Exploratory"
        assert "exploratory" in result["tests"][0]["labels"]

    def test_exploratory_charter_identity_round_trip(self) -> None:
        case_set = {
            "feature_id": "TEST-CHARTER",
            "spec_revision": "spec-charter-1",
            "manual_cases": [],
            "exploratory_charters": [
                {
                    "id": "CHARTER-101",
                    "revision": "charter-2",
                    "content_hash": "sha256:charter-101",
                    "oracle_revision": "oracle-charter-3",
                    "title": "Explore recovery",
                    "scope": "network recovery",
                    "questions": ["Can the user retry safely?"],
                    "trace_to": ["OBS-RECOVERY-1"],
                }
            ],
        }

        payload = convert_to_xray(case_set)
        schema = json.loads(
            (Path(__file__).resolve().parents[1] / "schemas" / "xray-export.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(payload)
        exported = payload["tests"][0]
        exported.update({"status": "PASS", "testKey": "QA-CHARTER-101"})
        evidence = import_xray_case(
            exported,
            "QA-EXEC-CHARTER",
            "QA-CHARTER-101",
            require_original_mapping=True,
        )

        assert evidence["charter_id"] == "CHARTER-101"
        assert "tc_id" not in evidence
        assert evidence["case_revision"] == "charter-2"
        assert evidence["spec_revision"] == "spec-charter-1"
        assert evidence["oracle_revision"] == "oracle-charter-3"
        assert evidence["case_content_hash"] == "sha256:charter-101"
        assert evidence["oracle_refs"] == ["OBS-RECOVERY-1"]

    def test_preconditions_extracted(self) -> None:
        case_set = {"feature_id": "TEST", "manual_cases": [{"preconditions": ["State=A"]}]}
        result = convert_to_xray(case_set)
        assert len(result["preconditions"]) == 1
        assert result["preconditions"][0]["summary"] == "State=A"

    def test_retired_status_preserved(self) -> None:
        case_set = {
            "feature_id": "TEST",
            "manual_cases": [
                {
                    "title": "Retired",
                    "status": "retired",
                    "replacement_refs": ["hate:AETE-001"],
                    "placement_change_ref": "qeg:PLC-001",
                }
            ],
        }
        result = convert_to_xray(case_set)
        exported = result["tests"][0]
        assert exported["status"] == "retired"
        assert "status:retired" in exported["labels"]
        assert exported["customFields"]["replacement_refs"] == ["hate:AETE-001"]

    def test_evidence_identity_round_trip(self) -> None:
        case_set = {
            "feature_id": "TEST-02",
            "spec_revision": "spec-8",
            "manual_cases": [
                {
                    "tc_id": "TC-202",
                    "title": "Identity contract",
                    "revision": "case-4",
                    "oracle_revision": "oracle-5",
                    "content_hash": "sha256:manual-case-202",
                    "oracle": {"type": "specified", "refs": ["AC-202"]},
                    "trace_to": ["OBS-202"],
                }
            ],
        }

        exported = convert_to_xray(case_set)["tests"][0]
        exported.update({"status": "PASS", "testKey": "QA-202"})
        evidence = import_xray_case(
            exported,
            "QA-EXEC-9",
            "QA-202",
            require_original_mapping=True,
        )

        assert evidence["tc_id"] == "TC-202"
        assert evidence["feature_id"] == "TEST-02"
        assert evidence["case_revision"] == "case-4"
        assert evidence["spec_revision"] == "spec-8"
        assert evidence["oracle_revision"] == "oracle-5"
        assert evidence["case_content_hash"] == "sha256:manual-case-202"
        assert evidence["oracle_refs"] == ["AC-202"]


class TestMainXray:
    """Tests for Xray main() entry point."""

    def test_version(self) -> None:
        with mock.patch.object(sys, "argv", ["script", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main_xray()
            assert exc_info.value.code == 0

    def test_json_export(self, tmp_path: Path) -> None:
        input_file = tmp_path / "test.manual_case_set.json"
        input_file.write_text(
            json.dumps({"feature_id": "TEST", "manual_cases": [{"title": "TC"}]}), encoding="utf-8"
        )
        output_file = tmp_path / "output.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "script",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
            ],
        ):
            assert main_xray() == 0
            assert output_file.exists()
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert "tests" in data


def test_external_identity_fallback_hash_ignores_result_status() -> None:
    tr_base = {"id": 501, "case_id": 101, "source_case_id": "TC-101", "status_id": 1}
    tr_pass = import_testrail_case(tr_base, {}, "tester", 12)
    tr_fail = import_testrail_case({**tr_base, "status_id": 5}, {}, "tester", 12)
    assert tr_pass["case_content_hash"] == tr_fail["case_content_hash"]

    xr_base = {"source_case_id": "TC-202", "status": "PASS"}
    xr_pass = import_xray_case(xr_base, "QA-EXEC-9", "QA-202")
    xr_fail = import_xray_case({**xr_base, "status": "FAIL"}, "QA-EXEC-9", "QA-202")
    assert xr_pass["case_content_hash"] == xr_fail["case_content_hash"]


def test_testrail_custom_fields_restore_original_identity() -> None:
    evidence = import_testrail_case(
        {
            "id": 777,
            "case_id": 777,
            "status_id": 1,
            "custom_source_case_id": "TC-777",
            "custom_source_feature_id": "FEATURE-777",
        },
        {},
        "tester",
        77,
        require_original_mapping=True,
    )
    assert evidence["tc_id"] == "TC-777"
    assert evidence["feature_id"] == "FEATURE-777"


@pytest.mark.parametrize(
    ("converter", "schema_name", "collection"),
    [
        (convert_to_testrail, "testrail-export.schema.json", "cases"),
        (convert_to_xray, "xray-export.schema.json", "tests"),
    ],
)
def test_exported_manual_case_satisfies_identity_schema(
    converter: object, schema_name: str, collection: str
) -> None:
    case_set = {
        "feature_id": "FEATURE-IDENTITY",
        "spec_revision": "spec-9",
        "manual_cases": [
            {
                "tc_id": "TC-909",
                "title": "Identity schema",
                "revision": "case-9",
                "oracle_revision": "oracle-9",
                "content_hash": "sha256:case-909",
                "oracle": {"type": "specified", "refs": ["AC-909"]},
            }
        ],
    }
    payload = converter(case_set)  # type: ignore[operator]
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / schema_name).read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(payload)

    without_revision = json.loads(json.dumps(payload))
    del without_revision[collection][0]["case_revision"]
    assert any(
        error.validator == "required"
        for error in Draft202012Validator(schema).iter_errors(without_revision)
    )


# ============== Export Notion Tests ==============

main_notion = export_notion.main
create_notion_page = export_notion.create_notion_page


class TestExportNotionDryRun:
    """Tests for export-notion.py dry-run mode."""

    def test_dry_run_without_api_token(self) -> None:
        """Dry-run should succeed without NOTION_API_TOKEN."""
        with mock.patch.object(
            sys,
            "argv",
            [
                "script",
                "--dry-run",
                "--score",
                "90",
                "--status",
                "pass",
                "--db",
                "dummy_db_id",
            ],
        ):
            with mock.patch.dict("os.environ", {"NOTION_API_TOKEN": ""}, clear=True):
                assert main_notion() == 0

    def test_dry_run_with_score_and_status(self) -> None:
        """Dry-run should print payload correctly."""
        with mock.patch.object(
            sys,
            "argv",
            [
                "script",
                "--dry-run",
                "--score",
                "85",
                "--status",
                "conditional_pass",
                "--feature",
                "TEST-01",
                "--db",
                "test-db",
                "--title",
                "Test Run",
            ],
        ):
            with mock.patch.dict("os.environ", {"NOTION_API_TOKEN": ""}, clear=True):
                assert main_notion() == 0

    def test_version(self) -> None:
        with mock.patch.object(sys, "argv", ["script", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main_notion()
            assert exc_info.value.code == 0

    def test_manual_case_status_in_payload(self) -> None:
        fake_response = mock.Mock()
        fake_response.json.return_value = {"id": "page-1", "url": "https://notion.test/page-1"}
        fake_response.raise_for_status.return_value = None
        fake_requests = mock.Mock()
        fake_requests.post.return_value = fake_response
        report = {
            "feature_id": "TEST",
            "score": 90,
            "pass_status": "pass",
            "manual_cases": [
                {
                    "tc_id": "TC-RET-001",
                    "status": "retired",
                    "replacement_refs": ["hate:AETE-001"],
                    "placement_change_ref": "qeg:PLC-001",
                }
            ],
        }

        with mock.patch.dict(sys.modules, {"requests": fake_requests}):
            create_notion_page("db", "Title", report, "token")

        payload = fake_requests.post.call_args.kwargs["json"]
        payload_text = json.dumps(payload, ensure_ascii=False)
        assert "Manual Case Status" in payload_text
        assert "TC-RET-001: retired" in payload_text
        assert "hate:AETE-001" in payload_text
