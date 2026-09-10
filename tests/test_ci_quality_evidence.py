"""CI境界の負例検証。ここで作る小さな入力は実CI受入証跡ではない。"""

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/ci/quality_evidence.py"
SPEC = importlib.util.spec_from_file_location("ci_quality_evidence", MODULE_PATH)
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)
REVISION = "a" * 40


@pytest.fixture
def evidence(tmp_path):
    context = {
        "repository": "test/repository",
        "commit_sha": REVISION,
        "run_id": "1234",
        "run_attempt": 1,
        "started_at": "2026-09-11T00:00:00Z",
        "finished_at": "2026-09-11T00:01:00Z",
        "ci_provider": "generic-ci",
    }
    raw = tmp_path / "raw"
    raw.mkdir()
    ci.write(raw / "github-context.json", context)
    (raw / "junit.xml").write_text(
        '<testsuites><testsuite name="pytest"><testcase classname="tests.test_x" '
        'name="test_one" time="0.1"/></testsuite></testsuites>',
        encoding="utf-8",
    )
    (raw / "lcov.info").write_text("SF:sample.py\nDA:1,1\nend_of_record\n", encoding="utf-8")
    ci.write(
        raw / "coverage.json",
        {"meta": {"branch_coverage": True}, "totals": {"percent_covered": 90, "num_statements": 1}},
    )
    ci.write(
        tmp_path / "collection.json",
        {
            "version": "manual-bb-ci/v1",
            "coverage_floor": 85,
            "pytest_exit_code": 0,
            "coverage_export_exit_code": 0,
            "hashes": {name: ci.digest(raw / name) for name in ci.RAW_FILES},
        },
    )
    record = {
        "schema_version": "HATE/v1",
        "commit_sha": REVISION,
        "run_id": "1234",
        "run_attempt": 1,
        "source_version": ci.HATE_REVISION,
        "payload": {
            "canonical_test_id": "junit:tests/test_x.py::test_one",
            "status": "passed",
            "identity_components": {"classname": "tests.test_x", "name": "test_one"},
        },
    }
    ci.write(
        tmp_path / "hate/p0a/precheck-decision.json", {"payload": {"qeg_export_allowed": True}}
    )
    (tmp_path / "hate/p0a/HATE-test-results.ndjson").write_text(
        json.dumps(record) + "\n", encoding="utf-8"
    )
    ci.write(
        tmp_path / "hate/export/qeg-bundle.json",
        {
            "metadata": {
                "qegVersion": "HATE/v1",
                "commitSha": REVISION,
                "runId": "1234",
                "runAttempt": 1,
            },
            "completeness": {"partial": False, "parserFailures": [], "unsupportedClaims": []},
            "nodes": [{"kind": "test", "data": record["payload"]}],
        },
    )
    ci.write(
        tmp_path / "hate/export/qeg-export-report.json",
        {"qeg_schema_compatibility": {"valid": True}},
    )
    return tmp_path, context, record


def build(evidence):
    return ci.build_qeg(evidence[0], REVISION, "1234", 1)


def reseal(root):
    collection = ci.read(root / "collection.json")
    collection["hashes"] = {name: ci.digest(root / "raw" / name) for name in ci.RAW_FILES}
    ci.write(root / "collection.json", collection)


def test_conversion_preserves_identity_and_hashes(evidence):
    out = build(evidence)
    result = ci.read(out / "gate-input.json")
    assert result["policy"]["inputContract"]["requireExecutedTests"] is True
    tests = [n for n in result["graph"]["nodes"] if n["kind"] == "test"]
    assert len(tests) == 2  # 元test 1件と、実際の終了コード・coverage検査
    assert tests[0]["executionIdentity"]["caseId"] == evidence[2]["payload"]["canonical_test_id"]
    for artifact in result["metadata"]["inputArtifacts"]:
        assert ci.digest(out / artifact["path"]) == artifact["contentHash"]
        assert artifact["revision"] == REVISION
    assert result["policy"]["inputContract"]["evaluationScope"]["notEvaluated"]


@pytest.mark.parametrize("file", ci.RAW_FILES)
def test_modified_raw_evidence_is_rejected(evidence, file):
    (evidence[0] / "raw" / file).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="改変"):
        build(evidence)


@pytest.mark.parametrize(
    "revision,run,attempt", [("b" * 40, "1234", 1), (REVISION, "999", 1), (REVISION, "1234", 2)]
)
def test_cross_run_or_revision_is_rejected(evidence, revision, run, attempt):
    with pytest.raises(ValueError, match="一致"):
        ci.build_qeg(evidence[0], revision, run, attempt)


def test_empty_junit_is_rejected(evidence):
    (evidence[0] / "raw/junit.xml").write_text("<testsuites/>", encoding="utf-8")
    reseal(evidence[0])
    with pytest.raises(ValueError, match="0件"):
        build(evidence)


@pytest.mark.parametrize(
    "mutation", ["status", "identity", "revision", "duplicate", "missing", "version"]
)
def test_hate_record_mismatch_is_rejected(evidence, mutation):
    root, _, record = evidence
    if mutation == "status":
        record["payload"]["status"] = "failed"
    elif mutation == "identity":
        record["payload"]["identity_components"]["name"] = "another"
    elif mutation == "revision":
        record["commit_sha"] = "b" * 40
    elif mutation == "version":
        record["schema_version"] = "HATE/v2"
    text = json.dumps(record) + "\n"
    if mutation == "duplicate":
        text *= 2
    if mutation == "missing":
        text = ""
    (root / "hate/p0a/HATE-test-results.ndjson").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        build(evidence)


@pytest.mark.parametrize(
    "tag,status", [("failure", "failed"), ("error", "error"), ("skipped", "skipped")]
)
def test_nonpass_is_never_converted_to_pass(evidence, tag, status):
    root, _, record = evidence
    path = root / "raw/junit.xml"
    path.write_text(
        path.read_text(encoding="utf-8").replace('time="0.1"/>', f'time="0.1"><{tag}/></testcase>'),
        encoding="utf-8",
    )
    reseal(root)
    record["payload"]["status"] = status
    bundle_path = root / "hate/export/qeg-bundle.json"
    bundle = ci.read(bundle_path)
    bundle["nodes"][0]["data"]["status"] = status
    ci.write(bundle_path, bundle)
    (root / "hate/p0a/HATE-test-results.ndjson").write_text(
        json.dumps(record) + "\n", encoding="utf-8"
    )
    out = build(evidence)
    executions = [
        n["execution"]
        for n in ci.read(out / "gate-input.json")["graph"]["nodes"]
        if "execution" in n
    ]
    assert executions[0]["status"] == ci.STATUS[status]


@pytest.mark.parametrize("exit_code,percent", [(1, 90), (0, 84.99)])
def test_pytest_exit_and_coverage_floor_produce_failed_check(evidence, exit_code, percent):
    root = evidence[0]
    collection = ci.read(root / "collection.json")
    collection["pytest_exit_code"] = exit_code
    ci.write(root / "collection.json", collection)
    coverage = ci.read(root / "raw/coverage.json")
    coverage["totals"]["percent_covered"] = percent
    ci.write(root / "raw/coverage.json", coverage)
    reseal(root)
    out = build(evidence)
    executions = [
        n["execution"]
        for n in ci.read(out / "gate-input.json")["graph"]["nodes"]
        if "execution" in n
    ]
    assert executions[-1]["status"] == "fail"


def test_existing_qeg_output_is_not_overwritten(evidence):
    out = build(evidence)
    original = ci.digest(out / "gate-input.json")
    with pytest.raises(FileExistsError):
        build(evidence)
    assert ci.digest(out / "gate-input.json") == original


def test_capture_records_failure_without_fabricating_missing_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(ci, "head", lambda repo: REVISION)
    monkeypatch.setattr(
        ci.subprocess, "run", lambda *a, **k: type("Result", (), {"returncode": 3})()
    )
    out = tmp_path / "capture"
    assert ci.capture(out, tmp_path) == 3
    collection = ci.read(out / "collection.json")
    assert collection["pytest_exit_code"] == 3
    assert "junit.xml" not in collection["hashes"]
    context = ci.read(out / "raw/github-context.json")
    with pytest.raises(ValueError, match="export"):
        ci.verify_collection(out, REVISION, context["run_id"], context["run_attempt"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("partial", True),
        ("parserFailures", [{"error": "bad"}]),
        ("unsupportedClaims", [{"reason": "missing"}]),
    ],
)
def test_incomplete_export_is_rejected(evidence, field, value):
    path = evidence[0] / "hate/export/qeg-bundle.json"
    bundle = ci.read(path)
    bundle["completeness"][field] = value
    ci.write(path, bundle)
    with pytest.raises(ValueError, match="不完全"):
        build(evidence)
