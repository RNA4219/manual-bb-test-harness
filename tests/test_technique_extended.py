"""CRUD、探索資産、試行予算、移行とGateの実際の利用経路。"""

import copy
import json
from pathlib import Path

import pytest

from bb_harness.artifact_migration import migrate_artifact
from bb_harness.coverage_engine import build_coverage_report, build_technique_plan, coverage_summary
from bb_harness.gate_engine import main as gate_main
from bb_harness.local_pipeline import LocalDesignPipeline
from bb_harness.techniques.common import ModelError, indexed
from bb_harness.techniques.extended import random_samples
from tests.test_coverage_engine import (
    FEATURE,
    SOURCE,
    case,
    cases,
    domain,
    evidence,
    expr,
    model,
    obligations,
    plan,
)
from tests.test_local_pipeline import FakeClient, _feature_input, _responses


def coverage_input(model_id, **values):
    return {"model_ref": model_id, "step_refs": [1], "expected_result_refs": [1], **values}


def crud():
    return model(
        crud_models=[
            {
                "id": "CRUD",
                "source_refs": [SOURCE],
                "entity": "注文",
                "operations": [{"operation": key, "function": key.lower()} for key in "CRUD"],
                "read_paths": ["detail", "list"],
                "coverage_criterion": "consistency",
            }
        ]
    )


def test_crud_negative_read_and_every_read_path():
    value = crud()
    required = obligations(value)
    assert len(required) == 8
    negative = next(item for item in required if "initial_entity_state" in item["selector"])
    no_precondition = cases(
        case(
            coverage_inputs=[coverage_input("CRUD", sequence=[{"operation": "R", "function": "r"}])]
        )
    )
    report = build_coverage_report(value, plan(value), no_precondition)
    assert negative["id"] in report["design"]["uncovered_ids"]
    inputs = [coverage_input("CRUD", **item["selector"]) for item in required]
    inputs = [
        item for item in inputs if not any(op.get("read_path") == "list" for op in item["sequence"])
    ]
    report = build_coverage_report(value, plan(value), cases(case(coverage_inputs=inputs)))
    assert report["design"]["covered_by_cases"] == 7
    assert len(report["design"]["uncovered_ids"]) == 1
    value["crud_models"][0]["coverage_criterion"] = "completeness"
    assert len(obligations(value)) == 4
    value["crud_models"][0].update(
        coverage_criterion="consistency", operations=[{"operation": "C", "function": "create"}]
    )
    assert plan(value)["selections"][0]["status"] == "blocked_by_missing_information"


def scenario():
    return model(
        scenario_models=[
            {
                "id": "FLOW",
                "source_refs": [SOURCE],
                "coverage_criterion": "paths_and_loops",
                "paths": [
                    {"id": "MAIN", "kind": "main", "nodes": ["a", "b"]},
                    {"id": "ALT", "kind": "extension", "nodes": ["a", "c"]},
                    {
                        "id": "ERR",
                        "kind": "exception",
                        "nodes": ["a", "e"],
                        "feasible": False,
                        "reason": "このprofileでは外部障害を注入できない",
                    },
                ],
                "loops": [{"id": "RETRY", "maximum": 3}],
            }
        ]
    )


def test_scenario_loop_counts_are_distinct():
    value = scenario()
    required = obligations(value)
    assert [
        item["selector"]["loop_counts"]["RETRY"]
        for item in required
        if "loop_counts" in item["selector"]
    ] == [0, 1, 2, 3]
    report = build_coverage_report(
        value,
        plan(value),
        cases(
            case(
                coverage_inputs=[
                    coverage_input("FLOW", path_id="MAIN", nodes=["a", "b"]),
                    coverage_input("FLOW", loop_counts={"RETRY": 1}),
                ]
            )
        ),
    )
    assert report["design"]["required_feasible"] == 6
    assert report["design"]["covered_by_cases"] == 2
    assert len(report["infeasible_ids"]) == 1
    del value["scenario_models"][0]["paths"][2]["reason"]
    assert plan(value)["selections"][0]["status"] == "blocked_by_missing_information"


def checklist():
    return model(
        checklist_models=[
            {
                "id": "LIST",
                "source_refs": [SOURCE],
                "version": "2",
                "scope": "入力",
                "objective": "過去不具合の再発確認",
                "coverage_criterion": "applicable_items",
                "items": [
                    {
                        "id": "EMPTY",
                        "question": "空入力を拒否するか",
                        "applicable": True,
                        "reason": "既存不具合",
                    },
                    {
                        "id": "ROTATE",
                        "question": "回転後も値を保持するか",
                        "applicable": False,
                        "reason": "対象に回転機能がない",
                    },
                ],
            }
        ]
    )


def test_checklist_requires_correct_revision():
    value = checklist()
    wrong = cases(
        case(
            coverage_inputs=[
                coverage_input("LIST", checklist_item_ids=["EMPTY"], checklist_version="1")
            ]
        )
    )
    assert build_coverage_report(value, plan(value), wrong)["design"]["rate"] == 0
    wrong["manual_cases"][0]["coverage_inputs"][0]["checklist_version"] = "2"
    assert build_coverage_report(value, plan(value), wrong)["design"]["rate"] == 100


def random_model(count=5, policy="allow"):
    return model(
        parameters=[{"id": "x", "name": "x", "type": "integer", "values": [0, 1, 2, 3, 4]}],
        random_models=[
            {
                "id": "RANDOM",
                "source_refs": [SOURCE],
                "parameter_ids": ["x"],
                "distribution": "uniform",
                "seed": 42,
                "sample_budget": count,
                "duplicate_policy": policy,
                "oracle_refs": ["AC-1"],
                "coverage_criterion": "sample_budget",
            }
        ],
    )


def test_random_seed_and_500_vs_499_budget():
    value = random_model(500)
    random = value["random_models"][0]
    parameters = indexed(value["parameters"], "parameter")
    samples = random_samples(random, parameters)
    assert samples == random_samples(random, parameters)
    results = [
        evidence(
            run_id=f"RUN-{index}",
            timestamp=f"2026-09-10T00:{index // 60:02d}:{index % 60:02d}Z",
            model_ref="RANDOM",
            sample_id=item["sample_id"],
            observed_inputs=item["data"],
        )
        for index, item in enumerate(samples)
    ]
    report = build_coverage_report(
        value, plan(value), cases(case()), results[:-1], build_id="BUILD"
    )
    assert report["design"]["rate"] is None
    assert report["exit_criteria"] == [
        {
            "model_ref": "RANDOM",
            "metric_kind": "budget",
            "required": 500,
            "actual": 499,
            "status": "unmet",
        }
    ]
    assert (
        build_coverage_report(value, plan(value), cases(case()), results, build_id="BUILD")[
            "exit_criteria"
        ][0]["status"]
        == "met"
    )
    unique = random_model(5, "reject")
    assert (
        len(
            {
                json.dumps(item["data"])
                for item in random_samples(unique["random_models"][0], parameters)
            }
        )
        == 5
    )
    unique["random_models"][0]["sample_budget"] = 6
    assert plan(unique)["selections"][0]["status"] == "blocked_by_missing_information"


def metamorphic():
    return model(
        metamorphic_relations=[
            {
                "id": "MR",
                "source_refs": [SOURCE],
                "source_data": {"x": 1},
                "transformations": [{"x": expr("add", {"var": "x"}, {"const": 1})}],
                "expected_relation": expr("gt", {"var": "follow_up_1.y"}, {"var": "source.y"}),
                "trial_budget": 1,
                "coverage_criterion": "joint_trials",
            }
        ]
    )


def mr_evidence():
    return [
        evidence(
            run_id="SOURCE", model_ref="MR", observed_inputs={"x": 1}, observed_outputs={"y": 10}
        ),
        evidence(
            tc_id="TC-2",
            run_id="FOLLOW",
            model_ref="MR",
            observed_inputs={"x": 2},
            observed_outputs={"y": 20},
        ),
        evidence(
            run_id="JOINT",
            timestamp="2026-09-10T00:01:00Z",
            relation_evaluation={
                "relation_id": "MR",
                "group_run_id": "GROUP-1",
                "source_run_id": "SOURCE",
                "follow_up_run_ids": ["FOLLOW"],
                "observed_values": {"source.y": 10, "follow_up_1.y": 20},
                "result": "pass",
            },
        ),
    ]


def test_metamorphic_requires_joint_grounded_in_actual_outputs():
    value, case_set, executions = metamorphic(), cases(case(), case(tc_id="TC-2")), mr_evidence()
    report = build_coverage_report(value, plan(value), case_set, executions[:2], build_id="BUILD")
    assert report["exit_criteria"][0]["status"] == "unmet"
    report = build_coverage_report(value, plan(value), case_set, executions, build_id="BUILD")
    assert report["exit_criteria"][0]["status"] == "met"
    assert report["design"]["rate"] is None
    executions[-1]["relation_evaluation"]["observed_values"]["follow_up_1.y"] = 100
    assert (
        build_coverage_report(value, plan(value), case_set, executions, build_id="BUILD")[
            "exit_criteria"
        ][0]["status"]
        == "unmet"
    )


@pytest.mark.parametrize(
    "invalid", ["source", "follow", "result", "count", "run", "reuse", "expression"]
)
def test_metamorphic_rejects_unverified_trials(invalid):
    value, case_set, executions = metamorphic(), cases(case(), case(tc_id="TC-2")), mr_evidence()
    joint = executions[-1]["relation_evaluation"]
    if invalid == "source":
        executions[0]["observed_inputs"] = {"x": 2}
    elif invalid == "follow":
        executions[1]["observed_inputs"] = {"x": 3}
    elif invalid == "result":
        joint["result"] = "fail"
    elif invalid == "count":
        value["metamorphic_relations"][0]["transformations"] *= 2
    elif invalid == "run":
        joint["source_run_id"] = "MISSING"
    elif invalid == "expression":
        value["metamorphic_relations"][0]["expected_relation"] = {"var": "unknown_output"}
    else:
        value["metamorphic_relations"][0]["trial_budget"] = 2
        another = copy.deepcopy(executions[-1])
        another.update(run_id="JOINT-2", timestamp="2026-09-10T00:02:00Z")
        another["relation_evaluation"]["group_run_id"] = "GROUP-2"
        executions.append(another)
    assert (
        build_coverage_report(value, plan(value), case_set, executions, build_id="BUILD")[
            "exit_criteria"
        ][0]["status"]
        == "unmet"
    )


def test_legacy_conversions_and_unrepresentable_techniques():
    original = cases(case(techniques=["boundary_value", "state_transition"]))
    enhanced = migrate_artifact(original, "manual_case_set")
    assert enhanced["migration"]["status"] == "unmapped"
    assert [item["key"] for item in enhanced["manual_cases"][0]["technique_refs"]] == [
        "boundary_value_analysis",
        "state_transition_testing",
    ]
    legacy = migrate_artifact(enhanced, "manual_case_set", artifact_version="legacy")
    assert "coverage_inputs" not in legacy["manual_cases"][0]
    with pytest.raises(ModelError):
        migrate_artifact(plan(domain()), "technique_plan", artifact_version="legacy")
    with pytest.raises(ModelError):
        migrate_artifact(model(), "test_model", artifact_version="wrong")
    value = evidence(model_ref="RANDOM", observed_inputs={"x": 1}, observed_outputs={"y": 2})
    assert "observed_outputs" not in migrate_artifact(
        value, "execution_evidence", artifact_version="legacy"
    )


def test_local_pipeline_emits_verified_domain_report_and_provenance(tmp_path):
    from bb_harness.local_runtime import LocalRuntimeConfig

    path = tmp_path / "input.md"
    _feature_input(path)
    responses = _responses()
    structured = domain()
    responses[0].update(
        parameters=structured["parameters"], domain_models=structured["domain_models"]
    )
    for index in (3, 4, 5):
        responses[index]["manual_cases"][0]["coverage_inputs"] = [
            coverage_input("D", data={"x": 10})
        ]
        responses[index]["manual_cases"][1]["coverage_inputs"] = [
            coverage_input("D", data={"x": 9})
        ]
    config = LocalRuntimeConfig(
        generation_mode="full",
        profile="generic",
        base_url="http://127.0.0.1:1234/v1",
        model="fake",
        temperature=0.1,
        max_tokens=1000,
        timeout_seconds=10,
    )
    pipeline = LocalDesignPipeline(config, FakeClient(responses))
    manifest = pipeline.run(path, tmp_path / "out")
    report = json.loads((tmp_path / "out/coverage_report.json").read_text(encoding="utf-8"))
    assert report["design"]["rate"] == 100
    assert report["execution"]["rate"] == 0
    assert manifest["generation"]["prompt_template_version"] == "coverage-2"
    assert manifest["generation"]["review_status"] == "pending"


def test_gate_shadow_preserves_decision_and_checks_identity(tmp_path):
    root = Path(__file__).resolve().parents[1]
    examples = root / "examples/artifacts"
    case_set = json.loads(
        (examples / "order-cancel.manual_case_set.json").read_text(encoding="utf-8")
    )
    feature_id = case_set["feature_id"]
    value = domain()
    value["feature_id"] = feature_id
    feature = {**FEATURE, "feature_id": feature_id}
    selected = build_technique_plan(
        feature,
        value,
        {"feature_id": feature_id, "observations": []},
        {"feature_id": feature_id, "risks": []},
    )
    build_id = json.loads(
        (examples / "execution_evidence/CHARTER-001.json").read_text(encoding="utf-8")
    )["build_id"]
    report = build_coverage_report(value, selected, case_set, build_id=build_id)
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    args = [
        "--input",
        str(examples),
        "--build-id",
        build_id,
        "--output",
        str(tmp_path / "gate.json"),
    ]
    assert gate_main(args) == 0
    before = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert gate_main(args + ["--coverage-report", str(report_path)]) == 0
    after = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert before["status"] == after["status"]
    assert after["evidence_summary"]["required_obligation_design_rate"] == 0
    assert after["evidence_summary"]["coverage_mode"] == "shadow"
    report["case_hash"] = "stale"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    assert gate_main(args + ["--coverage-report", str(report_path)]) == 1
    assert (
        coverage_summary(
            {**report, "case_hash": "anything"}, feature_id=feature_id, build_id=build_id
        )["coverage_mode"]
        == "shadow"
    )
