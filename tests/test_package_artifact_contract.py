"""公開スクリプトと配布 package が同じ artifact 契約を使うことを保証する。"""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from bb_harness.tools import validate_artifact as validator

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "filename",
    sorted(path.name for path in (ROOT / "schemas").glob("*.schema.json")),
)
def test_root_and_package_schema_match(filename: str) -> None:
    root = json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8"))
    package_path = ROOT / "src/bb_harness/schemas" / filename
    assert package_path.exists(), f"packaged schema missing: {filename}"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert root == package

@pytest.mark.parametrize("script,package", [
    ("export-notion", "bb_harness.tools.export_notion"),
    ("export-testrail", "bb_harness.tools.export_testrail"),
    ("export-xray", "bb_harness.tools.export_xray"),
    ("validate-artifact", "bb_harness.tools.validate_artifact"),
    ("evaluate-gate", "bb_harness.gate_engine"),
])
def test_script_uses_native_main(script: str, package: str) -> None:
    spec = importlib.util.spec_from_file_location(f"wrapper_{script}", ROOT / "scripts" / f"{script}.py")
    assert spec is not None and spec.loader is not None
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    assert wrapper.main is importlib.import_module(package).main


@pytest.mark.parametrize("schema_dir", [ROOT / "schemas", ROOT / "src/bb_harness/schemas"])
def test_gate_schema_rejects_legacy_waiver_and_missing_context(schema_dir: Path) -> None:
    schema = json.loads((schema_dir / "gate_decision.schema.json").read_text(encoding="utf-8"))
    validation = Draft202012Validator(schema)
    assert not validation.is_valid({"feature_id": "F-1", "status": "go", "reasons": ["passed"]})
    assert not validation.is_valid({
        "feature_id": "F-1", "build_id": "B-1", "status": "conditional_go", "profile": "standard",
        "reasons": ["approval required"],
        "evidence_summary": {"manual_by_priority": {}, "mandatory_observation_rate": 100},
        "waivers": ["implicitly approved"],
    })


def test_retired_semantics_are_checked_without_jsonschema(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "retired.manual_case_set.json"
    artifact.write_text(json.dumps({"feature_id": "F-1", "manual_cases": [
        {"tc_id": "TC-RET-1", "status": "retired"}
    ]}), encoding="utf-8")
    monkeypatch.setattr(validator, "HAS_JSONSCHEMA", False)
    result = validator.validate_artifact(artifact, "manual_case_set")
    assert not result["valid"]
    assert any("retired_reason" in message for message in result["errors"])
    assert any("replacement_refs" in message for message in result["errors"])


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_validator_rejects_non_finite_numbers(tmp_path: Path, number: float) -> None:
    artifact = tmp_path / "bad.automation_evidence.json"
    artifact.write_text(json.dumps({
        "feature_id": "F-1", "build_id": "B-1", "coverage_scope": "changed_code",
        "coverage_percent": number, "new_issues": {"blocker": 0, "critical": 0},
        "source_refs": [{"id": "CI-1", "kind": "auto_test"}],
    }), encoding="utf-8")
    result = validator.validate_artifact(artifact, "automation_evidence")
    assert not result["valid"]
    assert any("Non-finite" in message for message in result["errors"])


def test_validator_retains_timezone_check(tmp_path: Path) -> None:
    artifact = tmp_path / "bad.execution_evidence.json"
    artifact.write_text(json.dumps({
        "feature_id": "F-1", "build_id": "B-1", "tc_id": "TC-1", "run_id": "RUN-1",
        "result": "pass", "timestamp": "2026-09-12T00:00:00",
    }), encoding="utf-8")
    result = validator.validate_artifact(artifact, "execution_evidence")
    assert not result["valid"]
    assert any("date-time" in message for message in result["errors"])


def test_validator_keeps_gate_v2_artifact_types() -> None:
    assert "automation_evidence" in validator.ARTIFACT_SCHEMA_MAP
    assert "waiver_set" in validator.ARTIFACT_SCHEMA_MAP


def test_order_cancel_retirement_does_not_complete_mandatory_observation(tmp_path: Path) -> None:
    from bb_harness import gate_engine

    artifacts = ROOT / "examples/artifacts"
    output = tmp_path / "gate.json"
    args = ["--output", str(output), "--evidence", str(artifacts / "execution_evidence")]
    for option, kind in [("risk", "risk_register"), ("cases", "manual_case_set"),
                         ("feature", "feature_spec"), ("observations", "observation_set"),
                         ("model", "test_model"), ("automation", "automation_evidence")]:
        args.extend([f"--{option}", str(artifacts / f"order-cancel.{kind}.json")])
    assert gate_engine.main(args) == 0
    gate = json.loads(output.read_text(encoding="utf-8"))
    assert gate["status"] == "no_go"
    assert gate["evidence_summary"]["mandatory_observation_rate"] == pytest.approx(200 / 3)
    assert gate["retired_cases"][0]["id"] == "TC-003"
    assert gate["evidence_summary"]["manual_by_priority"]["P1"]["total"] == 1
    assert not gate.get("waivers")
