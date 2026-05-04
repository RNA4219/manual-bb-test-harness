"""Unit tests for export-testrail.py and export-xray.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Load modules dynamically
spec_testrail = importlib.util.spec_from_file_location(
    "export_testrail",
    Path(__file__).parent.parent / "scripts" / "export-testrail.py"
)
export_testrail = importlib.util.module_from_spec(spec_testrail)
sys.modules["export_testrail"] = export_testrail
spec_testrail.loader.exec_module(export_testrail)

spec_xray = importlib.util.spec_from_file_location(
    "export_xray",
    Path(__file__).parent.parent / "scripts" / "export-xray.py"
)
export_xray = importlib.util.module_from_spec(spec_xray)
sys.modules["export_xray"] = export_xray
spec_xray.loader.exec_module(export_xray)


# ============== TestRail Tests ==============

load_case_set_tr = export_testrail.load_case_set
convert_to_testrail = export_testrail.convert_to_testrail
export_testrail_csv = export_testrail.export_testrail_csv
main_testrail = export_testrail.main


class TestLoadCaseSet:
    """Tests for case set loading."""

    def test_valid_json(self, tmp_path: Path) -> None:
        file = tmp_path / "test.manual_case_set.json"
        file.write_text(json.dumps({"feature_id": "TEST", "manual_cases": []}), encoding="utf-8")
        result = load_case_set_tr(file)
        assert result["feature_id"] == "TEST"

    def test_invalid_json(self, tmp_path: Path) -> None:
        file = tmp_path / "test.json"
        file.write_text("{invalid}", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_case_set_tr(file)


class TestConvertToTestrail:
    """Tests for TestRail conversion."""

    def test_basic_conversion(self) -> None:
        case_set = {
            "feature_id": "TEST-01",
            "manual_cases": [
                {"title": "Test Case 1", "priority": "P1", "steps": ["Step 1"], "expected_results": ["Result 1"]}
            ]
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
            ]
        }
        result = convert_to_testrail(case_set)
        assert result["cases"][0]["priority_id"] == 5  # P0 -> 5
        assert result["cases"][1]["priority_id"] == 1  # P4 -> 1

    def test_estimate_conversion(self) -> None:
        case_set = {
            "feature_id": "TEST",
            "manual_cases": [{"estimate_minutes": 15}]
        }
        result = convert_to_testrail(case_set)
        assert result["cases"][0]["estimate"] == "15m"

    def test_empty_cases(self) -> None:
        case_set = {"feature_id": "TEST", "manual_cases": []}
        result = convert_to_testrail(case_set)
        assert result["cases"] == []


class TestExportTestrailCsv:
    """Tests for CSV export."""

    def test_csv_structure(self, tmp_path: Path) -> None:
        testrail_data = {
            "sections": [{"name": "TEST-01"}],
            "cases": [{"title": "Test", "priority_id": 4, "estimate": "10m", "custom_steps": "Step", "custom_expected": "Result"}]
        }
        output = tmp_path / "output.csv"
        export_testrail_csv(testrail_data, output)

        content = output.read_text(encoding="utf-8")
        assert "Section" in content
        assert "TEST-01" in content
        assert "Test" in content


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
            json.dumps({"feature_id": "TEST", "manual_cases": [{"title": "TC"}]}),
            encoding="utf-8"
        )
        output_file = tmp_path / "output.csv"

        with mock.patch.object(sys, "argv", [
            "script",
            "--input", str(input_file),
            "--format", "csv",
            "--output", str(output_file),
        ]):
            assert main_testrail() == 0
            assert output_file.exists()

    def test_json_export(self, tmp_path: Path) -> None:
        input_file = tmp_path / "test.manual_case_set.json"
        input_file.write_text(
            json.dumps({"feature_id": "TEST", "manual_cases": []}),
            encoding="utf-8"
        )
        output_file = tmp_path / "output.json"

        with mock.patch.object(sys, "argv", [
            "script",
            "--input", str(input_file),
            "--format", "json",
            "--output", str(output_file),
        ]):
            assert main_testrail() == 0
            assert output_file.exists()


# ============== Xray Tests ==============

load_case_set_xr = export_xray.load_case_set
convert_to_xray = export_xray.convert_to_xray
main_xray = export_xray.main


class TestConvertToXray:
    """Tests for Xray conversion."""

    def test_basic_conversion(self) -> None:
        case_set = {
            "feature_id": "TEST-01",
            "manual_cases": [
                {"title": "Test", "steps": ["Action"], "expected_results": ["Result"]}
            ]
        }
        result = convert_to_xray(case_set)
        assert len(result["tests"]) == 1
        assert result["tests"][0]["summary"] == "Test"
        assert result["tests"][0]["steps"][0]["action"] == "Action"

    def test_priority_mapping(self) -> None:
        case_set = {
            "feature_id": "TEST",
            "manual_cases": [{"priority": "P0"}]
        }
        result = convert_to_xray(case_set)
        assert result["tests"][0]["priority"] == "Highest"

    def test_labels_include_feature_id(self) -> None:
        case_set = {
            "feature_id": "FEATURE-X",
            "manual_cases": [{"trace_to": ["OBS-1"]}]
        }
        result = convert_to_xray(case_set)
        assert "FEATURE-X" in result["tests"][0]["labels"]
        assert "OBS-1" in result["tests"][0]["labels"]

    def test_exploratory_charters(self) -> None:
        case_set = {
            "feature_id": "TEST",
            "manual_cases": [],
            "exploratory_charters": [
                {"title": "Explore", "scope": "network", "questions": ["Q1"]}
            ]
        }
        result = convert_to_xray(case_set)
        assert len(result["tests"]) == 1
        assert result["tests"][0]["testType"] == "Exploratory"
        assert "exploratory" in result["tests"][0]["labels"]

    def test_preconditions_extracted(self) -> None:
        case_set = {
            "feature_id": "TEST",
            "manual_cases": [{"preconditions": ["State=A"]}]
        }
        result = convert_to_xray(case_set)
        assert len(result["preconditions"]) == 1
        assert result["preconditions"][0]["summary"] == "State=A"


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
            json.dumps({"feature_id": "TEST", "manual_cases": [{"title": "TC"}]}),
            encoding="utf-8"
        )
        output_file = tmp_path / "output.json"

        with mock.patch.object(sys, "argv", [
            "script",
            "--input", str(input_file),
            "--output", str(output_file),
        ]):
            assert main_xray() == 0
            assert output_file.exists()
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert "tests" in data