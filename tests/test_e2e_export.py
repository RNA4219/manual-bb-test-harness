"""Regression contract tests for deterministic, review-bound E2E export."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from bb_harness.e2e_export import E2EExportError, export_e2e


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def inputs(tmp_path):
    feature = {"feature_id": "ORDER", "revision": "spec-1",
               "acceptance_criteria": ["Confirmation is visible"],
               "source_refs": [{"id": "AC-1", "kind": "ac"}]}
    cases = {"feature_id": "ORDER", "spec_revision": "spec-1", "manual_cases": [
        {"tc_id": "TC-001", "title": "Order confirmation", "revision": "rev-1",
         "content_hash": "case-hash-1", "oracle_revision": "oracle-1",
         "oracle": {"type": "specified", "refs": ["AC-1"]},
         "steps": ["Open order page", "Confirm order"],
         "expected_results": ["Confirmation is visible"], "status": "active"}
    ]}
    binding = {"schemaVersion": "manual-bb/e2e-binding/v1", "featureId": "ORDER",
               "specRevision": "spec-1", "baseUrl": "https://app.example.test/",
               "featureSha256": digest(feature), "caseSetSha256": digest(cases),
               "seed": 4219, "cases": [
                   {"caseId": "TC-001", "revision": "rev-1", "contentHash": "case-hash-1",
                    "oracleRevision": "oracle-1", "reviewRef": "PR-10", "reviewedBy": "qa-reviewer",
                    "actions": [{"id": "open-order", "kind": "navigate", "path": "/order"},
                                {"id": "confirm", "kind": "click",
                                 "locator": {"role": "button", "name": "Confirm"}}],
                    "checks": [{"text": "Confirmation is visible", "kind": "visible",
                                "locator": {"testId": "confirmation"}}]}
               ]}
    paths = [tmp_path / "feature.json", tmp_path / "cases.json", tmp_path / "binding.json"]
    for path, item in zip(paths, [feature, cases, binding], strict=True):
        path.write_text(json.dumps(item), encoding="utf-8")
    return paths, binding


def test_export_deterministic_review_and_replay(tmp_path):
    (feature, cases, binding_path), _ = inputs(tmp_path)
    out = tmp_path / "out"
    assert export_e2e(feature, cases, binding_path, out) == ["TC-001"]
    folder = out / "TC-001"
    plan = json.loads((folder / "action-sequence.json").read_text())
    cfg = json.loads((folder / "lakda.config.json").read_text())
    manifest = json.loads((folder / "manifest.json").read_text())
    assert plan["actions"][1]["locator"]["name"] == "Confirm"
    assert cfg["obligations"] == [{"visible": {"testId": "confirmation"}}]
    assert "toBeVisible()" in (folder / "scenario.spec.ts").read_text()
    for filename, sha in manifest["filesSha256"].items():
        assert hashlib.sha256((folder / filename).read_bytes()).hexdigest() == sha
    with pytest.raises(E2EExportError, match="exists"):
        export_e2e(feature, cases, binding_path, out)
    other = tmp_path / "other"
    export_e2e(feature, cases, binding_path, other)
    for filename in manifest["filesSha256"]:
        assert (folder / filename).read_bytes() == (other / "TC-001" / filename).read_bytes()


@pytest.mark.parametrize("mutation", ["unknown", "tamper", "retired", "secret", "missing_check", "unsafe_action"])
def test_fails_closed(tmp_path, mutation):
    paths, data = inputs(tmp_path)
    case_data = json.loads(paths[1].read_text())
    if mutation == "unknown":
        data["cases"][0]["checks"][0]["kind"] = "text-equals"
    elif mutation == "tamper":
        data["cases"][0]["contentHash"] = "stale"
    elif mutation == "retired":
        case_data["manual_cases"][0]["status"] = "retired"
        paths[1].write_text(json.dumps(case_data))
        data["caseSetSha256"] = digest(case_data)
    elif mutation == "secret":
        data["cases"][0]["reviewRef"] = "password=badvalue"
    elif mutation == "missing_check":
        data["cases"][0]["checks"] = []
    elif mutation == "unsafe_action":
        data["cases"][0]["actions"][1]["selector"] = "#secret"
    paths[2].write_text(json.dumps(data))
    with pytest.raises(E2EExportError):
        export_e2e(*paths, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_reviewed_expected_urls_must_use_exact_origin(tmp_path):
    paths, binding = inputs(tmp_path)
    binding["cases"][0]["checks"] = [{
        "text": "Confirmation is visible", "kind": "url",
        "value": "https://app.example.test:8443/order",
    }]
    paths[2].write_text(json.dumps(binding), encoding="utf-8")
    with pytest.raises(E2EExportError, match="approved target"):
        export_e2e(*paths, tmp_path / "out")


def test_secret_in_human_steps_must_not_enter_generated_artifacts(tmp_path):
    paths, binding = inputs(tmp_path)
    cases = json.loads(paths[1].read_text(encoding="utf-8"))
    cases["manual_cases"][0]["steps"][0] = "password=abc123"
    paths[1].write_text(json.dumps(cases), encoding="utf-8")
    binding["caseSetSha256"] = digest(cases)
    paths[2].write_text(json.dumps(binding), encoding="utf-8")
    with pytest.raises(E2EExportError, match="possible secret"):
        export_e2e(*paths, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_invalid_input_profile_identifier_is_rejected(tmp_path):
    paths, binding = inputs(tmp_path)
    binding["cases"][0]["actions"][1] = {
        "id": "confirm", "kind": "fill",
        "locator": {"role": "textbox", "name": "Recipient"},
        "inputProfileId": "../secret",
    }
    paths[2].write_text(json.dumps(binding), encoding="utf-8")
    with pytest.raises(E2EExportError, match="invalid input profile"):
        export_e2e(*paths, tmp_path / "out")


def test_reviewed_example_round_trip_and_all_published_contracts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    sample = root / "examples" / "artifacts"
    schema_root = root / "schemas"
    packaged = root / "src" / "bb_harness" / "schemas"
    inputs = [
        sample / "e2e-sample.feature_spec.json",
        sample / "e2e-sample.manual_case_set.json",
        sample / "e2e-sample.e2e-binding.json",
    ]
    output = tmp_path / "example-output"
    assert export_e2e(*inputs, output) == ["TC-001"]
    for schema_name, artifact in [
        ("e2e_binding", inputs[2]),
        ("e2e_scenario", output / "TC-001" / "scenario.json"),
        ("e2e_export", output / "TC-001" / "manifest.json"),
    ]:
        root_schema = json.loads((schema_root / (schema_name + ".schema.json")).read_text())
        package_schema = json.loads((packaged / (schema_name + ".schema.json")).read_text())
        assert root_schema == package_schema
        Draft202012Validator.check_schema(root_schema)
        Draft202012Validator(root_schema).validate(json.loads(artifact.read_text()))
    for artifact, example in [
        ("scenario.json", "e2e-sample.e2e-scenario.json"),
        ("manifest.json", "e2e-sample.e2e-export.json"),
    ]:
        assert json.loads((output / "TC-001" / artifact).read_text()) == json.loads(
            (sample / example).read_text()
        )
    manifest = json.loads((output / "TC-001" / "manifest.json").read_text())
    for filename, expected in manifest["filesSha256"].items():
        saved_bytes = (output / "TC-001" / filename).read_bytes()
        assert hashlib.sha256(saved_bytes).hexdigest() == expected
        assert b"\r\n" not in saved_bytes  # Windows byte-level stability


def test_all_new_example_artifacts_are_discoverable_by_cli():
    from bb_harness.tools.validate_artifact import validate_artifact
    root = Path(__file__).resolve().parents[1] / "examples" / "artifacts"
    for suffix in ("e2e-binding", "e2e-scenario", "e2e-export"):
        result = validate_artifact(root / ("e2e-sample." + suffix + ".json"))
        assert result["valid"], result["errors"]


def test_authenticated_verification_only_step_replays_at_correct_position(tmp_path):
    paths, binding = inputs(tmp_path)
    cases = json.loads(paths[1].read_text(encoding="utf-8"))
    cases["manual_cases"][0]["steps"] = ["Go to admin", "Verify deletion is hidden"]
    cases["manual_cases"][0]["expected_results"] = ["Deletion is hidden"]
    paths[1].write_text(json.dumps(cases), encoding="utf-8")
    binding["caseSetSha256"] = digest(cases)
    entry = binding["cases"][0]
    entry["actions"] = [{"id": "open-admin", "kind": "navigate", "path": "/admin", "stepIndex": 0}]
    entry["checks"] = [{"text": "Deletion is hidden", "kind": "hidden",
                        "locator": {"testId": "delete-button"}, "atStep": 1}]
    entry["auth"] = {"persona": "member", "validationPath": "/dashboard",
                     "loginUrlPattern": "/login", "requiredLocator": {"testId": "member-menu"}}
    paths[2].write_text(json.dumps(binding), encoding="utf-8")
    output = tmp_path / "export"
    assert export_e2e(*paths, output) == ["TC-001"]
    folder = output / "TC-001"
    plan = json.loads((folder / "action-sequence.json").read_text())
    config = json.loads((folder / "lakda.config.json").read_text())
    scenario = json.loads((folder / "scenario.json").read_text())
    assert plan["actions"] == [
        {"id": "open-admin", "kind": "navigate", "path": "/admin"},
        {"id": "assert-step-2-1", "kind": "assert", "assertion": {"hidden": {"testId": "delete-button"}}},
    ]
    assert config["persona"] == "member"
    assert config["personas"]["member"]["validationPath"] == "/dashboard"
    assert config["obligations"] == []
    assert scenario["machineChecks"][0]["atStep"] == 1
    script = (folder / "scenario.spec.ts").read_text()
    assert 'test.use({ storageState: ".lakda/auth/member.json" });' in script
    assert ".toBeHidden()" in script
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "e2e_scenario.schema.json").read_text())
    Draft202012Validator(schema).validate(scenario)


@pytest.mark.parametrize(("kind", "value", "expectation"), [
    ("hidden", None, "toBeHidden"),
    ("enabled", None, "toBeEnabled"),
    ("disabled", None, "toBeDisabled"),
    ("text", "Approved", "toHaveText"),
])
def test_new_final_oracles(tmp_path, kind, value, expectation):
    paths, binding = inputs(tmp_path)
    check = {"text": "Confirmation is visible", "kind": kind, "locator": {"testId": "confirmation"}}
    if value is not None:
        check["value"] = value
    binding["cases"][0]["checks"] = [check]
    paths[2].write_text(json.dumps(binding))
    output = tmp_path / "out"
    export_e2e(*paths, output)
    config = json.loads((output / "TC-001" / "lakda.config.json").read_text())
    assert config["obligations"][0].get(kind) is not None
    assert expectation in (output / "TC-001" / "scenario.spec.ts").read_text()


@pytest.mark.parametrize("change", [
    "uncovered_step", "missing_action_index", "invalid_check_index",
    "unauthorized_auth", "secret_text", "mutation_no_reset", "reset_remote",
    "duplicate_assertion_id",
])
def test_new_bindings_fail_closed(tmp_path, change):
    paths, binding = inputs(tmp_path)
    entry = binding["cases"][0]
    entry["actions"] = [{"id": "open", "kind": "navigate", "path": "/order", "stepIndex": 0}]
    entry["checks"][0]["atStep"] = 1
    if change == "uncovered_step":
        entry["checks"][0].pop("atStep")
    elif change == "missing_action_index":
        entry["actions"][0].pop("stepIndex")
    elif change == "invalid_check_index":
        entry["checks"][0]["atStep"] = 999
    elif change == "unauthorized_auth":
        entry["auth"] = {"persona": "member", "validationPath": "/dashboard",
                         "loginUrlPattern": "/login", "requiredLocator": {"testId": "foo"},
                         "storageStatePath": "/tmp/unsafe"}
    elif change == "secret_text":
        entry["checks"][0]["kind"] = "text"
        entry["checks"][0]["value"] = "password=raw"
    elif change in {"mutation_no_reset", "reset_remote"}:
        entry["actions"][0]["mutates"] = True
        if change == "reset_remote":
            entry["fixtureReset"] = {"url": "https://prod.example.test/reset"}
    elif change == "duplicate_assertion_id":
        entry["actions"][0]["id"] = "assert-step-2-1"
    paths[2].write_text(json.dumps(binding), encoding="utf-8")
    with pytest.raises(E2EExportError):
        export_e2e(*paths, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_mutation_requires_explicit_loopback_reset(tmp_path):
    paths, binding = inputs(tmp_path)
    binding["cases"][0]["actions"][1]["mutates"] = True
    binding["cases"][0]["fixtureReset"] = {"url": "http://127.0.0.1:3000/reset"}
    paths[2].write_text(json.dumps(binding))
    export_e2e(*paths, tmp_path / "out")
    config = json.loads((tmp_path / "out" / "TC-001" / "lakda.config.json").read_text())
    assert config["fixtureReset"] == {"url": "http://127.0.0.1:3000/reset"}
    assert config["actionCatalog"][1]["mutates"] is True


def test_reviewed_auth_checkpoint_example_contract(tmp_path):
    root = Path(__file__).resolve().parents[1]
    sample = root / "examples" / "artifacts"
    binding_path = sample / "e2e-auth-checkpoint.e2e-binding.json"
    schema = json.loads((root / "schemas" / "e2e_binding.schema.json").read_text())
    Draft202012Validator(schema).validate(json.loads(binding_path.read_text()))
    out = tmp_path / "new-example"
    export_e2e(sample / "e2e-sample.feature_spec.json",
               sample / "e2e-sample.manual_case_set.json", binding_path, out)
    plan = json.loads((out / "TC-001" / "action-sequence.json").read_text())
    assert plan["actions"][-1]["kind"] == "assert"
