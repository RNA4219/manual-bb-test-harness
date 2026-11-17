"""Acceptance tests for offline Lakda/manual-bb handoff."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from bb_harness.lakda_bridge import export_charter, import_replay, import_report
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schemaVersion", "unknown"),
        ("platform", ""),
    ],
)
def test_export_rejects_invalid_template(tmp_path: Path, field: str, value: object) -> None:
    case = write(tmp_path / "cases.json", case_set())
    template_data = template()
    template_data[field] = value
    source = write(tmp_path / "template.json", template_data)
    with pytest.raises(ValueError):
        export_charter(case, "CH-1", source, tmp_path / "reject")
    assert not (tmp_path / "reject").exists()


@pytest.mark.parametrize(
    "minutes",
    [True, 0, -1, "0.5", float("inf"), 0.000001],
)
def test_export_rejects_invalid_timebox(tmp_path: Path, minutes: object) -> None:
    case = case_set()
    case["exploratory_charters"][0]["timebox_minutes"] = minutes
    source = write(tmp_path / "cases.json", case)
    template_path = write(tmp_path / "template.json", template())
    with pytest.raises(ValueError):
        export_charter(source, "CH-1", template_path, tmp_path / "reject")
    assert not (tmp_path / "reject").exists()


def test_export_missing_charter_and_no_timebox(tmp_path: Path) -> None:
    source = case_set()
    source["exploratory_charters"][0].pop("estimate_minutes")
    path = write(tmp_path / "source.json", source)
    template_path = write(tmp_path / "template.json", template())
    export_charter(path, "CH-1", template_path, tmp_path / "valid")
    assert json.loads((tmp_path / "valid/charter.json").read_text())["budget"]["durationMs"] == 1000
    with pytest.raises(ValueError, match="Unknown exploratory charter"):
        export_charter(path, "UNKNOWN", template_path, tmp_path / "reject")


@pytest.mark.parametrize(
    "mutation",
    [
        "no-origin", "wrong-tool", "wrong-charter-id", "session-id",
        "digest", "feature-id", "revision", "oracle-revision",
        "bad-findings", "bad-finding", "bad-oracle", "bad-evidence",
        "bad-duration", "unknown-case",
    ],
)
def test_report_rejects_broken_evidence(
    tmp_path: Path, mutation: str
) -> None:
    rep, sess, cases = report(), session(), case_set()
    if mutation == "no-origin":
        rep.pop("origin")
    elif mutation == "wrong-tool":
        rep["origin"]["tool"] = "unknown"
    elif mutation == "wrong-charter-id":
        rep["charterId"] = "wrong"
    elif mutation == "session-id":
        sess["sessionId"] = "wrong"
    elif mutation == "digest":
        sess["charterDigest"] = "wrong"
    elif mutation == "feature-id":
        rep["origin"]["featureId"] = "other"
    elif mutation == "revision":
        rep["origin"]["revision"] = "wrong"
    elif mutation == "oracle-revision":
        rep["origin"]["oracleRevision"] = "wrong"
    elif mutation == "bad-findings":
        rep["findings"] = None
    elif mutation == "bad-finding":
        rep["findings"] = [0]
    elif mutation == "bad-oracle":
        rep["findings"][0]["oracleRefs"] = [0]
    elif mutation == "bad-evidence":
        rep["findings"][0]["evidenceRefs"] = [None]
    elif mutation == "bad-duration":
        sess["activeDurationMs"] = -1
    elif mutation == "unknown-case":
        cases["exploratory_charters"] = []
    report_path = write(tmp_path / "report.json", rep)
    session_path = write(tmp_path / "session.json", sess)
    case_path = write(tmp_path / "cases.json", cases)
    with pytest.raises((ValueError, TypeError, KeyError)):
        import_report(report_path, session_path, case_path, "F-1", "b1", "v1", tmp_path / "reject")
    assert not (tmp_path / "reject").exists()


def test_report_rejects_unauthorized_configuration(tmp_path: Path) -> None:
    rep = write(tmp_path / "report.json", report())
    sess = write(tmp_path / "session.json", session())
    cases = case_set()
    cases["execution_configurations"] = [{"id": "c1", "env": "test"}]
    cases["exploratory_charters"][0]["configuration_ids"] = ["c1"]
    case = write(tmp_path / "cases.json", cases)
    with pytest.raises(ValueError, match="configuration"):
        import_report(rep, sess, case, "F-1", "b1", "v1", tmp_path / "reject", "other")
    assert not (tmp_path / "reject").exists()


@pytest.mark.parametrize("mutation", ["duplicate-suite", "no-traces", "missing-digest", "unknown-digest",
                                      "duplicate-run", "no-manifest", "unknown-outcome", "fixture-run"])
def test_replay_rejects_ambiguous_or_untrusted_run(tmp_path: Path, mutation: str) -> None:
    source = {"feature_id": "F-1", "build_id": "b1", "coverage_scope": "changed_code",
              "coverage_percent": 81, "new_issues": {"blocker": 0, "critical": 0},
              "source_refs": [{"id": "ci-1", "kind": "auto_test"}],
              "test_suites": [{"suite_id": "unit", "status": "passed", "total": 1,
                               "passed": 1, "failed": 0, "errors": 0, "skipped": 0,
                               "source_refs": [{"id": "unit", "kind": "auto_test"}]}]}
    merged = write(tmp_path / "automation.json", source)
    traces = tmp_path / "traces"
    trace = write(traces / "p1/action-sequence.json", {"actions": [1]})
    if mutation == "no-traces":
        trace.unlink()
    if mutation == "duplicate-suite":
        suite_id = "unit"
    else:
        suite_id = "promoted"
    run = tmp_path / "runs" / "r1"
    metadata = {
        "mode": "regression-replay", "outcome": "passed", "executionMode": "real",
        "replayInputSha256": hashlib.sha256(trace.read_bytes()).hexdigest()
        if trace.exists() else "0" * 64,
    }
    if mutation == "missing-digest":
        metadata.pop("replayInputSha256")
    elif mutation == "unknown-digest":
        metadata["replayInputSha256"] = "0" * 64
    elif mutation == "unknown-outcome":
        metadata["outcome"] = "aborted"
    elif mutation == "fixture-run":
        metadata["executionMode"] = "fixture"
    write(run / "run-metadata.json", metadata)
    if mutation != "no-manifest":
        write(run / "exports/artifact-manifest.json", {"schemaVersion": "hate/v1"})
    if mutation == "duplicate-run":
        write(tmp_path / "runs" / "r2/run-metadata.json", metadata)
        write(tmp_path / "runs" / "r2/exports/artifact-manifest.json",
              {"schemaVersion": "hate/v1"})
    with pytest.raises(ValueError):
        import_replay(tmp_path / "runs", traces, suite_id, merged, tmp_path / "reject")
    assert not (tmp_path / "reject").exists()
