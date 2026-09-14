"""ID一致だけで別版の実行結果を合格にできないことを確認する。"""

import copy
import json
from pathlib import Path

import pytest

from bb_harness.artifact_migration import migrate_artifact
from bb_harness.cli import main
from bb_harness.coverage_engine import build_coverage_report
from bb_harness.evidence_revisions import (
    bind_case_set,
    case_index,
    case_revision,
    verify_case_set,
    verify_execution_revision,
)
from bb_harness.gate_engine import main as gate_main
from bb_harness.schema_validation import SchemaValidationError
from bb_harness.techniques.common import ModelError, digest
from tests.test_coverage_engine import case, cases, domain, evidence, plan


def bound_inputs():
    model = domain()
    bound = bind_case_set(cases(case({"x": 10})), model)
    item = evidence(
        "TC-1",
        "pass",
        build_id="B",
        case_revision=bound["manual_cases"][0]["case_revision"],
        model_hash=bound["evidence_binding"]["model_hash"],
    )
    return model, bound, item


def test_bound_evidence_and_legacy_status():
    model, bound, item = bound_inputs()
    assert verify_case_set(bound, model) == "case_revision"
    verify_execution_revision(item, bound)
    report = build_coverage_report(model, plan(model), bound, [item], build_id="B")
    assert report["evidence_binding_mode"] == "case_revision"
    assert report["execution"]["passed"] == 1
    legacy = cases(case())
    assert verify_case_set(legacy) == "legacy_unverified"
    verify_execution_revision({}, legacy)
    assert (
        build_coverage_report(model, plan(model), legacy)["evidence_binding_mode"]
        == "legacy_unverified"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_results", ["changed"]),
        ("steps", ["changed"]),
        ("preconditions", ["new state"]),
        ("test_data", {"x": 99}),
        ("oracle", {"type": "human", "refs": []}),
        ("source_ref", {"type": "acceptance", "refs": ["AC-2"]}),
    ],
)
def test_execution_definition_edits_invalidate_old_evidence(field, value):
    model, bound, item = bound_inputs()
    bound["manual_cases"][0][field] = value
    with pytest.raises(ModelError, match="changed after binding"):
        verify_case_set(bound, model)
    with pytest.raises(ModelError, match="case revision"):
        verify_execution_revision(item, bound)


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "renamed"),
        ("priority", "P2"),
        ("estimate_minutes", 30),
        ("trace_to", ["OBS-OTHER"]),
        ("techniques", ["boundary_value"]),
    ],
)
def test_non_execution_metadata_does_not_change_revision(field, value):
    model, bound, item = bound_inputs()
    before = case_revision(bound["manual_cases"][0])
    bound["manual_cases"][0][field] = value
    assert case_revision(bound["manual_cases"][0]) == before
    assert verify_case_set(bound, model) == "case_revision"
    verify_execution_revision(item, bound)


@pytest.mark.parametrize(
    "mutate", ["missing_case", "stale_case", "missing_model", "stale_model", "unknown_case"]
)
def test_coverage_rejects_wrong_revision(mutate):
    model, bound, item = bound_inputs()
    if mutate == "unknown_case":
        item["tc_id"] = "TC-999"
    else:
        key = "case_revision" if mutate.endswith("case") else "model_hash"
        if mutate.startswith("missing"):
            item.pop(key)
        else:
            item[key] = "0" * 64
    expected_error = SchemaValidationError if mutate == "missing_case" else ModelError
    with pytest.raises(expected_error):
        build_coverage_report(model, plan(model), bound, [item], build_id="B")


def test_model_change_requires_rebinding_and_new_execution():
    model, bound, item = bound_inputs()
    model["parameters"][0]["step"] = 0.1
    with pytest.raises(ModelError, match="model hash"):
        verify_case_set(bound, model)
    rebound = bind_case_set(bound, model)
    with pytest.raises(ModelError, match="model revision"):
        verify_execution_revision(item, rebound)


def test_binding_checks_feature_and_duplicate_ids():
    model, bound, _ = bound_inputs()
    with pytest.raises(ModelError, match="feature mismatch"):
        bind_case_set({**bound, "feature_id": "OTHER"}, model)
    bound["manual_cases"].append(copy.deepcopy(bound["manual_cases"][0]))
    with pytest.raises(ModelError, match="duplicate"):
        case_index(bound)


def test_legacy_export_preserves_identity_without_stamping_old_evidence():
    _, bound, item = bound_inputs()
    old = migrate_artifact(bound, "manual_case_set", artifact_version="legacy")
    assert "evidence_binding" not in old
    assert old["manual_cases"][0]["case_revision"] == bound["manual_cases"][0]["case_revision"]
    old_item = migrate_artifact(item, "execution_evidence", artifact_version="legacy")
    assert old_item["case_revision"] == item["case_revision"]
    assert "model_hash" not in old_item
    upgraded = migrate_artifact(old_item, "execution_evidence")
    assert upgraded["case_revision"] == item["case_revision"]


def test_bind_cli_preserves_input_and_refuses_overwrite(tmp_path):
    model, bound, _ = bound_inputs()
    original = cases(case())
    for name, data in (("model.json", model), ("cases.json", original)):
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    args = [
        "bind-cases",
        "--input",
        str(tmp_path / "cases.json"),
        "--test-model",
        str(tmp_path / "model.json"),
        "--output",
    ]
    assert main([*args, str(tmp_path / "bound.json")]) == 0
    assert main([*args, str(tmp_path / "bound.json")]) == 1
    assert main([*args, str(tmp_path / "cases.json")]) == 1
    assert main([*args, str(tmp_path / "model.json")]) == 1
    assert json.loads((tmp_path / "cases.json").read_text(encoding="utf-8")) == original


@pytest.mark.parametrize("wrong", [None, "case", "model", "report"])
def test_gate_checks_current_case_and_report_model(tmp_path, wrong):
    root = Path(__file__).resolve().parents[1] / "examples/artifacts"
    case_set = json.loads((root / "order-cancel.manual_case_set.json").read_text(encoding="utf-8"))
    model = json.loads((root / "order-cancel.test_model.json").read_text(encoding="utf-8"))
    bound = bind_case_set(case_set, model)
    tc = bound["manual_cases"][0]
    item = {
        "run_id": "RUN-1",
        "tc_id": tc["tc_id"],
        "feature_id": bound["feature_id"],
        "build_id": "B",
        "timestamp": "2026-09-10T00:00:00Z",
        "result": "pass",
        "case_revision": tc["case_revision"],
        "spec_revision": bound["spec_revision"],
        "oracle_revision": tc["oracle_revision"],
        "case_content_hash": tc["content_hash"],
        "oracle_refs": tc["oracle"]["refs"],
        "model_hash": bound["evidence_binding"]["model_hash"],
    }
    if wrong in {"case", "model"}:
        item["case_revision" if wrong == "case" else "model_hash"] = "0" * 64
    for name, data in (("cases.json", bound), ("evidence.json", item)):
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    args = [
        "--evidence",
        str(tmp_path / "evidence.json"),
        "--cases",
        str(tmp_path / "cases.json"),
        "--risk",
        str(root / "order-cancel.risk_register.json"),
        "--feature",
        str(root / "order-cancel.feature_spec.json"),
        "--model",
        str(root / "order-cancel.test_model.json"),
        "--observations",
        str(root / "order-cancel.observation_set.json"),
        "--build-id",
        "B",
        "--output",
        str(tmp_path / "gate.json"),
    ]
    if wrong == "report":
        report = {"model_hash": "0" * 64, "case_hash": digest(bound)}
        (tmp_path / "report.json").write_text(json.dumps(report), encoding="utf-8")
        args.extend(["--coverage-report", str(tmp_path / "report.json")])
    assert gate_main(args) == (0 if wrong is None else 1)
    if wrong is None:
        result = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
        assert result["evidence_summary"]["evidence_binding_mode"] == "case_revision"
