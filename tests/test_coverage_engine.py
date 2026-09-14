"""調査資料の受入条件を、小さな有限モデルと実行証跡で検証する。"""

import copy
import json
from pathlib import Path

import pytest

from bb_harness.artifact_migration import migrate_artifact
from bb_harness.cli import main
from bb_harness.coverage_engine import (
    build_coverage_report,
    build_technique_plan,
    coverage_summary,
    enumerate_coverage_obligations,
    validate_case_coverage,
)
from bb_harness.evidence_revisions import stamp_case_identity
from bb_harness.local_pipeline import (
    _merge_case_sets,
    _preserve_review_cases,
    _validate_source_grounding,
)
from bb_harness.schema_validation import SchemaValidationError, validate_artifact
from bb_harness.techniques.common import ModelError, evaluate

SOURCE = {"id": "AC-1", "kind": "ac"}
FEATURE = {"feature_id": "F", "title": "テスト対象", "acceptance_criteria": ["AC-1: テスト対象が利用できる"], "source_refs": [SOURCE], "revision": "spec-test-rev-1"}
OBS = {"feature_id": "F", "observations": []}
RISKS = {"feature_id": "F", "risks": []}


def expr(op, left, right):
    return {"op": op, "args": [left, right]}


def model(**extra):
    return {
        "feature_id": "F",
        "coverage_items": [{"id": "COV-TEST-SURFACE", "dimension": "quality", "technique": "exploratory", "applicability": "not_applicable", "mandatory": False, "coverage_criterion": "each_item", "source_refs": [SOURCE], "not_applicable_reason": "個別技法モデルのテストでは品質面を別途評価しない"}],
        "flows": [],
        "data_partitions": [],
        "rule_columns": [],
        "states": [],
        "role_matrix": [],
        "regression_edges": [],
        **extra,
    }


def domain(operator=">=", step=1, criterion="simplified_domain"):
    ops = {">=": "gte", ">": "gt", "<": "lt", "<=": "lte", "=": "eq", "!=": "neq"}
    predicate = expr(ops[operator], {"var": "x"}, {"const": 10})
    return model(
        parameters=[{"id": "x", "name": "金額", "type": "decimal", "step": step}],
        domain_models=[
            {
                "id": "D",
                "source_refs": [SOURCE],
                "variable_ids": ["x"],
                "partition_predicate": predicate,
                "borders": [
                    {
                        "id": "B",
                        "operator": operator,
                        "predicate": predicate,
                        "axis": "x",
                        "anchor": {"x": 0},
                    }
                ],
                "coverage_criterion": criterion,
            }
        ],
    )


def plan(value):
    return build_technique_plan(FEATURE, value, OBS, RISKS)


def obligations(value):
    return enumerate_coverage_obligations(value, plan(value))


def case(data=None, **extra):
    value = {
        "tc_id": "TC-1",
        "title": "境界",
        "priority": "P1",
        "primary_view": "black",
        "steps": ["指定の入力で操作する"],
        "expected_results": ["指定の条件に対応する結果が表示される"],
        "oracle": {"type": "specified", "refs": ["AC-1"]},
        "source_ref": {"type": "acceptance", "refs": ["AC-1"]},
        "trace_to": ["OBS-DATA-1"],
        "revision": "case-test-rev-1",
        "content_hash": "sha256:case-test-rev-1",
        "oracle_revision": "oracle-test-rev-1",
        "coverage_inputs": []
        if data is None
        else [{"model_ref": "D", "data": data, "step_refs": [1], "expected_result_refs": [1]}],
        **extra,
    }
    return stamp_case_identity(value)


def cases(*values):
    return {"feature_id": "F", "manual_cases": list(values), "spec_revision": "spec-test-rev-1"}


def evidence(tc_id="TC-1", result="pass", **extra):
    return {
        "run_id": "RUN-1",
        "feature_id": "F",
        "build_id": "BUILD",
        "timestamp": "2026-09-10T00:00:00Z",
        "tc_id": tc_id,
        "result": result,
        "case_revision": "case-test-rev-1",
        "spec_revision": "spec-test-rev-1",
        "oracle_revision": "oracle-test-rev-1",
        "case_content_hash": "sha256:case-test-rev-1",
        "oracle_refs": ["AC-1"],
        **extra,
    }


@pytest.mark.parametrize(
    ("operator", "expected"),
    [
        (">=", {"ON": 10, "OFF": 9}),
        (">", {"ON": 11, "OFF": 10}),
        ("<=", {"ON": 10, "OFF": 11}),
        ("<", {"ON": 9, "OFF": 10}),
        ("=", {"ON": 10, "OFF-LOW": 9, "OFF-HIGH": 11}),
        ("!=", {"OFF": 10, "ON-LOW": 9, "ON-HIGH": 11}),
    ],
)
def test_domain_open_closed_equality(operator, expected):
    actual = {
        item["selector"]["point_role"]: item["selector"]["data"]["x"]
        for item in obligations(domain(operator))
    }
    assert actual == expected


def test_precision_and_reliable_require_in_out():
    value = domain(step=0.1, criterion="reliable_domain")
    obs = obligations(value)
    assert {item["selector"]["point_role"] for item in obs} == {"ON", "OFF", "IN", "OUT"}
    assert (
        next(item for item in obs if item["selector"]["point_role"] == "OFF")["selector"]["data"][
            "x"
        ]
        == "9.9"
    )
    report = build_coverage_report(
        value, plan(value), cases(case({"x": 10}), case({"x": 9.9}, tc_id="TC-2"))
    )
    assert report["design"]["rate"] == 50
    assert len(report["design"]["uncovered_ids"]) == 2


def test_multivariable_discount_border():
    value = domain()
    value["parameters"] = [
        {"id": key, "name": key, "type": "integer", "step": 1} for key in ("P", "D")
    ]
    predicate = expr("gte", expr("sub", {"var": "P"}, {"var": "D"}), {"const": 5000})
    value["domain_models"][0].update(
        variable_ids=["P", "D"],
        partition_predicate=predicate,
        borders=[
            {
                "id": "B",
                "operator": ">=",
                "predicate": predicate,
                "axis": "D",
                "anchor": {"P": 6000, "D": 0},
            }
        ],
        constraints=[expr("lte", {"var": "D"}, {"var": "P"})],
    )
    assert [item["selector"]["data"] for item in obligations(value)] == [
        {"P": 6000, "D": 1000},
        {"P": 6000, "D": 1001},
    ]


@pytest.mark.parametrize(
    "change", ["step", "operator", "closed", "axis", "nonlinear", "anchor", "source"]
)
def test_domain_invalid_or_unknown_models_are_not_complete(change):
    value = domain()
    border = value["domain_models"][0]["borders"][0]
    if change == "step":
        del value["parameters"][0]["step"]
    elif change == "operator":
        border["operator"] = "<"
    elif change == "closed":
        border["closed"] = False
    elif change == "axis":
        border["axis"] = "missing"
    elif change == "anchor":
        border["anchor"] = {}
    elif change == "nonlinear":
        border["predicate"]["args"][0] = expr("mul", {"var": "x"}, {"var": "x"})
    else:
        value["domain_models"][0]["source_refs"] = [{"id": "MADE-UP", "kind": "ac"}]
    if change == "source":
        with pytest.raises(ModelError, match="source"):
            plan(value)
    else:
        assert plan(value)["selections"][0]["status"] == "blocked_by_missing_information"


def test_constraints_and_masking_remain_unknown():
    value = domain()
    value["domain_models"][0]["constraints"] = [expr("gte", {"var": "x"}, {"const": 10})]
    report = build_coverage_report(value, plan(value), cases(case({"x": 10})))
    assert len(report["unknown_ids"]) == 1
    assert (
        coverage_summary(report, feature_id="F", build_id="unexecuted")[
            "coverage_exit_criteria_met"
        ]
        is False
    )


def combination(criterion="pairwise"):
    return model(
        parameters=[{"id": key, "name": key, "type": "enum", "values": [0, 1]} for key in "abc"],
        combination_models=[
            {
                "id": "C",
                "source_refs": [SOURCE],
                "parameter_ids": list("abc"),
                "coverage_criterion": criterion,
                "constraints": [
                    {
                        "op": "not",
                        "args": [
                            {
                                "op": "and",
                                "args": [
                                    expr("eq", {"var": "a"}, {"const": 1}),
                                    expr("eq", {"var": "b"}, {"const": 1}),
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    )


def test_feasible_pairs_only_and_missing_tuple_id():
    value = combination()
    required = obligations(value)
    assert len(required) == 11
    assert not any(item["selector"]["data"] == {"a": 1, "b": 1} for item in required)
    report = build_coverage_report(
        value,
        plan(value),
        cases(
            case(
                coverage_inputs=[
                    {
                        "model_ref": "C",
                        "data": {"a": 0, "b": 0, "c": 0},
                        "step_refs": [1],
                        "expected_result_refs": [1],
                    }
                ]
            )
        ),
    )
    assert report["design"]["covered_by_cases"] == 3
    assert len(report["design"]["uncovered_ids"]) == 8


@pytest.mark.parametrize(("criterion", "count"), [("base_choice", 4), ("n_wise", 6), ("all", 6)])
def test_other_combination_criteria(criterion, count):
    value = combination(criterion)
    value["combination_models"][0].update(base_choice={"a": 0, "b": 0, "c": 0}, strength=3)
    assert len(obligations(value)) == count


def state(criterion="n_switch", n=1):
    return model(
        state_models=[
            {
                "id": "S",
                "source_refs": [SOURCE],
                "states": ["a", "b", "c"],
                "transitions": [
                    {"id": "AB", "from": "a", "to": "b", "event": "next", "valid": True},
                    {"id": "BC", "from": "b", "to": "c", "event": "next", "valid": True},
                    {"id": "CA", "from": "c", "to": "a", "event": "reset", "valid": True},
                    {"id": "AC", "from": "a", "to": "c", "event": "skip", "valid": False},
                ],
                "coverage_criterion": criterion,
                "n": n,
            }
        ]
    )


def state_case(path, tc_id="TC-1", initial="a", **extra):
    return case(
        tc_id=tc_id,
        coverage_inputs=[
            {
                "model_ref": "S",
                "initial_state": initial,
                "transition_ids": path,
                "step_refs": [1],
                "expected_result_refs": [1],
                **extra,
            }
        ],
    )


def test_switch_requires_contiguous_execution():
    value = state()
    independent = cases(
        state_case(["AB"]), state_case(["BC"], "TC-2", "b"), state_case(["CA"], "TC-3", "c")
    )
    assert build_coverage_report(value, plan(value), independent)["design"]["rate"] == 0
    value["state_models"][0]["n"] = 0
    assert build_coverage_report(value, plan(value), independent)["design"]["rate"] == 100
    value["state_models"][0]["coverage_criterion"] = "all_transitions"
    assert build_coverage_report(value, plan(value), independent)["design"]["rate"] == 75
    value["state_models"][0]["coverage_criterion"] = "all_states"
    assert build_coverage_report(value, plan(value), independent)["design"]["rate"] == 100


def test_roundtrip_guard_actions_and_invalid_paths():
    value = state("round_trip")
    assert len(obligations(value)) == 3
    report = build_coverage_report(value, plan(value), cases(state_case(["AB", "BC", "CA"])))
    assert report["design"]["covered_by_cases"] == 1
    assert validate_case_coverage(cases(state_case(["AB", "CA"])), value, plan(value))["errors"]
    value = state()
    value["state_models"][0]["contexts"] = [{"credit": 0}]
    transitions = value["state_models"][0]["transitions"]
    transitions[0]["actions"] = {"credit": {"const": 1}}
    transitions[1]["guard"] = expr("eq", {"var": "credit"}, {"const": 1})
    requirements = obligations(value)
    assert (
        next(item for item in requirements if item["selector"]["transition_ids"] == ["AB", "BC"])[
            "feasibility"
        ]
        == "feasible"
    )
    assert (
        next(item for item in requirements if item["selector"]["transition_ids"] == ["BC", "CA"])[
            "feasibility"
        ]
        == "infeasible"
    )


def decision():
    return model(
        parameters=[{"id": "member", "name": "member", "type": "boolean", "values": [True, False]}],
        decision_tables=[
            {
                "id": "T",
                "source_refs": [SOURCE],
                "parameter_ids": ["member"],
                "coverage_criterion": "feasible_rules",
                "rules": [
                    {"id": "Y", "conditions": {"member": [True]}, "actions": {"discount": 10}},
                    {"id": "N", "conditions": {"member": [False]}, "actions": {"discount": 0}},
                ],
            }
        ],
    )


@pytest.mark.parametrize("problem", ["conflict", "overlap", "gap", "minimized", "feasible"])
def test_decision_table_errors(problem):
    value = decision()
    table = value["decision_tables"][0]
    if problem in {"conflict", "overlap"}:
        table["rules"].append(
            {
                "id": "X",
                "conditions": {"member": [True]},
                "actions": {"discount": 20 if problem == "conflict" else 10},
            }
        )
    elif problem == "gap":
        table["rules"].pop()
    elif problem == "feasible":
        table["rules"][0]["feasible"] = False
    else:
        table["minimized_rules"] = [
            {
                "id": "M",
                "conditions": {},
                "actions": {"discount": 10},
                "represented_rule_ids": ["Y"],
            }
        ]
    assert plan(value)["selections"][0]["status"] == "blocked_by_missing_information"


def test_decision_minimization_and_result_check():
    value = decision()
    table = value["decision_tables"][0]
    table["rules"][1]["actions"] = {"discount": 10}
    table["minimized_rules"] = [
        {
            "id": "M",
            "conditions": {},
            "actions": {"discount": 10},
            "represented_rule_ids": ["Y", "N"],
        }
    ]
    assert len(obligations(value)) == 2
    input_value = {
        "model_ref": "T",
        "data": {"member": True},
        "action_checks": {"discount": 10},
        "step_refs": [1],
        "expected_result_refs": [1],
    }
    assert (
        build_coverage_report(value, plan(value), cases(case(coverage_inputs=[input_value])))[
            "design"
        ]["rate"]
        == 50
    )
    input_value["action_checks"] = {"discount": 0}
    assert (
        build_coverage_report(value, plan(value), cases(case(coverage_inputs=[input_value])))[
            "design"
        ]["rate"]
        == 0
    )
    del table["minimized_rules"]
    table["constraints"] = [expr("eq", {"var": "member"}, {"const": True})]
    assert len([item for item in obligations(value) if item["feasibility"] == "infeasible"]) == 1


def test_claims_do_not_prove_coverage_and_evidence_fail_is_executed():
    value = domain()
    required = obligations(value)
    bad = case({"x": 9}, coverage_obligation_ids=[required[0]["id"]])
    validation = validate_case_coverage(cases(bad), value, plan(value))
    assert validation["errors"] and validation["case_mapping"][required[0]["id"]] == []
    report = build_coverage_report(
        value, plan(value), cases(case({"x": 10})), [evidence(result="fail")], build_id="BUILD"
    )
    assert report["design"]["rate"] == report["execution"]["rate"] == 50
    assert report["execution"]["passed"] == 0
    blocked = build_coverage_report(
        value, plan(value), cases(case({"x": 10})), [evidence(result="blocked")], build_id="BUILD"
    )
    assert blocked["execution"]["executed"] == 0


@pytest.mark.parametrize(
    "problem",
    [
        "model_hash",
        "obligation",
        "duplicate_case",
        "step",
        "model",
        "feature",
        "evidence_feature",
        "duplicate_evidence",
        "summary_build",
    ],
)
def test_identity_and_mapping_errors(problem):
    value, case_set = domain(), cases(case({"x": 10}))
    selected = plan(value)
    if problem == "model_hash":
        selected["model_hash"] = "bad"
    elif problem == "obligation":
        selected["obligation_sets"][0]["obligations"].pop()
    elif problem == "duplicate_case":
        case_set["manual_cases"] *= 2
    elif problem == "feature":
        case_set["feature_id"] = "other"
    elif problem in {"step", "model"}:
        item = case_set["manual_cases"][0]["coverage_inputs"][0]
        item["step_refs" if problem == "step" else "model_ref"] = (
            [2] if problem == "step" else "missing"
        )
        assert validate_case_coverage(case_set, value, selected)["errors"]
        return
    if problem == "evidence_feature":
        with pytest.raises(ModelError):
            build_coverage_report(
                value, selected, case_set, [evidence(feature_id="other")], build_id="BUILD"
            )
    elif problem == "duplicate_evidence":
        with pytest.raises(ModelError):
            build_coverage_report(
                value, selected, case_set, [evidence(), evidence(run_id="RUN-2")], build_id="BUILD"
            )
    elif problem == "summary_build":
        with pytest.raises(ModelError):
            coverage_summary(
                build_coverage_report(value, selected, case_set), feature_id="F", build_id="wrong"
            )
    else:
        with pytest.raises(ModelError):
            validate_case_coverage(case_set, value, selected)


def test_same_title_and_review_keep_different_inputs():
    feature = {**FEATURE, "platforms": []}
    first, second = cases(case({"x": 10})), cases(case({"x": 9}))
    merged = _merge_case_sets(first, second, feature, OBS, RISKS)
    assert len(merged["manual_cases"]) == 2
    assert len(_merge_case_sets(first, first, feature, OBS, RISKS)["manual_cases"]) == 1
    assert len(_preserve_review_cases(merged, first, feature, OBS, RISKS)["manual_cases"]) == 2


def test_grounding_and_non_destructive_idempotent_migration():
    with pytest.raises(ValueError, match="unknown"):
        _validate_source_grounding(
            cases(case(oracle={"type": "specified", "refs": ["AC-999"]})), {"AC-1"}
        )
    legacy = model(boundaries=["金額が10を超える"])
    before = copy.deepcopy(legacy)
    migrated = migrate_artifact(legacy, "test_model")
    assert legacy == before
    assert migrated["migration"]["status"] == "needs_review"
    assert "domain_models" not in migrated
    assert migrate_artifact(migrated, "test_model") == migrated
    assert migrate_artifact(migrated, "test_model", artifact_version="legacy") == legacy
    assert build_coverage_report(legacy, plan(legacy), cases())["design"]["rate"] is None


@pytest.mark.parametrize(
    "node",
    [
        {"op": "eval", "args": [{"const": "anything"}]},
        {"var": "missing"},
        expr("div", {"const": 1}, {"const": 0}),
        {"op": "not", "args": [{"const": 1}]},
        {"op": "add", "args": []},
    ],
)
def test_restricted_expression_rejects_invalid_operations(node):
    with pytest.raises(ModelError):
        evaluate(node, {})


def test_schema_mirrors_and_legacy_examples():
    root = Path(__file__).resolve().parents[1]
    for source in (root / "schemas").glob("*.schema.json"):
        packaged = root / "src/bb_harness/schemas" / source.name
        assert json.loads(source.read_text(encoding="utf-8")) == json.loads(
            packaged.read_text(encoding="utf-8")
        )
    with pytest.raises(SchemaValidationError):
        validate_artifact({"feature_id": "F", "selections": []}, "technique_plan.schema.json")


def test_cli_coverage_and_migration(tmp_path):
    for name, value in [
        ("feature", FEATURE),
        ("model", domain()),
        ("obs", OBS),
        ("risk", RISKS),
        ("cases", cases(case({"x": 10}))),
    ]:
        (tmp_path / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    args = ["coverage"]
    for option, name in [
        ("feature", "feature"),
        ("test-model", "model"),
        ("observations", "obs"),
        ("risk", "risk"),
        ("cases", "cases"),
    ]:
        args += ["--" + option, str(tmp_path / f"{name}.json")]
    args += ["--output", str(tmp_path / "coverage")]
    assert main(args) == 0
    assert main(args) == 1
    assert (tmp_path / "coverage/coverage_report.json").exists()
    migration = [
        "migrate",
        "--input",
        str(tmp_path / "model.json"),
        "--output",
        str(tmp_path / "migrated.json"),
        "--type",
        "test_model",
    ]
    assert main(migration) == 0
    assert main(migration) == 1


@pytest.mark.parametrize("tamper", ["selection", "model", "technique", "criterion", "exits"])
def test_plan_cannot_remove_or_relabel_required_models(tamper):
    value = domain()
    selected = plan(value)
    if tamper == "selection":
        selected["selections"] = []
        selected["obligation_sets"] = []
    elif tamper == "model":
        selected["selections"][0]["model_refs"] = ["MISSING"]
    elif tamper == "technique":
        selected["selections"][0]["technique"]["key"] = "random_testing"
    elif tamper == "criterion":
        selected["selections"][0]["technique"]["criterion"] = "reliable_domain"
    else:
        selected["exit_models"] = ["D"]
    with pytest.raises((ModelError, SchemaValidationError)):
        build_coverage_report(value, selected, cases(case({"x": 10})))


def test_decimal_finite_values_and_explicit_precision():
    from bb_harness.techniques.common import configurations, typed_data

    parameters = {"x": {"type": "decimal", "values": [0.1, 0.2], "step": "0.1", "precision": 1}}
    assert len(configurations({"parameter_ids": ["x"]}, parameters)) == 2
    with pytest.raises(ModelError):
        typed_data({"x": 0.15}, {"x": {"type": "decimal", "precision": 1}})
    for step in ("0", "-0.1"):
        with pytest.raises(ModelError):
            typed_data({"x": 1}, {"x": {"type": "decimal", "step": step}})


def test_portable_schema_limits_shared_definitions_and_keeps_recursive_expressions():
    from bb_harness.local_pipeline import portable_schema

    observation_schema = portable_schema("observation_set.schema.json")
    assert "DomainModel" not in observation_schema["$defs"]["shared"]
    model_schema = portable_schema("test_model.schema.json")
    assert "ExprNode" in model_schema["$defs"]["shared"]
    assert "shared_defs.schema.json" not in json.dumps(model_schema)
