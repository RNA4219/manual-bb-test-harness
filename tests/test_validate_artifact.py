"""Unit tests for validate-artifact.py."""

from __future__ import annotations

import json
from pathlib import Path

from bb_harness.tools import validate_artifact as validate_artifact_module

detect_artifact_type = validate_artifact_module.detect_artifact_type
validate_all = validate_artifact_module.validate_all
validate_artifact = validate_artifact_module.validate_artifact


class TestDetectArtifactType:
    """Tests for artifact type detection from filenames."""

    def test_detects_feature_spec_from_generated_example_name(self) -> None:
        assert detect_artifact_type(Path("test_spec.feature_spec.json")) == "feature_spec"

    def test_unknown_filename_returns_empty_string(self) -> None:
        assert detect_artifact_type(Path("test_spec.json")) == ""


class TestValidateArtifact:
    """Tests for artifact validation."""

    def test_rejects_additional_properties_with_jsonschema(self, tmp_path: Path) -> None:
        artifact = tmp_path / "bad.feature_spec.json"
        artifact.write_text(
            json.dumps(
                {
                    "feature_id": "BAD-1",
                    "title": "Bad feature",
                    "acceptance_criteria": ["AC-1"],
                    "source_refs": [{"id": "AC-1", "kind": "ac"}],
                    "unexpected": True,
                }
            ),
            encoding="utf-8",
        )

        result = validate_artifact(artifact, "feature_spec")

        assert result["valid"] is False
        assert any("Additional properties" in error for error in result["errors"])

    def test_examples_artifacts_all_validate(self) -> None:
        results = validate_all(Path("examples/artifacts"))

        assert results
        assert all(result["valid"] for result in results)

    def test_nested_execution_evidence_is_validated(self) -> None:
        """Ensure rglob picks up nested execution_evidence files."""
        results = validate_all(Path("examples/artifacts"))

        # Check that nested execution_evidence files are included
        execution_evidence_files = [r for r in results if r.get("type") == "execution_evidence"]
        assert len(execution_evidence_files) >= 3  # TC-001, TC-002, CHARTER-001
        assert all(r["valid"] for r in execution_evidence_files)

    def test_retired_case_with_replacement_refs_is_valid(self, tmp_path: Path) -> None:
        artifact = tmp_path / "retired.manual_case_set.json"
        artifact.write_text(
            json.dumps(
                {
                    "feature_id": "RET-1",
                    "spec_revision": "spec-rev-1",
                    "manual_cases": [
                        {
                            "tc_id": "TC-RET-001",
                            "revision": "case-rev-1",
                            "content_hash": "sha256:tc-ret-001",
                            "oracle_revision": "oracle-rev-1",
                            "title": "Retired case",
                            "priority": "P1",
                            "primary_view": "black",
                            "steps": ["移管先を確認"],
                            "expected_results": ["自動テスト参照が存在する"],
                            "oracle": {"type": "specified", "refs": ["AC-1"]},
                            "trace_to": ["RISK-1"],
                            "status": "retired",
                            "retired_reason": "自動テストへ移管済み",
                            "replacement_refs": ["hate:AETE-001"],
                            "placement_change_ref": "qeg:PLC-001",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = validate_artifact(artifact, "manual_case_set")

        assert result["valid"] is True

    def test_retired_case_without_replacement_refs_is_invalid(self, tmp_path: Path) -> None:
        artifact = tmp_path / "bad-retired.manual_case_set.json"
        artifact.write_text(
            json.dumps(
                {
                    "feature_id": "RET-1",
                    "spec_revision": "spec-rev-1",
                    "manual_cases": [
                        {
                            "tc_id": "TC-RET-001",
                            "revision": "case-rev-1",
                            "content_hash": "sha256:tc-ret-001",
                            "oracle_revision": "oracle-rev-1",
                            "title": "Retired case",
                            "priority": "P1",
                            "primary_view": "black",
                            "steps": ["移管先を確認"],
                            "expected_results": ["自動テスト参照が存在する"],
                            "oracle": {"type": "specified", "refs": ["AC-1"]},
                            "trace_to": ["RISK-1"],
                            "status": "retired",
                            "retired_reason": "自動テストへ移管済み",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = validate_artifact(artifact, "manual_case_set")

        assert result["valid"] is False
        assert any("replacement_refs" in error for error in result["errors"])
