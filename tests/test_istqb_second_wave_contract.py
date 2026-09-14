"""第二波 ISTQB レビュー反例を固定する赤テスト。

R5/R6/R7/R8/R9/R10/R19について、現行の構造だけでは失われる判断材料を
小さな反例で表現する。契約がまだ存在しない項目は、テスト内で妥当な公開
関数名を明示し、実装前の失敗を監督可能にする。
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from typing import Any

import pytest

from bb_harness import schema_validation
from bb_harness.gate_engine import (
    GATE_THRESHOLDS,
    count_results_by_priority,
    evaluate_gate,
)

FEATURE = "ISTQB-SECOND-WAVE-01"
BUILD = "build-istqb-second-wave-01"


def _base_evidence() -> dict[str, Any]:
    return {
        "run_id": "RUN-SECOND-1",
        "tc_id": "TC-001",
        "feature_id": FEATURE,
        "build_id": BUILD,
        "timestamp": "2026-09-12T12:00:00+09:00",
        "result": "pass",
    }


def _identity_evidence() -> dict[str, Any]:
    evidence = _base_evidence()
    evidence.update(
        {
            "case_revision": "case-rev-2",
            "spec_revision": "spec-rev-7",
            "oracle_revision": "oracle-rev-3",
            "case_content_hash": "sha256:case-001",
            "oracle_refs": ["AC-1"],
        }
    )
    return evidence


def test_execution_evidence_requires_testware_revision_identity() -> None:
    """build一致だけでは、どのcase/spec/oracleで実行したかを再現できない。"""
    with pytest.raises(schema_validation.SchemaValidationError, match="revision|identity|testware"):
        schema_validation.validate_artifact(
            _base_evidence(), "execution_evidence.schema.json"
        )


def test_execution_evidence_accepts_case_spec_oracle_identity() -> None:
    """case/spec/oracleの版とcase内容hashを証跡に結び付ける。"""
    schema_validation.validate_artifact(
        _identity_evidence(), "execution_evidence.schema.json"
    )


def _validate_evidence_identity() -> Callable[..., Any]:
    """R5で追加するidentity検証APIを解決する。"""
    for module_name in ("bb_harness.evidence_policy", "bb_harness.gate_engine"):
        module = importlib.import_module(module_name)
        function = getattr(module, "validate_evidence_identity", None)
        if callable(function):
            return function
    pytest.fail(
        "R5 contract API is missing: expected "
        "bb_harness.evidence_policy.validate_evidence_identity"
    )


def test_execution_evidence_rejects_case_revision_mismatch() -> None:
    """case revisionが違うpass証跡を、現行caseの実行結果へ流用しない。"""
    evidence = _identity_evidence()
    case_set = {
        "feature_id": FEATURE,
        "manual_cases": [
            {
                "tc_id": "TC-001",
                "revision": "case-rev-3",
                "content_hash": "sha256:case-001",
            }
        ],
    }
    feature_spec = {"feature_id": FEATURE, "revision": "spec-rev-7"}

    with pytest.raises(ValueError, match="revision|identity|case"):
        _validate_evidence_identity()(evidence, case_set, feature_spec)


def _valid_automation(profile: str = "standard") -> dict[str, Any]:
    return {
        "feature_id": FEATURE,
        "build_id": BUILD,
        "coverage_scope": GATE_THRESHOLDS[profile]["coverage_scope"],
        "coverage_percent": 100,
        "hotspot_review_percent": 100,
        "new_issues": {"blocker": 0, "critical": 0},
        "test_suites": [
            {
                "suite_id": "regression",
                "status": "passed",
                "total": 1,
                "passed": 1,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "source_refs": [{"id": "CI-1", "kind": "auto_test"}],
            }
        ],
        "source_refs": [{"id": "CI-1", "kind": "auto_test"}],
    }


def _evaluate(
    results: dict[str, dict[str, Any]],
    *,
    profile: str = "standard",
    feature_spec: dict[str, Any] | None = None,
    blocking_risks: list[str] | None = None,
    residual_risks: list[str] | None = None,
    waiver_set: dict[str, Any] | None = None,
    risk_register: dict[str, Any] | None = None,
) -> tuple[Any, ...]:
    return evaluate_gate(
        feature_id=FEATURE,
        build_id=BUILD,
        profile=profile,
        counts=count_results_by_priority(results),
        defects=[],
        blocking_risks=blocking_risks or [],
        feature_spec=feature_spec
        or {
            "feature_id": FEATURE,
            "acceptance_criteria": ["操作結果を確認できる"],
            "assumptions": [],
        },
        observations={
            "feature_id": FEATURE,
            "observations": [
                {
                    "id": "OBS-1",
                    "title": "外部結果",
                    "view": "black",
                    "mandatory": True,
                }
            ],
        },
        automation=_valid_automation(profile),
        waiver_set=waiver_set,
        results=results,
        residual_risks=residual_risks or [],
        risk_register=risk_register
        or {
            "feature_id": FEATURE,
            "risks": [
                {
                    "id": "RISK-P0",
                    "scenario": "critical path fails",
                    "impact": 5,
                    "likelihood": 5,
                    "priority": "P0",
                    "trace_to": ["TC-P0"],
                }
            ],
        },
    )


def test_p2_only_release_does_not_require_invented_p0_evidence() -> None:
    """計画上P0がないP2-only変更は、他の条件を満たせばGoにできる。"""
    results = {
        "TC-P2": {
            "priority": "P2",
            "result": "pass",
            "trace_to": ["OBS-1"],
        }
    }

    status, reasons, *_ = _evaluate(
        results,
        risk_register={
            "feature_id": FEATURE,
            "risks": [
                {
                    "id": "RISK-P2",
                    "scenario": "minor issue",
                    "impact": 2,
                    "likelihood": 2,
                    "priority": "P2",
                    "trace_to": ["TC-P2"],
                }
            ],
        },
    )

    assert status == "go", reasons


def _risk_score_function() -> Callable[..., Any]:
    for module_name in ("bb_harness.risk_policy", "bb_harness.gate_engine"):
        module = importlib.import_module(module_name)
        function = getattr(module, "calculate_risk_score", None)
        if callable(function):
            return function
    pytest.fail(
        "R6 contract API is missing: expected calculate_risk_score(I, L, D, C, X, P, A)"
    )


def test_risk_score_lower_bound_is_zero() -> None:
    """I=L=1かつ自動カバレッジ補正最大でも、scoreは負値にならない。"""
    score = _risk_score_function()(1, 1, 0, 0, 0, 0, 3)

    assert score == 0


def test_risk_score_upper_bound_is_one_hundred() -> None:
    """最大入力は文書化した分母124で正規化され、100を超えない。"""
    score = _risk_score_function()(5, 5, 3, 3, 3, 3, 0)

    assert score == 100


def test_checklist_based_observation_is_first_class() -> None:
    """チェックリストは探索的観点へ埋め込まず、版・項目結果を保持する。"""
    artifact = {
        "feature_id": FEATURE,
        "observations": [
            {
                "id": "OBS-CHECK-01",
                "title": "必須UIチェックリスト",
                "view": "black",
                "mandatory": True,
                "techniques": ["checklist_based"],
                "source_refs": [{"id": "AC-1", "kind": "ac", "excerpt": "UI is usable"}],
                "checklist": {
                    "id": "CHK-UI-01",
                    "revision": "v2",
                    "items": [
                        {"id": "CHK-1", "result": "pass"},
                        {"id": "CHK-2", "result": "not_applicable", "reason": "API-only"},
                    ],
                },
            }
        ],
    }

    schema_validation.validate_artifact(artifact, "observation_set.schema.json")


def test_exploratory_charter_keeps_timebox_and_session_feedback() -> None:
    """探索は質問だけでなく、timebox・メモ・発見・振り返りを記録する。"""
    artifact = {
        "feature_id": FEATURE,
        "spec_revision": "spec-rev-1",
        "manual_cases": [],
        "exploratory_charters": [
            {
                "id": "CHARTER-1",
                "revision": "charter-rev-1",
                "content_hash": "sha256:charter-1",
                "oracle_revision": "oracle-rev-1",
                "title": "再試行からの復帰を探索する",
                "scope": "network loss",
                "questions": ["二重実行にならないか"],
                "estimate_minutes": 30,
                "timebox_minutes": 30,
                "session_notes": ["offlineから再開"],
                "findings": ["再試行導線が不明瞭"],
                "retrospective": "recovery copy should be explicit",
                "trace_to": ["OBS-RECOVERY-01"],
            }
        ],
    }

    schema_validation.validate_artifact(artifact, "manual_case_set.schema.json")


def test_low_support_explicit_p0_observation_remains_mandatory() -> None:
    """3 run中1回の抽出でも、AC/P0根拠がある観点をoptionalへ落とさない。"""
    artifact = {
        "feature_id": FEATURE,
        "observations": [
            {
                "id": "OBS-SECURITY-01",
                "title": "権限外操作の拒否",
                "view": "black",
                "mandatory": True,
                "techniques": ["use_case"],
                "source_refs": [
                    {"id": "AC-P0-1", "kind": "ac", "excerpt": "must be denied"}
                ],
                "support_count": 1,
                "run_count": 3,
                "mandatory_reason": "explicit P0 acceptance criterion",
            }
        ],
    }

    schema_validation.validate_artifact(artifact, "observation_set.schema.json")
    assert artifact["observations"][0]["mandatory"] is True


def _merge_observation_runs() -> Callable[..., Any]:
    try:
        module = importlib.import_module("bb_harness.observation_policy")
    except ImportError:
        pytest.fail(
            "R8 contract API is missing: expected "
            "bb_harness.observation_policy.merge_observation_runs"
        )
    function = getattr(module, "merge_observation_runs", None)
    if not callable(function):
        pytest.fail(
            "R8 contract API is missing: expected "
            "bb_harness.observation_policy.merge_observation_runs"
        )
    return function


def test_multi_run_merge_uses_support_count_as_signal_only() -> None:
    """support_count=1/3でも、明示AC/P0観点のmandatoryを維持する。"""
    runs = [
        [
            {
                "id": "OBS-SECURITY-01",
                "title": "権限外操作の拒否",
                "view": "black",
                "mandatory": True,
                "priority": "P0",
                "source_refs": ["AC-P0-1"],
            }
        ],
        [],
        [],
    ]

    merged = _merge_observation_runs()(runs)
    observation = next(item for item in merged if item["id"] == "OBS-SECURITY-01")
    assert observation["mandatory"] is True
    assert observation["support_count"] == 1


def _test_plan() -> dict[str, Any]:
    return {
        "plan_id": "TP-1",
        "feature_id": FEATURE,
        "objective": "confirm cancellation behavior",
        "test_level": "system",
        "entry_criteria": [
            {"id": "ENTRY-1", "condition": "build is deployable", "status": "met"}
        ],
        "stop_conditions": ["critical defect found"],
        "resume_conditions": ["fix is deployed and smoke test passes"],
        "data_readiness": {"status": "ready", "notes": "canonical data exists"},
        "environment_readiness": {
            "status": "ready",
            "configuration_ids": ["WEB-CHROME"],
        },
        "estimate_basis": {
            "method": "historical",
            "source_refs": ["RUN-20260901"],
            "assumptions": ["one QA tester"],
            "uncertainty": "medium",
        },
    }


def test_test_plan_preserves_entry_stop_resume_and_estimate_basis() -> None:
    """テスト開始・停止/再開条件と見積根拠をeffortとは別に追跡できる。"""
    schema_validation.validate_artifact(_test_plan(), "test_plan.schema.json")


def test_test_plan_requires_entry_criteria() -> None:
    plan = _test_plan()
    plan["entry_criteria"] = []

    with pytest.raises(schema_validation.SchemaValidationError, match="entry"):
        schema_validation.validate_artifact(plan, "test_plan.schema.json")


def test_test_plan_is_recognized_by_artifact_validator(tmp_path) -> None:
    from bb_harness.tools.validate_artifact import detect_artifact_type, validate_artifact

    path = tmp_path / "release.test_plan.json"
    path.write_text(json.dumps(_test_plan()), encoding="utf-8")
    assert detect_artifact_type(path) == "test_plan"
    assert validate_artifact(path)["valid"] is True


def test_quality_lens_records_applicability_oracle_owner_and_feedback() -> None:
    """NFRの対象外理由・対象時oracle/ownerと、次回改善を残す。"""
    artifact = {
        "feature_id": FEATURE,
        "flows": ["cancel"],
        "data_partitions": ["valid"],
        "boundaries": ["last cancellable state"],
        "rule_columns": ["state x actor"],
        "states": ["pending", "cancelled"],
        "valid_transitions": ["pending -> cancelled"],
        "invalid_transitions": ["cancelled -> cancelled"],
        "role_matrix": ["buyer x cancel x own_order x pending"],
        "regression_edges": ["direct:order_detail"],
        "coverage_items": [
            {
                "id": "COV-QUALITY-01",
                "dimension": "quality",
                "technique": "use_case",
                "applicability": "applicable",
                "mandatory": True,
                "coverage_criterion": "each_item",
                "source_refs": [
                    {"id": "NFR-ACC-1", "kind": "spec", "excerpt": "public UI"}
                ],
            }
        ],
        "quality_lenses": [
            {
                "id": "QL-PERF-01",
                "lens": "performance",
                "applicable": False,
                "reason": "no performance requirement in this release",
                "owner": "PM",
            },
            {
                "id": "QL-ACC-01",
                "lens": "accessibility",
                "applicable": True,
                "reason": "public cancellation UI",
                "oracle": {"type": "specified", "refs": ["NFR-ACC-1"]},
                "owner": "QA",
            },
        ],
        "improvement_feedback": [
            {
                "id": "FB-1",
                "source_refs": ["BUG-1"],
                "finding": "error copy was unclear",
                "action": "update checklist and golden",
                "target_refs": ["QL-ACC-01"],
            }
        ],
    }

    schema_validation.validate_artifact(artifact, "test_model.schema.json")


def _waiver(*, with_approval: bool) -> dict[str, Any]:
    waiver: dict[str, Any] = {
        "id": "WAIVER-1",
        "risk_ids": ["RISK-P2"],
        "reason": "contained until next release",
        "owner": "QA",
        "expires_at": "2027-01-01T00:00:00+09:00",
        "containment": "monitor metric",
        "rollback": "disable feature",
    }
    if with_approval:
        waiver.update(
            {
                "approver": "Tech Lead",
                "approved_at": "2026-09-12T12:00:00+09:00",
                "approval_ref": "DECISION-1",
            }
        )
    return {"feature_id": FEATURE, "build_id": BUILD, "waivers": [waiver]}


def test_waiver_requires_approval_provenance() -> None:
    """担当者と承認者を分け、承認日時と根拠を保持する。"""
    with pytest.raises(schema_validation.SchemaValidationError, match="approv"):
        schema_validation.validate_artifact(_waiver(with_approval=False), "waiver_set.schema.json")

    schema_validation.validate_artifact(_waiver(with_approval=True), "waiver_set.schema.json")


def test_lean_profile_does_not_silently_accept_p2_residual_risk() -> None:
    """leanでも残余P2を明示受容なしにGoへしない。"""
    results = {
        "TC-P0": {"priority": "P0", "result": "pass", "trace_to": ["OBS-1"]},
        "TC-P2": {"priority": "P2", "result": "untested", "trace_to": []},
    }
    status, reasons, *_ = _evaluate(
        results,
        profile="lean",
        residual_risks=["RISK-P2: medium residual risk"],
        risk_register={
            "feature_id": FEATURE,
            "risks": [
                {
                    "id": "RISK-P0",
                    "scenario": "critical path fails",
                    "impact": 5,
                    "likelihood": 5,
                    "priority": "P0",
                    "trace_to": ["TC-P0"],
                },
                {
                    "id": "RISK-P2",
                    "scenario": "minor issue remains",
                    "impact": 2,
                    "likelihood": 2,
                    "priority": "P2",
                    "trace_to": ["TC-P2"],
                },
            ],
        },
    )

    assert status == "no_go", reasons


def test_accepted_critical_assumption_is_not_a_waiver() -> None:
    """critical assumptionはaccepted表記だけで解消済み扱いにしない。"""
    results = {
        "TC-P0": {"priority": "P0", "result": "pass", "trace_to": ["OBS-1"]}
    }
    status, reasons, *_ = _evaluate(
        results,
        feature_spec={
            "feature_id": FEATURE,
            "acceptance_criteria": ["critical assumption is resolved"],
            "assumptions": [
                {
                    "id": "ASM-1",
                    "severity": "critical",
                    "resolution_status": "accepted",
                }
            ],
        },
    )

    assert status == "no_go", reasons


def test_accepted_critical_defect_remains_blocking() -> None:
    """accepted表記だけの重大欠陥は、承認済みwaiverとして扱わない。"""
    determine = importlib.import_module("bb_harness.gate_engine").determine_gate_status
    counts = count_results_by_priority(
        {"TC-P0": {"priority": "P0", "result": "pass"}}
    )
    status, reasons, _ = determine(
        counts,
        [{"title": "critical defect", "severity": "critical", "status": "accepted"}],
        [],
    )

    assert status == "no_go"
    assert any("defect" in reason.lower() for reason in reasons)


def test_definition_identity_is_required_for_evidence_validation() -> None:
    """定義側identityが欠ける場合、任意のexecution identityを受理しない。"""
    with pytest.raises(ValueError, match="identity|revision|hash"):
        _validate_evidence_identity()(
            _identity_evidence(),
            {"feature_id": FEATURE, "manual_cases": [{"tc_id": "TC-001"}]},
            {"feature_id": FEATURE},
        )


def test_waiver_requires_independent_approver() -> None:
    """リスクowner自身の自己承認をrelease waiverとして受理しない。"""
    waiver_set = _waiver(with_approval=True)
    waiver_set["waivers"][0]["approver"] = waiver_set["waivers"][0]["owner"]
    validator = importlib.import_module("bb_harness.gate_engine").valid_waivers
    with pytest.raises(ValueError, match="approver|independent|self"):
        validator(waiver_set, FEATURE, BUILD)
