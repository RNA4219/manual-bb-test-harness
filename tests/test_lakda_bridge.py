"""Acceptance tests for offline Lakda/manual-bb handoff."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from bb_harness.lakda_bridge import export_charter, import_report, import_replay
from bb_harness.schema_validation import validate_artifact


def write(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def case_set() -> dict:
    return {"feature_id": "F-1", "spec_revision": "s1", "exploratory_charters": [
        {"id": "CH-1", "revision": "r1", "content_hash": "hash1", "oracle_revision": "o1",
         "title": "Explore", "scope": "Scope", "questions": ["What happens?"], "trace_to": ["OBS-1"],
         "basis_refs": ["AC-1"], "estimate_minutes": 12}]}


def template() -> dict:
    return {"schemaVersion": "lakda/exploration-charter/v1", "charterId": "original",
            "platform": "pc-web", "executionMode": "fixture", "baseUrl": "http://127.0.0.1:3000",
            "scope": {"allowHosts": ["127.0.0.1"]}, "budget": {"durationMs": 1000},
            "stopWhen": {"any": []}, "generator": {"strategy": "autonomous-uncovered"}}


def test_export_changes_only_identity_time_and_origin(tmp_path: Path) -> None:
    source = write(tmp_path / "cases.json", case_set())
    before = template()
    t = write(tmp_path / "template.json", before)
    export_charter(source, "CH-1", t, tmp_path / "out")
    result = json.loads((tmp_path / "out/charter.json").read_text())
    expected = copy.deepcopy(before)
    expected["charterId"] = "CH-1-pc-web"
    expected["budget"]["durationMs"] = 720000
    expected["origin"] = {"tool": "manual-bb-test-harness", "charterId": "CH-1",
                          "revision": "r1", "contentHash": "hash1", "oracleRevision": "o1",
                          "featureId": "F-1", "questions": ["What happens?"],
                          "traceTo": ["OBS-1"], "basisRefs": ["AC-1"]}
    assert result == expected
    with pytest.raises(ValueError, match="already exists"):
        export_charter(source, "CH-1", t, tmp_path / "out")


def report() -> dict:
    return {"schemaVersion": "lakda/exploration-report/v1", "sessionId": "session-1",
            "charterId": "CH-1-pc-web", "charterDigest": "sha256:" + "a" * 64,
            "platform": "pc-web", "executionMode": "real", "targetRevision": "build",
            "technicalOutcome": "partial", "terminationReason": "timeout",
            "acceptanceStatus": "pending_external",
            "origin": {"tool": "manual-bb-test-harness", "charterId": "CH-1",
                       "revision": "r1", "contentHash": "hash1", "oracleRevision": "o1",
                       "featureId": "F-1", "basisRefs": ["AC-1"]},
            "findings": [{"kind": "crash", "severity": "warning", "message": "Broken",
                          "oracleRefs": ["oracle-1"], "evidenceRefs": ["evidence-1"]}]}


def session() -> dict:
    return {"schemaVersion": "lakda/exploration-session/v1", "sessionId": "session-1",
            "charterDigest": "sha256:" + "a" * 64, "updatedAt": "2026-11-17T08:00:00Z",
            "activeDurationMs": 90000}


def test_import_unknown_and_blocks_invalid_provenance(tmp_path: Path) -> None:
    r = write(tmp_path / "report.json", report())
    s = write(tmp_path / "session.json", session())
    c = write(tmp_path / "case-set.json", case_set())
    import_report(r, s, c, "F-1", "build", "0.5.0", tmp_path / "ok")
    evidence = json.loads((tmp_path / "ok/execution_evidence.json").read_text())
    assert evidence["result"] == "unknown"
    assert evidence["charter_id"] == "CH-1"
    assert evidence["anomaly_notes"] == ["timeout"]
    validate_artifact(evidence, "execution_evidence.schema.json")
    wrong = report()
    wrong["origin"]["contentHash"] = "tampered"
    write(r, wrong)
    with pytest.raises(ValueError, match="provenance"):
        import_report(r, s, c, "F-1", "build", "0.5.0", tmp_path / "refuse")
    assert not (tmp_path / "refuse").exists()
    wrong["origin"]["contentHash"] = "hash1"
    wrong["executionMode"] = "fixture"
    write(r, wrong)
    with pytest.raises(ValueError, match="Only real"):
        import_report(r, s, c, "F-1", "build", "0.5.0", tmp_path / "fixture")
    assert not (tmp_path / "fixture").exists()


def test_import_error_blocked_and_missing_oracle_rejected(tmp_path: Path) -> None:
    case = write(tmp_path / "c.json", case_set())
    sess = write(tmp_path / "s.json", session())
    doc = report()
    doc["technicalOutcome"] = "error"
    doc["findings"] = []
    rep = write(tmp_path / "r.json", doc)
    import_report(rep, sess, case, "F-1", "build", "0.5.0", tmp_path / "blocked")
    assert json.loads((tmp_path / "blocked/execution_evidence.json").read_text())["result"] == "blocked"
    doc["origin"].pop("basisRefs")
    write(rep, doc)
    with pytest.raises(ValueError, match="oracle refs"):
        import_report(rep, sess, case, "F-1", "build", "0.5.0", tmp_path / "no-oracle")


def test_replay_suite_counts_missing_trace_and_keeps_coverage(tmp_path: Path) -> None:
    source = {"feature_id": "F-1", "build_id": "b1", "coverage_scope": "changed_code",
              "coverage_percent": 81, "new_issues": {"blocker": 0, "critical": 0},
              "source_refs": [{"id": "ci-1", "kind": "auto_test"}],
              "test_suites": [{"suite_id": "unit", "status": "passed", "total": 1,
                               "passed": 1, "failed": 0, "errors": 0, "skipped": 0,
                               "source_refs": [{"id": "unit-1", "kind": "auto_test"}]}]}
    original = write(tmp_path / "automation.json", source)
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    trace_dir = tmp_path / "traces"
    for index in range(3):
        write(trace_dir / f"p{index}" / "action-sequence.json", {"actions": [index]})
    for index in range(2):
        trace = trace_dir / f"p{index}" / "action-sequence.json"
        run = tmp_path / "runs" / f"run{index}"
        write(run / "run-metadata.json", {"mode": "regression-replay",
              "executionMode": "real", "replayInputSha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
              "outcome": "passed"})
        write(run / "exports" / "artifact-manifest.json", {"schemaVersion": "hate/v1"})
    import_replay(tmp_path / "runs", trace_dir, "promoted", original, tmp_path / "result")
    artifact = json.loads((tmp_path / "result/automation_evidence.json").read_text())
    suite = artifact["test_suites"][-1]
    assert suite["total"] == 3
    assert suite["skipped"] == 1
    assert suite["status"] == "not_run"
    assert artifact["coverage_percent"] == 81
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    validate_artifact(artifact, "automation_evidence.schema.json")


def test_unbound_run_rejected_and_zero_runs_not_run(tmp_path: Path) -> None:
    base = {"feature_id": "f", "build_id": "b", "coverage_scope": "changed_code",
        "coverage_percent": 80, "new_issues": {"blocker": 0, "critical": 0},
        "source_refs": [{"id": "unit", "kind": "auto_test"}],
        "test_suites": [{"suite_id": "unit", "status": "passed", "total": 1,
                         "passed": 1, "failed": 0, "errors": 0, "skipped": 0,
                         "source_refs": [{"id": "unit", "kind": "auto_test"}]}]}
    merge = write(tmp_path / "merge.json", base)
    traces = tmp_path / "traces"
    write(traces / "p0/action-sequence.json", {"actions": []})
    (tmp_path / "runs").mkdir()
    import_replay(tmp_path / "runs", traces, "promoted", merge, tmp_path / "none")
    suite = json.loads((tmp_path / "none/automation_evidence.json").read_text())["test_suites"][-1]
    assert suite["status"] == "not_run"
    write(tmp_path / "runs/run1/run-metadata.json",
          {"mode": "regression-replay", "outcome": "passed"})
    with pytest.raises(ValueError, match="Unbound"):
        import_replay(tmp_path / "runs", traces, "promoted", merge, tmp_path / "no")
