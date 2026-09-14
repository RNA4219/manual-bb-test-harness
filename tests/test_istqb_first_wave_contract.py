"""第一波 ISTQB レビュー反例を固定する赤テスト。

このファイルは R14/R15/R17/R23 の契約を、既存実装の都合ではなく
レビューで確認した反例から表現する。実装側の変更に合わせて既存テストを
弱めることはせず、ここで期待する意味を保持する。
"""

from __future__ import annotations

from typing import Any

import pytest

from bb_harness import schema_validation
from bb_harness.gate_engine import (
    GATE_THRESHOLDS,
    count_results_by_priority,
    evaluate_gate,
    extract_case_results,
)
from bb_harness.tools.export_testrail import convert_to_testrail
from bb_harness.tools.export_xray import convert_to_xray
from bb_harness.tools.import_testrail import convert_to_execution_evidence as import_testrail_case
from bb_harness.tools.import_xray import convert_to_execution_evidence as import_xray_case

FEATURE = "ISTQB-FIRST-WAVE-01"
BUILD = "build-istqb-first-wave-01"


def _case_set() -> dict[str, Any]:
    return {
        "feature_id": FEATURE,
        "manual_cases": [
            {
                "tc_id": "TC-042",
                "title": "注文を確定する",
                "priority": "P1",
                "primary_view": "black",
                "steps": ["詳細を開く", "確定を選ぶ", "確定を実行する"],
                "expected_results": ["注文が確定済みになる"],
                "trace_to": ["OBS-ORDER-01"],
            }
        ],
        "exploratory_charters": [
            {
                "id": "CHARTER-007",
                "title": "確定失敗からの復帰を探索する",
                "scope": "network loss during confirmation",
                "questions": ["再試行で二重確定にならないか"],
                "trace_to": ["OBS-RECOVERY-01"],
            }
        ],
    }


def test_testrail_export_preserves_original_case_id() -> None:
    """列挙順の外部IDではなく、元のTC-042を輸出に保持する。"""
    exported = convert_to_testrail(_case_set())

    assert exported["cases"][0]["source_case_id"] == "TC-042"


def test_xray_export_preserves_case_and_charter_ids() -> None:
    """Xrayのmanual/exploratory双方で元IDを追跡できる。"""
    exported = convert_to_xray(_case_set())

    manual, charter = exported["tests"]
    assert manual["source_case_id"] == "TC-042"
    assert charter["source_charter_id"] == "CHARTER-007"


def test_testrail_import_prefers_explicit_original_case_id() -> None:
    """外部case_idが7でも、明示された元ID TC-042を結果へ戻す。"""
    evidence = import_testrail_case(
        {
            "id": 1,
            "case_id": 7,
            "source_case_id": "TC-042",
            "status_id": 1,
        },
        {},
        "qa",
        1234,
        require_original_mapping=True,
    )

    assert evidence["tc_id"] == "TC-042"


def test_xray_import_prefers_explicit_original_case_id() -> None:
    """Xrayのtest keyが変わっても、輸出時の元case IDを優先する。"""
    evidence = import_xray_case(
        {
            "status": "PASS",
            "source_case_id": "TC-042",
            "executedBy": "qa",
        },
        "PROJ-TE-99",
        "PROJ-TEST-7",
        FEATURE,
        require_original_mapping=True,
    )

    assert evidence["tc_id"] == "TC-042"


def test_import_without_original_mapping_does_not_synthesize_case_id() -> None:
    """元IDまたは一意な対応表がない結果をTC-007へ誤割当しない。"""
    with pytest.raises(ValueError, match="original|mapping|case"):
        import_testrail_case(
            {"id": 1, "case_id": 7, "status_id": 1},
            {},
            "qa",
            1234,
            require_original_mapping=True,
        )


def test_import_with_ambiguous_original_mapping_is_rejected() -> None:
    """複数の元ID候補を勝手に選ばず、割当を拒否する。"""
    with pytest.raises(ValueError, match="ambiguous|mapping|original"):
        import_testrail_case(
            {
                "id": 1,
                "case_id": 7,
                "source_case_ids": ["TC-042", "TC-043"],
                "status_id": 1,
            },
            {},
            "qa",
            1234,
            require_original_mapping=True,
        )


def _gate_inputs(view: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """primary_viewだけを変えた最小のP0受入入力を作る。"""
    cases = {
        "feature_id": FEATURE,
        "manual_cases": [
            {
                "tc_id": "TC-P0",
                "title": "権限外の確定を拒否する",
                "priority": "P0",
                "primary_view": view,
                "steps": ["確定操作を行う"],
                "expected_results": ["拒否される"],
                "trace_to": ["OBS-BLACK-01", "RISK-P0"],
            }
        ],
    }
    results = extract_case_results(
        [
            {
                "run_id": "RUN-P0",
                "tc_id": "TC-P0",
                "feature_id": FEATURE,
                "build_id": BUILD,
                "timestamp": "2026-09-12T12:00:00+09:00",
                "result": "pass",
            }
        ],
        cases,
    )
    return cases, results


def _evaluate_view(view: str) -> str:
    cases, results = _gate_inputs(view)
    # 実行結果へケースの観測面が伝播すること自体も契約の一部。
    results["TC-P0"]["primary_view"] = cases["manual_cases"][0]["primary_view"]
    status, _reasons, _waivers, _unmet, _rate = evaluate_gate(
        feature_id=FEATURE,
        build_id=BUILD,
        profile="standard",
        counts=count_results_by_priority(results),
        defects=[],
        blocking_risks=[],
        feature_spec={
            "feature_id": FEATURE,
            "acceptance_criteria": ["権限外の確定は拒否される"],
            "assumptions": [],
        },
        observations={
            "feature_id": FEATURE,
            "observations": [
                {
                    "id": "OBS-BLACK-01",
                    "title": "外部受入面で拒否を確認する",
                    "view": "black",
                    "mandatory": True,
                }
            ],
        },
        automation={
            "feature_id": FEATURE,
            "build_id": BUILD,
            "coverage_scope": GATE_THRESHOLDS["standard"]["coverage_scope"],
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
        },
        waiver_set=None,
        results=results,
        risk_register={
            "feature_id": FEATURE,
            "risks": [
                {
                    "id": "RISK-P0",
                    "scenario": "権限外の確定を許す",
                    "impact": 5,
                    "likelihood": 5,
                    "priority": "P0",
                    "trace_to": ["TC-P0"],
                }
            ],
        },
    )
    return status


def test_white_or_gray_pass_does_not_satisfy_black_primary_acceptance() -> None:
    """white/grayのpassだけではblackの必須受入を完了扱いにしない。"""
    assert _evaluate_view("white") == "no_go"


def test_black_case_pass_satisfies_black_primary_acceptance() -> None:
    """black観測面のP0 passは主受入の証跡として扱う。"""
    assert _evaluate_view("black") == "go"


def _phase_contract() -> dict[str, Any]:
    return {
        "contract_id": "PHASE-1",
        "feature_id": FEATURE,
        "readiness": {
            "status": "blocked",
            "decision": "not_ready",
            "reasons": ["critical question remains"],
            "required_before_dev": ["resolve question"],
        },
        "problem_owner": {"persona": "buyer", "problem": "cancel order"},
        "success_conditions": [
            {"id": "SC-1", "text": "cancel succeeds", "source_refs": ["MEMO-1"]}
        ],
        "phase1_scope": ["cancel"],
        "phase1_non_goals": ["refund admin"],
        "open_questions": [],
        "spec_gaps": [],
        "technical_risks": [],
        "metrics": ["cancel success rate"],
        "test_lenses": [
            {
                "id": "TL-1",
                "lens": "state",
                "title": "state",
                "rationale": "state changes",
                "trace_to": ["SC-1"],
            }
        ],
        "source_refs": [
            {"id": "MEMO-1", "kind": "memo", "excerpt": "cancel"}
        ],
    }


def _assert_phase_contract_rejected(artifact: dict[str, Any]) -> None:
    with pytest.raises(schema_validation.SchemaValidationError, match="readiness|owner|critical"):
        schema_validation.validate_artifact(artifact, "phase_contract.schema.json")


def test_phase_blocked_cannot_claim_ready() -> None:
    artifact = _phase_contract()
    artifact["readiness"]["decision"] = "ready"

    _assert_phase_contract_rejected(artifact)


def test_phase_unresolved_critical_question_blocks_ready() -> None:
    artifact = _phase_contract()
    artifact["readiness"] = {
        "status": "ok",
        "decision": "ready",
        "reasons": [],
        "required_before_dev": [],
    }
    artifact["open_questions"] = [
        {
            "id": "Q-CRITICAL",
            "severity": "critical",
            "question": "返金責務はどこか",
            "owner": "PM",
            "blocks_ready": True,
        }
    ]

    _assert_phase_contract_rejected(artifact)


def test_phase_open_question_requires_nonempty_owner() -> None:
    artifact = _phase_contract()
    artifact["readiness"] = {
        "status": "degraded",
        "decision": "ready_with_conditions",
        "reasons": ["owner missing"],
        "required_before_dev": ["assign owner"],
    }
    artifact["open_questions"] = [
        {
            "id": "Q-1",
            "severity": "medium",
            "question": "Who confirms the copy?",
            "owner": "",
            "blocks_ready": False,
        }
    ]

    _assert_phase_contract_rejected(artifact)
