"""レビュー R11/R18/R20 の運用契約。ISTQB が定める判定規則ではない。

必要な判断材料と一意なケース定義を受領してから Gate を計算し、
数値は有限値、実績区分は相互排他的に扱う本ツールの契約を検証する。
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from bb_harness.gate_engine import (
    GateInputError,
    assess_residual_risks,
    count_results_by_priority,
    evaluate_gate,
    extract_case_results,
    main,
    validate_schema,
)

FEATURE = "GATE-REVIEW-01"
BUILD = "build-review-01"
OUTCOMES = ("pass", "fail", "skip", "blocked", "unknown", "untested")


@pytest.fixture
def artifacts() -> dict[str, dict[str, Any]]:
    """各不正入力と対にする、単独で Go になる最小の判断材料。"""
    source = {"id": "AC-1", "kind": "ac"}
    return {
        "feature": {
            "feature_id": FEATURE,
            "revision": "spec-rev-1",
            "title": "保存結果を確認する",
            "acceptance_criteria": ["AC-1: 保存後に入力値を表示する"],
            "source_refs": [source],
        },
        "model": {
            "feature_id": FEATURE,
            "coverage_items": [{
                "id": "COV-FLOW-SAVE", "dimension": "flow", "technique": "use_case",
                "applicability": "applicable", "mandatory": True,
                "coverage_criterion": "each_item", "source_refs": [source],
            }],
            "flows": ["save"], "data_partitions": [], "rule_columns": [],
            "states": [], "role_matrix": [], "regression_edges": [],
        },
        "observations": {
            "feature_id": FEATURE,
            "observations": [{
                "id": "OBS-SAVE-01", "title": "保存結果", "view": "black",
                "coverage_item_id": "COV-FLOW-SAVE",
                "mandatory": True, "techniques": ["use_case"],
                "source_refs": [source],
            }],
        },
        "risk": {
            "feature_id": FEATURE,
            "risks": [{
                "id": "RISK-1", "scenario": "保存した値を失う",
                "impact": 5, "likelihood": 5, "priority": "P0",
                "trace_to": ["TC-1"],
            }],
        },
        "cases": {
            "feature_id": FEATURE,
            "spec_revision": "spec-rev-1",
            "manual_cases": [{
                "tc_id": "TC-1", "title": "入力値を保存する", "priority": "P0",
                "revision": "case-rev-1", "content_hash": "sha256:tc-1",
                "oracle_revision": "oracle-rev-1",
                "primary_view": "black", "steps": ["値を入力して保存する"],
                "expected_results": ["保存した値が表示される"],
                "oracle": {"type": "specified", "refs": ["AC-1"]},
                "source_ref": {"type": "acceptance", "refs": ["AC-1"]},
                "trace_to": ["OBS-SAVE-01", "RISK-1"],
            }],
        },
        "evidence": {
            "run_id": "RUN-1", "tc_id": "TC-1", "feature_id": FEATURE,
            "build_id": BUILD, "timestamp": "2026-09-12T10:00:00+09:00",
            "case_revision": "case-rev-1", "spec_revision": "spec-rev-1",
            "oracle_revision": "oracle-rev-1", "case_content_hash": "sha256:tc-1",
            "oracle_refs": ["AC-1"],
            "result": "pass", "actual": ["保存した値が表示された"],
        },
        "automation": {
            "feature_id": FEATURE, "build_id": BUILD,
            "coverage_scope": "changed_code", "coverage_percent": 100,
            "hotspot_review_percent": 100,
            "test_suites": [{"suite_id": "regression", "status": "passed", "total": 1, "passed": 1, "failed": 0, "errors": 0, "skipped": 0, "source_refs": [{"id": "CI-1", "kind": "auto_test"}]}],
            "new_issues": {"blocker": 0, "critical": 0},
            "source_refs": [{"id": "CI-1", "kind": "auto_test"}],
        },
    }


def run_cli(
    tmp_path: Path, artifacts: dict[str, dict[str, Any]],
    *, omitted: tuple[str, ...] = (),
) -> tuple[int, Path]:
    output = tmp_path / "gate.json"
    argv = ["--profile", "strict", "--build-id", BUILD, "--output", str(output)]
    for name, artifact in artifacts.items():
        if name in omitted:
            continue
        path = tmp_path / f"{name}.json"
        # 不正な NaN/Infinity の JSON 入力も CLI で拒否されることを確認する。
        path.write_text(json.dumps(artifact, ensure_ascii=False), encoding="utf-8")
        argv.extend([f"--{name}", str(path)])
    return main(argv), output


def evaluate_artifacts(artifacts: dict[str, dict[str, Any]]) -> tuple[Any, ...]:
    results = extract_case_results([artifacts["evidence"]], artifacts["cases"])
    return evaluate_gate(
        feature_id=FEATURE, build_id=BUILD, profile="strict",
        counts=count_results_by_priority(results), defects=[], blocking_risks=[],
        feature_spec=artifacts.get("feature"), observations=artifacts.get("observations"),
        automation=artifacts["automation"], waiver_set=None, results=results,
        risk_register=artifacts["risk"],
    )


def charter(identifier: str = "CH-1") -> dict[str, Any]:
    return {
        "id": identifier, "title": "保存操作を探索する", "priority": "P2",
        "revision": "charter-rev-1", "content_hash": "sha256:charter-1",
        "oracle_revision": "oracle-rev-1",
        "scope": "保存画面", "questions": ["保存後の値が一致するか"],
        "trace_to": ["OBS-SAVE-01"],
    }


def duplicate_definition(artifacts: dict[str, dict[str, Any]], kind: str) -> None:
    cases = artifacts["cases"]
    if kind == "manual":
        duplicate = copy.deepcopy(cases["manual_cases"][0])
        duplicate["title"] = "別の入力値を保存する"
        duplicate["steps"] = ["別の値を入力して保存する"]
        cases["manual_cases"].append(duplicate)
    elif kind == "charter":
        cases["exploratory_charters"] = [charter(), charter()]
        cases["exploratory_charters"][1]["questions"] = ["再表示しても一致するか"]
    else:
        cases["exploratory_charters"] = [charter("TC-1")]


@pytest.mark.parametrize("mandatory", [True, False], ids=["required", "all-optional"])
def test_complete_inputs_allow_go(
    tmp_path: Path, artifacts: dict[str, dict[str, Any]], mandatory: bool,
) -> None:
    # 非空で全 optional の観点集合は、未提供とは異なる明示的な設計として扱う。
    artifacts["observations"]["observations"][0]["mandatory"] = mandatory
    code, output = run_cli(tmp_path, artifacts)
    assert code == 0
    gate = json.loads(output.read_text(encoding="utf-8"))
    assert gate["status"] == "go"
    assert gate["evidence_summary"]["mandatory_observation_rate"] == 100
    assert evaluate_artifacts(artifacts)[0] == "go"


@pytest.mark.parametrize("omitted", [("feature",), ("observations",), ("feature", "observations")])
def test_cli_requires_feature_and_observations_before_writing_gate(
    tmp_path: Path, artifacts: dict[str, dict[str, Any]], omitted: tuple[str, ...],
) -> None:
    code, output = run_cli(tmp_path, artifacts, omitted=omitted)
    assert code == 1
    assert not output.exists()


@pytest.mark.parametrize("missing", ["feature", "observations"])
def test_direct_evaluation_rejects_missing_required_artifact(
    artifacts: dict[str, dict[str, Any]], missing: str,
) -> None:
    artifacts.pop(missing)
    with pytest.raises(GateInputError):
        evaluate_artifacts(artifacts)


def test_empty_observations_are_not_an_explicit_optional_design(
    tmp_path: Path, artifacts: dict[str, dict[str, Any]],
) -> None:
    artifacts["observations"]["observations"] = []
    code, output = run_cli(tmp_path, artifacts)
    assert code == 1
    assert not output.exists()
    with pytest.raises(GateInputError):
        evaluate_artifacts(artifacts)


@pytest.mark.parametrize("missing", [True, False], ids=["missing-ac", "empty-ac"])
def test_direct_evaluation_requires_acceptance_criteria(
    artifacts: dict[str, dict[str, Any]], missing: bool,
) -> None:
    if missing:
        artifacts["feature"].pop("acceptance_criteria")
    else:
        artifacts["feature"]["acceptance_criteria"] = []
    with pytest.raises(GateInputError):
        evaluate_artifacts(artifacts)


@pytest.mark.parametrize("kind", ["manual", "charter", "cross-kind"])
def test_duplicate_definitions_are_input_errors_before_cli_output(
    tmp_path: Path, artifacts: dict[str, dict[str, Any]], kind: str,
) -> None:
    duplicate_definition(artifacts, kind)
    code, output = run_cli(tmp_path, artifacts)
    assert code == 1
    assert not output.exists()


@pytest.mark.parametrize("kind", ["manual", "charter", "cross-kind"])
def test_direct_extraction_rejects_duplicate_definitions(
    artifacts: dict[str, dict[str, Any]], kind: str,
) -> None:
    duplicate_definition(artifacts, kind)
    with pytest.raises(GateInputError):
        extract_case_results([artifacts["evidence"]], artifacts["cases"])


def test_distinct_case_and_charter_definitions_are_preserved(
    artifacts: dict[str, dict[str, Any]],
) -> None:
    artifacts["cases"]["exploratory_charters"] = [charter()]
    results = extract_case_results([artifacts["evidence"]], artifacts["cases"])
    assert set(results) == {"TC-1", "CH-1"}
    assert results["TC-1"]["result"] == "pass"
    assert results["CH-1"]["result"] == "untested"


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_result_buckets_are_mutually_exclusive(outcome: str) -> None:
    counts = count_results_by_priority({"TC-1": {"priority": "P0", "result": outcome}})
    assert counts["P0"][outcome] == 1
    assert counts["P0"]["total"] == 1
    assert sum(counts["P0"][name] for name in OUTCOMES) == 1
    if outcome != "skip":
        assert counts["P0"]["skip"] == 0


@pytest.mark.parametrize("outcome", ["blocked", "unknown", "untested"])
def test_cli_reports_nonpassing_evidence_without_counting_it_as_skip(
    tmp_path: Path, artifacts: dict[str, dict[str, Any]], outcome: str,
) -> None:
    if outcome == "untested":
        extra = copy.deepcopy(artifacts["cases"]["manual_cases"][0])
        extra["tc_id"] = "TC-2"
        artifacts["cases"]["manual_cases"].append(extra)
    else:
        artifacts["evidence"]["result"] = outcome
    code, output = run_cli(tmp_path, artifacts)
    assert code == 0  # 有効な未成功実績は入力エラーではなく No-Go 判定。
    gate = json.loads(output.read_text(encoding="utf-8"))
    assert gate["status"] == "no_go"
    counts = gate["evidence_summary"]["manual_by_priority"]["P0"]
    assert counts[outcome] == 1
    assert counts["skip"] == 0
    assert sum(counts[name] for name in OUTCOMES) == counts["total"]


@pytest.mark.parametrize("field", ["coverage_percent", "hotspot_review_percent"])
@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")], ids=["nan", "inf", "minus-inf"])
def test_cli_rejects_nonfinite_automation_numbers(
    tmp_path: Path, artifacts: dict[str, dict[str, Any]], field: str, number: float,
) -> None:
    artifacts["automation"][field] = number
    code, output = run_cli(tmp_path, artifacts)
    assert code == 1
    assert not output.exists()


@pytest.mark.parametrize("field", ["coverage_percent", "hotspot_review_percent"])
@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")], ids=["nan", "inf", "minus-inf"])
def test_schema_validation_rejects_nonfinite_python_numbers(
    artifacts: dict[str, dict[str, Any]], field: str, number: float,
) -> None:
    artifacts["automation"][field] = number
    with pytest.raises(GateInputError):
        validate_schema(artifacts["automation"], "automation_evidence.schema.json")


@pytest.mark.parametrize("number", [0, 100])
def test_schema_accepts_finite_percentage_boundaries(
    artifacts: dict[str, dict[str, Any]], number: int,
) -> None:
    artifacts["automation"]["coverage_percent"] = number
    artifacts["automation"]["hotspot_review_percent"] = number
    validate_schema(artifacts["automation"], "automation_evidence.schema.json")


@pytest.mark.parametrize("waive_active_failure", [False, True], ids=["no-waiver", "active-waiver"])
def test_retired_p1_does_not_require_an_additional_failure_waiver(
    artifacts: dict[str, dict[str, Any]], waive_active_failure: bool,
) -> None:
    """手動から移管したリスクは、別の P1 失敗の承認対象に混ぜない。"""
    for suffix in ("A", "B"):
        case = copy.deepcopy(artifacts["cases"]["manual_cases"][0])
        case.update(tc_id=f"TC-{suffix}", priority="P1", trace_to=[f"RISK-{suffix}"])
        if suffix == "B":
            case.update(
                status="retired", retired_reason="自動テストへ移管済み",
                replacement_refs=["hate:AETE-B"],
            )
        artifacts["cases"]["manual_cases"].append(case)
        artifacts["risk"]["risks"].append({
            "id": f"RISK-{suffix}", "scenario": f"保存経路 {suffix} の不具合",
            "impact": 4, "likelihood": 4, "priority": "P1", "trace_to": [f"TC-{suffix}"],
        })
    failure = {**artifacts["evidence"], "tc_id": "TC-A", "result": "fail"}
    results = extract_case_results([artifacts["evidence"], failure], artifacts["cases"])
    residual, blocking = assess_residual_risks(artifacts["risk"], results)
    waiver_set = None
    if waive_active_failure:
        waiver_set = {"feature_id": FEATURE, "build_id": BUILD, "waivers": [{
            "id": "WAIVER-A", "risk_ids": ["RISK-A"], "reason": "影響を限定できる",
            "owner": "qa-lead",
            "approver": "release-lead", "approved_at": "2026-09-12T12:00:00+09:00",
            "approval_ref": "DECISION-A",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "containment": "対象操作を監視する", "rollback": "対象機能を無効化する",
        }]}

    status, _, applied, unmet, observation_execution = evaluate_gate(
        feature_id=FEATURE, build_id=BUILD, profile="strict",
        counts=count_results_by_priority(results), defects=[], blocking_risks=blocking,
        residual_risks=residual, feature_spec=artifacts["feature"],
        observations=artifacts["observations"], automation=artifacts["automation"],
        waiver_set=waiver_set, results=results, risk_register=artifacts["risk"],
    )

    assert observation_execution == 100
    assert status == ("conditional_go" if waive_active_failure else "no_go")
    missing_waivers = [condition for condition in unmet if condition.startswith("waiver missing")]
    assert missing_waivers == ([] if waive_active_failure else ["waiver missing for risks: RISK-A"])
    assert [waiver["id"] for waiver in applied] == (["WAIVER-A"] if waive_active_failure else [])
