"""Regression contract tests for deterministic, review-bound E2E export."""
from __future__ import annotations

import hashlib
import json

import pytest

from bb_harness.e2e_export import E2EExportError, export_e2e


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def inputs(tmp_path):
    feature = {"feature_id": "ORDER", "revision": "spec-1"}
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
    for path, item in zip(paths, [feature, cases, binding]):
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
