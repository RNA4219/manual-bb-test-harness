"""Fail-closed, offline Lakda/manual-bb evidence handoff.

These converters never execute a product, decide pass/fail, or alter input files.
Only new output directories are allowed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from bb_harness.schema_validation import validate_artifact


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _required(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Non-empty {key} required")
    return value


def _publish(output: Path, payload: dict[str, Any]) -> dict[str, Any]:
    # Validate and build every output before creating the directory.
    if output.exists():
        raise ValueError(f"Output directory already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    for name, value in payload.items():
        (output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    return {"status": "ok", "output": str(output), "artifacts": sorted(payload)}


def export_charter(case_set_path: Path, charter_id: str, template_path: Path, output: Path) -> dict[str, Any]:
    case_set = _object(case_set_path)
    charter = next(
        (row for row in case_set.get("exploratory_charters", []) if row.get("id") == charter_id),
        None,
    )
    if charter is None:
        raise ValueError(f"Unknown exploratory charter: {charter_id}")
    source = copy.deepcopy(_object(template_path))
    if source.get("schemaVersion") != "lakda/exploration-charter/v1":
        raise ValueError("Expected Lakda exploration-charter/v1 template")
    platform = _required(source, "platform")
    source["charterId"] = f"{_required(charter, 'id')}-{platform}"
    origin: dict[str, Any] = {
        "tool": "manual-bb-test-harness",
        "charterId": charter["id"],
        "revision": _required(charter, "revision"),
        "contentHash": _required(charter, "content_hash"),
        "oracleRevision": _required(charter, "oracle_revision"),
    }
    for in_key, out_key in (
        ("priority", "priority"), ("mission", "mission"),
        ("questions", "questions"), ("trace_to", "traceTo"),
        ("basis_refs", "basisRefs"),
    ):
        if in_key in charter:
            origin[out_key] = copy.deepcopy(charter[in_key])
    if "feature_id" in case_set:
        origin["featureId"] = _required(case_set, "feature_id")
    source["origin"] = origin
    minutes = charter.get("timebox_minutes", charter.get("estimate_minutes"))
    if minutes is not None:
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or minutes <= 0:
            raise ValueError("Charter timebox must be positive and finite")
        duration = minutes * 60000
        if duration != int(duration):
            raise ValueError("Timebox does not resolve to integer milliseconds")
        if not isinstance(source.get("budget"), dict):
            raise ValueError("Lakda template budget object required")
        source["budget"]["durationMs"] = int(duration)
    handoff = {
        "schemaVersion": "manual-bb/lakda-handoff/v1",
        "sourceSha256": hashlib.sha256(case_set_path.read_bytes()).hexdigest(),
        "charterId": charter_id,
        "changedFields": ["charterId", *(["budget.durationMs"] if minutes is not None else []), "origin"],
        "reviewRequired": ["scope", "platform", "executionMode", "baseUrl", "stopWhen"],
    }
    return _publish(output, {"charter.json": source, "handoff.json": handoff})


def import_report(
    report_path: Path, session_path: Path, case_set_path: Path,
    feature_id: str, build_id: str, lakda_version: str, output: Path,
    configuration_id: str | None = None,
) -> dict[str, Any]:
    report, session, case_set = (_object(p) for p in (report_path, session_path, case_set_path))
    if report.get("schemaVersion") != "lakda/exploration-report/v1":
        raise ValueError("Unsupported Lakda exploration report schema")
    if session.get("schemaVersion") != "lakda/exploration-session/v1":
        raise ValueError("Unsupported Lakda session schema")
    if report.get("executionMode") != "real":
        raise ValueError("Only real Lakda exploration can be imported")
    origin = report.get("origin")
    if not isinstance(origin, dict) or origin.get("tool") != "manual-bb-test-harness":
        raise ValueError("Missing manual-bb origin")
    charter_id = _required(origin, "charterId")
    if report.get("charterId") and report["charterId"] != f"{charter_id}-{report.get('platform')}":
        raise ValueError("Report charterId does not match exported manual-bb charter")
    if report.get("sessionId") != session.get("sessionId") or report.get("charterDigest") != session.get("charterDigest"):
        raise ValueError("Lakda session/digest mismatch")
    if case_set.get("feature_id") != feature_id or origin.get("featureId", feature_id) != feature_id:
        raise ValueError("Feature identity mismatch")
    cases = [row for row in case_set.get("exploratory_charters", []) if row.get("id") == charter_id]
    if len(cases) != 1:
        raise ValueError("Charter identity missing or ambiguous")
    charter = cases[0]
    for a, b in (("revision", "revision"), ("contentHash", "content_hash"), ("oracleRevision", "oracle_revision")):
        if origin.get(a) != charter.get(b):
            raise ValueError(f"Charter provenance mismatch: {a}")
    if configuration_id is not None:
        configs = {c.get("id") for c in case_set.get("execution_configurations", [])}
        if configuration_id not in configs or configuration_id not in charter.get("configuration_ids", [configuration_id]):
            raise ValueError("Unknown or unauthorized execution configuration")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("findings must be an array")
    oracle_refs: list[str] = []
    attachments = [str(report_path)]
    formatted: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("finding must be an object")
        formatted.append(f"{_required(finding, 'kind')} / {_required(finding, 'severity')}: {_required(finding, 'message')}")
        for ref in finding.get("oracleRefs", []):
            if not isinstance(ref, str) or not ref:
                raise ValueError("Invalid oracle reference")
            if ref not in oracle_refs:
                oracle_refs.append(ref)
        for ref in finding.get("evidenceRefs", []):
            if not isinstance(ref, str) or not ref:
                raise ValueError("Invalid evidence reference")
            if ref not in attachments:
                attachments.append(ref)
    if not oracle_refs:
        oracle_refs = list(origin.get("basisRefs", []))
    if not oracle_refs:
        raise ValueError("Cannot create execution evidence without oracle refs")
    duration = session.get("activeDurationMs", 0)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
        raise ValueError("Invalid activeDurationMs")
    evidence: dict[str, Any] = {
        "run_id": _required(report, "sessionId"),
        "charter_id": charter_id,
        "case_revision": _required(origin, "revision"),
        "case_content_hash": _required(origin, "contentHash"),
        "oracle_revision": _required(origin, "oracleRevision"),
        "spec_revision": _required(case_set, "spec_revision"),
        "feature_id": feature_id,
        "build_id": build_id,
        "timestamp": _required(session, "updatedAt"),
        "tester": f"Lakda {lakda_version}",
        "oracle_refs": oracle_refs,
        "findings": formatted,
        "attachments": attachments,
        "time_spent_minutes": round(duration / 60000, 4),
        "result": "blocked" if report.get("technicalOutcome") == "error" or report.get("sessionStatus", report.get("status")) == "aborted" else "unknown",
    }
    if configuration_id:
        evidence["configuration_id"] = configuration_id
    if report.get("technicalOutcome") == "partial" and report.get("terminationReason"):
        evidence["anomaly_notes"] = [str(report["terminationReason"])]
    validate_artifact(evidence, "execution_evidence.schema.json")
    handoff = {
        "schemaVersion": "manual-bb/lakda-handoff/v1",
        "charterDigest": report["charterDigest"],
        "targetRevision": report.get("targetRevision"),
        "executionMode": report["executionMode"],
        "acceptanceStatus": report.get("acceptanceStatus"),
        "humanReviewRequired": True,
    }
    return _publish(output, {"execution_evidence.json": evidence, "handoff.json": handoff})


def import_replay(
    runs_dir: Path, traces_dir: Path, suite_id: str, merge_path: Path, output: Path
) -> dict[str, Any]:
    # Require exact replay input hashes and per-run HATE manifests; never infer an
    # executed trace from a similarly named file or a run folder.
    source = _object(merge_path)
    validate_artifact(source, "automation_evidence.schema.json")
    if any(row.get("suite_id") == suite_id for row in source["test_suites"]):
        raise ValueError("Duplicate suite id")
    traces = sorted(traces_dir.rglob("action-sequence.json"))
    if not traces:
        raise ValueError("No promoted action sequences found")
    expected = {hashlib.sha256(p.read_bytes()).hexdigest(): p for p in traces}
    if len(expected) != len(traces):
        raise ValueError("Duplicate trace contents are ambiguous")
    matched: dict[str, str] = {}
    refs: list[dict[str, str]] = []
    for path in sorted(runs_dir.glob("*/run-metadata.json")):
        item = _object(path)
        if item.get("mode") != "regression-replay":
            continue
        digest = item.get("replayInputSha256")
        if not isinstance(digest, str) or digest not in expected:
            raise ValueError("Unbound replay result: missing or unknown input digest")
        if digest in matched:
            raise ValueError("Multiple run outcomes for one promoted trace")
        if item.get("executionMode") != "real":
            raise ValueError("Replay is not explicitly bound to an approved real execution")
        outcome = item.get("outcome")
        if outcome not in ("passed", "failed", "error", "partial"):
            raise ValueError("Unknown or unfinished replay outcome")
        manifest = path.parent / "exports" / "artifact-manifest.json"
        if not manifest.is_file():
            raise ValueError(f"Missing HATE manifest for {path}")
        _object(manifest)
        refs.append({"id": str(manifest), "kind": "auto_test"})
        matched[digest] = outcome
    outcomes = list(matched.values())
    passed = outcomes.count("passed")
    failed = outcomes.count("failed")
    errors = outcomes.count("error") + outcomes.count("partial")
    skipped = len(expected) - len(matched)
    status = (
        "not_run" if not outcomes else
        "failed" if failed else "error" if errors else
        "passed" if skipped == 0 else "not_run"
    )
    suite = {
        "suite_id": suite_id, "status": status, "total": len(expected),
        "passed": passed, "failed": failed, "errors": errors, "skipped": skipped,
        "source_refs": refs or [{"id": f"not-run:{suite_id}", "kind": "memo"}],
    }
    result = copy.deepcopy(source)
    result["test_suites"].append(suite)
    validate_artifact(result, "automation_evidence.schema.json")
    return _publish(output, {"automation_evidence.json": result, "handoff.json": {
        "schemaVersion": "manual-bb/lakda-handoff/v1", "suiteId": suite_id,
        "traceCount": len(traces), "boundRunCount": len(matched),
        "gateDecision": "external-qeg-required",
    }})
