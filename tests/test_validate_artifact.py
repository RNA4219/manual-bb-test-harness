"""Unit tests for validate-artifact.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

spec_validate_artifact = importlib.util.spec_from_file_location(
    "validate_artifact",
    Path(__file__).parent.parent / "scripts" / "validate-artifact.py",
)
validate_artifact_module = importlib.util.module_from_spec(spec_validate_artifact)
sys.modules["validate_artifact"] = validate_artifact_module
spec_validate_artifact.loader.exec_module(validate_artifact_module)

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
