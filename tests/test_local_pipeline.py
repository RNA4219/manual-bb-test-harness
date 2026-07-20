"""ローカルモデルパイプラインの決定的境界テスト。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from bb_harness.local_pipeline import (
    LocalDesignPipeline,
    _link_risks_and_cases,
    build_effort_plan,
    build_risk_register,
    lint_design,
    normalize_feature_spec,
)
from bb_harness.local_runtime import CompletionResult, LocalRuntimeConfig
from bb_harness.schema_validation import validate_artifact


class FakeClient:
    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = responses
        self.calls = 0

    def discover_model(self) -> str:
        return "fake-local-model"

    def complete_json(self, **_: Any) -> CompletionResult:
        value = self.responses[self.calls]
        self.calls += 1
        return CompletionResult(
            value=value,
            elapsed_seconds=0.01,
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            model="fake-local-model",
        )


def _feature_input(path: Path) -> None:
    path.write_text(
        """# 注文取消

## Feature
pending注文を取消し、在庫を戻す。

## Acceptance Criteria
- AC-1: pending注文を取消できる。
- AC-2: shipped注文は取消できない。

## Business Rules
- BR-1: 二重取消で在庫を二重に戻さない。

## Changed Areas
- order
- inventory
""",
        encoding="utf-8",
    )


def _responses() -> list[dict[str, Any]]:
    valid_model = {
        "feature_id": "IGNORED",
        "flows": ["buyer cancellation"],
        "data_partitions": ["pending", "shipped"],
        "boundaries": ["pending/shipped"],
        "rule_columns": ["state x repeated operation"],
        "states": ["pending", "shipped", "cancelled"],
        "valid_transitions": ["pending -> cancelled"],
        "invalid_transitions": ["shipped -> cancelled", "cancelled -> cancelled"],
        "role_matrix": ["buyer x own order x cancel"],
        "regression_edges": ["inventory"],
        "quality_lenses": ["recovery"],
    }
    observations = {
        "feature_id": "IGNORED",
        "observations": [
            {
                "id": "OBS-STATE-01",
                "title": "取消可能状態と禁止状態",
                "view": "black",
                "mandatory": True,
                "techniques": ["state_transition", "boundary_value"],
                "source_refs": [{"id": "AC-1", "kind": "ac"}],
            },
            {
                "id": "OBS-RACE-02",
                "title": "二重取消の副作用",
                "view": "gray",
                "mandatory": True,
                "techniques": ["error_guessing"],
                "source_refs": [{"id": "BR-1", "kind": "rule"}],
            },
        ],
    }
    candidates = {
        "feature_id": "IGNORED",
        "risks": [
            {
                "id": f"candidate-{index}",
                "scenario": scenario,
                "impact": 4,
                "likelihood": likelihood,
                "detectability_difficulty": 1,
                "change_surface": 1,
                "externality": 1,
                "privilege": 0,
                "automation_credit": 0,
                "rationale": "状態または在庫の不整合になる",
                "observation_ids": ["OBS-STATE-01", "OBS-RACE-02"],
            }
            for index, (scenario, likelihood) in enumerate(
                [("shippedを取消できる", 4), ("在庫が戻らない", 4), ("在庫を二重に戻す", 4)],
                1,
            )
        ],
    }
    cases = {
        "feature_id": "IGNORED",
        "manual_cases": [
            {
                "tc_id": f"X-{index}",
                "title": title,
                "priority": "P1",
                "primary_view": "black",
                "steps": ["注文詳細から取消を実行する"],
                "expected_results": [expected],
                "oracle": {"type": "specified", "refs": [oracle]},
                "source_ref": {"type": "acceptance", "refs": [oracle]},
                "estimate_minutes": 10,
                "trace_to": [obs, f"RISK-{index:02d}"],
            }
            for index, (title, expected, oracle, obs) in enumerate(
                [
                    ("pending取消", "状態がcancelledと表示される", "AC-1", "OBS-STATE-01"),
                    (
                        "shipped取消禁止",
                        "取消不可メッセージが表示され状態が維持される",
                        "AC-2",
                        "OBS-STATE-01",
                    ),
                    ("二重取消", "2回目が拒否され在庫増分は1件分である", "BR-1", "OBS-RACE-02"),
                ],
                1,
            )
        ],
        "exploratory_charters": [
            {
                "id": "CHARTER-X",
                "title": "競合探索",
                "scope": "同時取消と応答喪失後の再試行",
                "questions": ["副作用は一度だけか"],
                "estimate_minutes": 30,
                "trace_to": ["OBS-RACE-02", "RISK-03"],
            }
        ],
    }
    return [
        valid_model,
        observations,
        candidates,
        cases,
        copy.deepcopy(cases),
        copy.deepcopy(cases),
    ]


def test_pipeline_writes_valid_artifacts_and_no_go_without_evidence(tmp_path: Path) -> None:
    input_path = tmp_path / "order-cancel.input.md"
    output = tmp_path / "out"
    _feature_input(input_path)
    config = LocalRuntimeConfig(
        profile="qwen36",
        base_url="http://127.0.0.1:8084/v1",
        model="fake-local-model",
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=1000,
    )
    pipeline = LocalDesignPipeline(config, client=FakeClient(_responses()))
    manifest = pipeline.run(input_path, output)

    assert manifest["status"] == "succeeded"
    assert manifest["model"] == "fake-local-model"
    assert len(manifest["stages"]) == 6
    assert "api_key" not in json.dumps(manifest)
    assert "messages" not in json.dumps(manifest)
    gate = json.loads((output / "gate_decision.json").read_text(encoding="utf-8"))
    assert gate["status"] == "no_go"
    quality = json.loads((output / "quality_report.json").read_text(encoding="utf-8"))
    assert quality["automatic_fails"] == []
    for artifact, schema in {
        "feature_spec": "feature_spec.schema.json",
        "test_model": "test_model.schema.json",
        "observation_set": "observation_set.schema.json",
        "risk_register": "risk_register.schema.json",
        "manual_case_set": "manual_case_set.schema.json",
        "effort_plan": "effort_plan.schema.json",
        "gate_decision": "gate_decision.schema.json",
        "release_brief": "release_brief.schema.json",
    }.items():
        value = json.loads((output / f"{artifact}.json").read_text(encoding="utf-8"))
        validate_artifact(value, schema)


def test_one_repair_is_recorded(tmp_path: Path) -> None:
    input_path = tmp_path / "order-cancel.input.md"
    _feature_input(input_path)
    responses = _responses()
    invalid = dict(responses[0], data_partitions=[])
    responses.insert(0, invalid)
    config = LocalRuntimeConfig(
        profile="generic",
        base_url="http://127.0.0.1:8080/v1",
        model="fake-local-model",
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=1000,
    )
    manifest = LocalDesignPipeline(config, client=FakeClient(responses)).run(
        input_path, tmp_path / "out"
    )
    assert manifest["stages"][0]["repairs"] == 1


def test_risk_and_effort_arithmetic_are_host_controlled() -> None:
    candidates = _responses()[2]
    risks = build_risk_register("F-1", candidates)
    assert risks["risks"][0]["score"] == 56.5
    assert risks["risks"][0]["priority"] == "P1"
    cases = _responses()[3]
    effort = build_effort_plan("F-1", cases)
    phase_sum = round(sum(item["estimate_hours"] for item in effort["phases"]), 2)
    assert effort["total_estimate_hours"] == round(phase_sum * 1.2, 2)


def test_markdown_intake_preserves_source_ids(tmp_path: Path) -> None:
    path = tmp_path / "order-cancel.input.md"
    _feature_input(path)
    feature = normalize_feature_spec(path)
    assert {item["id"] for item in feature["source_refs"]} >= {"AC-1", "AC-2", "BR-1"}


def test_second_invalid_artifact_fails_and_records_diagnostic(tmp_path: Path) -> None:
    input_path = tmp_path / "order-cancel.input.md"
    output = tmp_path / "out"
    _feature_input(input_path)
    invalid = dict(_responses()[0], data_partitions=[])
    client = FakeClient([invalid, copy.deepcopy(invalid)])
    config = LocalRuntimeConfig(
        profile="generic",
        base_url="http://127.0.0.1:8080/v1",
        model="fake-local-model",
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=1000,
    )
    with pytest.raises(ValueError):
        LocalDesignPipeline(config, client=client).run(input_path, output)
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["stages"] == [
        {
            "name": "test_model",
            "elapsed_seconds": 0.02,
            "repairs": 1,
            "schema_valid": False,
            "usage": {"prompt_tokens": 20, "completion_tokens": 40},
        }
    ]
    assert client.calls == 2


def test_lint_detects_oracle_trace_state_and_ownership_gaps(tmp_path: Path) -> None:
    input_path = tmp_path / "order-cancel.input.md"
    output = tmp_path / "out"
    _feature_input(input_path)
    config = LocalRuntimeConfig(
        profile="generic",
        base_url="http://127.0.0.1:8080/v1",
        model="fake-local-model",
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=1000,
    )
    LocalDesignPipeline(config, client=FakeClient(_responses())).run(input_path, output)
    values = {
        name: json.loads((output / f"{name}.json").read_text(encoding="utf-8"))
        for name in (
            "feature_spec",
            "test_model",
            "observation_set",
            "risk_register",
            "manual_case_set",
            "effort_plan",
        )
    }
    values["feature_spec"]["summary"] += " role 権限変更"
    values["test_model"]["invalid_transitions"] = []
    values["test_model"]["role_matrix"] = ["admin can change role"]
    values["manual_case_set"]["manual_cases"][0]["oracle"]["refs"] = ["UNKNOWN"]
    values["manual_case_set"]["manual_cases"][0]["trace_to"] = ["UNKNOWN"]
    lint = lint_design(
        values["feature_spec"],
        values["test_model"],
        values["observation_set"],
        values["risk_register"],
        values["manual_case_set"],
        values["effort_plan"],
    )
    assert lint["status"] == "fail"
    assert any("unknown oracle" in item for item in lint["errors"])
    assert any("observation trace missing" in item for item in lint["errors"])
    assert any("invalid transition" in item for item in lint["errors"])
    assert any("ownership context" in item for item in lint["errors"])


def test_execution_evidence_uses_existing_gate_engine(tmp_path: Path) -> None:
    input_path = tmp_path / "order-cancel.input.md"
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _feature_input(input_path)
    config = LocalRuntimeConfig(
        profile="generic",
        base_url="http://127.0.0.1:8080/v1",
        model="fake-local-model",
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=1000,
    )
    LocalDesignPipeline(config, client=FakeClient(_responses())).run(input_path, first_output)
    cases = json.loads((first_output / "manual_case_set.json").read_text(encoding="utf-8"))
    evidence_items = [("tc_id", item["tc_id"]) for item in cases["manual_cases"]] + [
        ("charter_id", item["id"]) for item in cases.get("exploratory_charters", [])
    ]
    for index, (id_field, item_id) in enumerate(evidence_items, 1):
        evidence = {
            "run_id": f"RUN-{index}",
            id_field: item_id,
            "feature_id": cases["feature_id"],
            "build_id": "build-evidence-1",
            "timestamp": "2026-07-20T00:00:00Z",
            "result": "pass",
        }
        (evidence_dir / f"{index:02d}.json").write_text(json.dumps(evidence), encoding="utf-8")
    LocalDesignPipeline(config, client=FakeClient(_responses())).run(
        input_path,
        second_output,
        evidence_path=evidence_dir,
        build_id="build-evidence-1",
    )
    gate = json.loads((second_output / "gate_decision.json").read_text(encoding="utf-8"))
    assert gate["build_id"] == "build-evidence-1"
    assert "未指定" not in " ".join(gate["reasons"])


def test_linker_preserves_optional_observation_trace() -> None:
    risks = {"risks": [{"id": "RISK-01", "priority": "P1", "trace_to": ["OBS-MANDATORY-01"]}]}
    cases = {
        "manual_cases": [
            {
                "tc_id": "TC-001",
                "priority": "P2",
                "trace_to": ["OBS-OPTIONAL-02"],
            }
        ],
        "exploratory_charters": [],
    }
    _link_risks_and_cases(risks, cases)
    assert cases["manual_cases"][0]["trace_to"] == ["OBS-OPTIONAL-02", "RISK-01"]


def test_lint_detects_missing_race_coverage(tmp_path: Path) -> None:
    input_path = tmp_path / "order-cancel.input.md"
    output = tmp_path / "out"
    _feature_input(input_path)
    config = LocalRuntimeConfig(
        profile="generic",
        base_url="http://127.0.0.1:8080/v1",
        model="fake-local-model",
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=1000,
    )
    LocalDesignPipeline(config, client=FakeClient(_responses())).run(input_path, output)
    feature = json.loads((output / "feature_spec.json").read_text(encoding="utf-8"))
    model = json.loads((output / "test_model.json").read_text(encoding="utf-8"))
    observations = json.loads((output / "observation_set.json").read_text(encoding="utf-8"))
    risks = json.loads((output / "risk_register.json").read_text(encoding="utf-8"))
    cases = json.loads((output / "manual_case_set.json").read_text(encoding="utf-8"))
    effort = json.loads((output / "effort_plan.json").read_text(encoding="utf-8"))
    for key in model:
        if isinstance(model[key], list):
            model[key] = ["通常経路"]
    for case in cases["manual_cases"]:
        case["title"] = "通常経路"
        case["steps"] = ["操作する"]
        case["expected_results"] = ["状態を観測する"]
    for charter in cases["exploratory_charters"]:
        charter["title"] = "通常経路"
        charter["scope"] = "通常経路"
        charter["questions"] = ["状態は何か"]
    lint = lint_design(feature, model, observations, risks, cases, effort)
    assert "race-sensitive feature: concurrency/retry coverage missing" in lint["errors"]
