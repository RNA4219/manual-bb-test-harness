"""モデルから被覆義務を導出し、自己申告IDとは独立に設計・実施を検証する。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bb_harness.schema_validation import validate_artifact
from bb_harness.techniques.common import (
    LIMIT,
    ModelError,
    canonical,
    digest,
    evaluate,
    indexed,
)
from bb_harness.techniques.domain import enumerate_domain
from bb_harness.techniques.extended import (
    enumerate_checklist,
    enumerate_crud,
    enumerate_scenarios,
    random_samples,
)
from bb_harness.techniques.finite import (
    enumerate_combinations,
    enumerate_decisions,
    enumerate_states,
    rule_matches,
    validate_input,
    walk,
)

VERSION = "1.1.0"
GENERATOR_VERSION = "finite-coverage-1"
TECHNIQUES = {
    "domain_models": ("domain_testing", "TA-3.1.1", enumerate_domain),
    "combination_models": ("combinatorial_testing", "TA-3.1.2", enumerate_combinations),
    "state_models": ("state_transition_testing", "TA-3.2.2", enumerate_states),
    "decision_tables": ("decision_table_testing", "TA-3.3.1", enumerate_decisions),
    "crud_models": ("crud_testing", "TA-3.2.1", enumerate_crud),
    "scenario_models": ("scenario_based_testing", "TA-3.2.3", enumerate_scenarios),
    "checklist_models": ("checklist_based_testing", "TA-3.4.2", enumerate_checklist),
    "random_models": ("random_testing", "TA-3.1.3", None),
    "metamorphic_relations": ("metamorphic_testing", "TA-3.3.2", None),
}
ALIASES = {
    "boundary_value": "boundary_value_analysis",
    "decision_table": "decision_table_testing",
    "state_transition": "state_transition_testing",
    "exploratory": "exploratory_testing",
    "use_case": "scenario_based_testing",
    "user_scenario": "scenario_based_testing",
    "pairwise": "combinatorial_testing",
    "metamorphic": "metamorphic_testing",
}


def model_hash(model: dict) -> str:
    return digest(
        {
            key: value
            for key, value in model.items()
            if key not in {"generation", "migration", "schema_version"}
        }
    )


def models_by_id(model: dict) -> dict[str, dict]:
    return indexed([item for field in TECHNIQUES for item in model.get(field, [])], "model")


def _enumerate_model(model: dict, key: str, generator: Any, parameters: dict) -> list | None:
    if generator:
        obligations = generator(model, parameters)
        if len(obligations) > LIMIT:
            raise ModelError("obligation limit exceeded")
        return obligations
    if key == "random_testing":
        random_samples(model, parameters)
    else:
        for transform in model["transformations"]:
            for expr in transform.values():
                evaluate(expr, model["source_data"])
    return None


def build_technique_plan(
    feature_spec: dict, test_model: dict, observations: dict, risks: dict
) -> dict:
    validate_artifact(test_model, "test_model.schema.json")
    feature_id = feature_spec["feature_id"]
    if any(
        artifact.get("feature_id") != feature_id for artifact in (test_model, observations, risks)
    ):
        raise ModelError("technique plan feature mismatch")
    models_by_id(test_model)
    sources = indexed(feature_spec.get("source_refs", []), "source")
    observation_ids = set(indexed(observations.get("observations", []), "observation"))
    risk_ids = set(indexed(risks.get("risks", []), "risk"))
    parameters = indexed(test_model.get("parameters", []), "parameter")
    plan: dict[str, Any] = {
        "schema_version": VERSION,
        "feature_id": feature_id,
        "model_hash": model_hash(test_model),
        "generator_version": GENERATOR_VERSION,
        "selections": [],
        "obligation_sets": [],
        "exit_models": [],
    }
    for field, (key, reference, generator) in TECHNIQUES.items():
        for model in sorted(test_model.get(field, []), key=lambda value: value["id"]):
            for source in model["source_refs"]:
                if source["id"] not in sources or any(
                    sources[source["id"]].get(k) != value for k, value in source.items()
                ):
                    raise ModelError(f"unknown or altered model source: {source['id']}")
            if (
                set(model.get("observation_ids", [])) - observation_ids
                or set(model.get("risk_ids", [])) - risk_ids
            ):
                raise ModelError("model references unknown observation/risk")
            selection = {
                "id": f"TECH-{model['id']}",
                "technique": {
                    "key": key,
                    "standard": "ISTQB CTAL-TA v4.0",
                    "reference": reference,
                    "criterion": model["coverage_criterion"],
                },
                "status": "selected",
                "rationale": model.get("rationale", "根拠付きモデルに明示された基準を適用する"),
                "model_refs": [model["id"]],
                "risk_ids": model.get("risk_ids", []),
                "observation_ids": model.get("observation_ids", []),
            }
            try:
                if key == "random_testing" and set(model["oracle_refs"]) - sources.keys():
                    raise ModelError("unknown random oracle")
                obligations = _enumerate_model(model, key, generator, parameters)
                if obligations is not None:
                    plan["obligation_sets"].append(
                        {
                            "id": f"COVSET-{model['id']}",
                            "representation": "explicit",
                            "obligations": obligations,
                        }
                    )
                else:
                    plan["exit_models"].append(model["id"])
            except (ModelError, KeyError, ArithmeticError) as exc:
                selection.update(status="blocked_by_missing_information", rationale=str(exc))
            plan["selections"].append(selection)
    if not plan["selections"]:
        plan["selections"].append(
            {
                "id": "TECH-LEGACY",
                "technique": {
                    "key": "equivalence_partitioning",
                    "standard": "ISTQB CTFL v4.0.1",
                    "reference": "4.2.1",
                },
                "status": "blocked_by_missing_information",
                "rationale": "legacy_unstructured: 型付きモデルがなく形式的被覆を計算できない",
                "model_refs": [],
                "risk_ids": [],
                "observation_ids": [],
            }
        )
    validate_artifact(plan, "technique_plan.schema.json")
    return plan


def enumerate_coverage_obligations(test_model: dict, technique_plan: dict) -> list[dict]:
    validate_artifact(test_model, "test_model.schema.json")
    validate_artifact(technique_plan, "technique_plan.schema.json")
    if (
        technique_plan["feature_id"] != test_model["feature_id"]
        or technique_plan["model_hash"] != model_hash(test_model)
        or technique_plan["generator_version"] != GENERATOR_VERSION
    ):
        raise ModelError("stale technique plan or unsupported generator")
    parameters = indexed(test_model.get("parameters", []), "parameter")
    models = models_by_id(test_model)
    selections = indexed(technique_plan["selections"], "technique selection")
    if set(selections) != ({f"TECH-{key}" for key in models} or {"TECH-LEGACY"}):
        raise ModelError("plan must retain every declared model")
    expected, exits = [], []
    for field, (key, _, generator) in TECHNIQUES.items():
        for model in sorted(test_model.get(field, []), key=lambda value: value["id"]):
            selection = selections[f"TECH-{model['id']}"]
            if (
                selection["model_refs"] != [model["id"]]
                or selection["technique"]["key"] != key
                or selection["technique"].get("criterion") != model["coverage_criterion"]
            ):
                raise ModelError("plan technique/model contract mismatch")
            try:
                obligations = _enumerate_model(model, key, generator, parameters)
            except (ModelError, KeyError, ArithmeticError):
                if selection["status"] != "blocked_by_missing_information":
                    raise ModelError("unsupported model must remain blocked") from None
                continue
            if selection["status"] != "selected":
                # Source/oracle review may block a structurally valid model, but
                # callers must not turn its denominator into a successful report.
                if selection["status"] != "blocked_by_missing_information":
                    raise ModelError("model cannot be silently omitted")
                continue
            if obligations is None:
                exits.append(model["id"])
            else:
                expected.extend(obligations)
    if sorted(exits) != sorted(technique_plan["exit_models"]):
        raise ModelError("plan exit models mismatch")
    actual = [item for group in technique_plan["obligation_sets"] for item in group["obligations"]]
    if canonical(expected) != canonical(actual):
        raise ModelError("coverage obligations differ from deterministic model enumeration")
    indexed(expected, "coverage obligation")
    return expected


def _contains(sequence: list, part: list) -> bool:
    return bool(part) and any(
        sequence[start : start + len(part)] == part
        for start in range(len(sequence) - len(part) + 1)
    )


def _matches(obligation: dict, case_input: dict, model: dict) -> bool:
    selector = obligation["selector"]
    if "data" in selector:
        # Decimal文字列とJSON数値は数値型のDomainだけ同値として比較する。
        if obligation["technique_key"] == "domain_testing":
            from bb_harness.techniques.common import decimal

            return all(
                decimal(case_input.get("data", {}).get(key)) == decimal(value)
                for key, value in selector["data"].items()
            )
        return all(
            canonical(case_input.get("data", {}).get(key)) == canonical(value)
            for key, value in selector["data"].items()
        )
    if "transition_ids" in selector:
        return _contains(case_input.get("transition_ids", []), selector["transition_ids"])
    if "state_id" in selector:
        states, _ = walk(
            model,
            case_input.get("transition_ids", []),
            case_input.get("data", {}),
            case_input.get("initial_state", ""),
        )
        return selector["state_id"] in states
    if "rule_id" in selector:
        rule = indexed(model["rules"], "rule")[selector["rule_id"]]
        return (
            rule_matches(rule, case_input.get("data", {}))
            and case_input.get("action_checks") == rule["actions"]
        )
    if "sequence" in selector:
        return _contains(case_input.get("sequence", []), selector["sequence"]) and (
            "initial_entity_state" not in selector
            or case_input.get("initial_entity_state") == selector["initial_entity_state"]
        )
    if "path_id" in selector:
        return (
            case_input.get("path_id") == selector["path_id"]
            and case_input.get("nodes") == selector["nodes"]
        )
    if "loop_counts" in selector:
        return all(
            case_input.get("loop_counts", {}).get(key) == value
            for key, value in selector["loop_counts"].items()
        )
    if "checklist_item_ids" in selector:
        return case_input.get("checklist_version") == selector["version"] and set(
            selector["checklist_item_ids"]
        ) <= set(case_input.get("checklist_item_ids", []))
    return False


def validate_case_coverage(manual_case_set: dict, test_model: dict, technique_plan: dict) -> dict:
    validate_artifact(manual_case_set, "manual_case_set.schema.json")
    if manual_case_set["feature_id"] != test_model["feature_id"]:
        raise ModelError("case/model feature mismatch")
    obligations = enumerate_coverage_obligations(test_model, technique_plan)
    mapping = {item["id"]: [] for item in obligations}
    errors = []
    models = models_by_id(test_model)
    parameters = indexed(test_model.get("parameters", []), "parameter")
    cases = indexed(
        [{**case, "id": case["tc_id"]} for case in manual_case_set["manual_cases"]], "case"
    )
    for case_id, case in cases.items():
        covered = set()
        for item in case.get("coverage_inputs", []):
            try:
                if item["model_ref"] not in models:
                    raise ModelError("unknown coverage model")
                if any(index > len(case["steps"]) for index in item["step_refs"]) or any(
                    index > len(case["expected_results"]) for index in item["expected_result_refs"]
                ):
                    raise ModelError("coverage input references a missing step/expected result")
                model = models[item["model_ref"]]
                validate_input(model, item, parameters)
                for requirement in obligations:
                    if (
                        requirement["model_ref"] == model["id"]
                        and requirement["feasibility"] == "feasible"
                        and _matches(requirement, item, model)
                    ):
                        covered.add(requirement["id"])
            except (ModelError, KeyError, ArithmeticError) as exc:
                errors.append(f"{case_id}: {exc}")
        claims = set(case.get("coverage_obligation_ids", []))
        if claims - covered:
            errors.append(f"{case_id}: unverified coverage claims: {sorted(claims - covered)}")
        for key in covered:
            mapping[key].append(case_id)
    return {"case_mapping": mapping, "errors": errors, "obligations": obligations}


def _select_evidence(
    evidence: list[dict], feature_id: str, build_id: str, cases: set[str]
) -> tuple[list[dict], dict[str, dict]]:
    selected, latest, run_ids = [], {}, set()
    for raw in evidence:
        item = {key: value for key, value in raw.items() if key != "_source_path"}
        validate_artifact(item, "execution_evidence.schema.json")
        if item["feature_id"] != feature_id:
            raise ModelError("evidence feature mismatch")
        if item["build_id"] != build_id:
            continue
        if item["run_id"] in run_ids:
            raise ModelError("duplicate execution run ID")
        run_ids.add(item["run_id"])
        selected.append(item)
        case_id = item.get("tc_id")
        if case_id not in cases:
            continue
        stamp = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
        previous = latest.get(case_id)
        if previous and stamp == previous[0]:
            raise ModelError("ambiguous duplicate case evidence")
        if not previous or stamp > previous[0]:
            latest[case_id] = (stamp, item)
    return selected, {key: item for key, (_, item) in latest.items()}


def _exit_results(test_model: dict, plan: dict, cases: dict, evidence: list[dict]) -> list[dict]:
    models = models_by_id(test_model)
    parameters = indexed(test_model.get("parameters", []), "parameter")
    runs = {item["run_id"]: item for item in evidence}
    case_map = {case["tc_id"]: case for case in cases["manual_cases"]}
    result = []
    for key in plan["exit_models"]:
        model = models[key]
        completed = set()
        if "sample_budget" in model:
            samples = {
                item["sample_id"]: item["data"] for item in random_samples(model, parameters)
            }
            for item in evidence:
                sample_id = item.get("sample_id")
                if (
                    item.get("model_ref") == key
                    and item.get("tc_id") in case_map
                    and item["result"] in {"pass", "fail"}
                    and sample_id in samples
                    and item.get("observed_inputs") == samples[sample_id]
                ):
                    completed.add(sample_id)
            required, kind = model["sample_budget"], "budget"
        else:
            used_trial_runs = set()
            for item in evidence:
                joint = item.get("relation_evaluation", {})
                if joint.get("relation_id") != key or joint.get("result") not in {"pass", "fail"}:
                    continue
                ids = [joint["source_run_id"], *joint["follow_up_run_ids"]]
                if len(set(ids)) != len(ids) or any(
                    ref not in runs
                    or runs[ref]["result"] not in {"pass", "fail"}
                    or runs[ref].get("tc_id") not in case_map
                    or runs[ref].get("model_ref") != key
                    for ref in ids
                ):
                    continue
                if set(ids) & used_trial_runs:
                    continue
                if len(joint["follow_up_run_ids"]) != len(model["transformations"]):
                    continue
                source = runs[ids[0]].get("observed_inputs")
                if source != model["source_data"]:
                    continue
                valid = True
                for transform, run_id in zip(model["transformations"], ids[1:], strict=True):
                    expected = {
                        **source,
                        **{key: evaluate(expr, source) for key, expr in transform.items()},
                    }
                    if runs[run_id].get("observed_inputs") != expected:
                        valid = False
                try:
                    observed = {}
                    for index, run_id in enumerate(ids):
                        prefix = "source" if index == 0 else f"follow_up_{index}"
                        observed.update(
                            {
                                f"{prefix}.{name}": value
                                for name, value in runs[run_id].get("observed_outputs", {}).items()
                            }
                        )
                    if not observed or joint["observed_values"] != observed:
                        continue
                    relation = evaluate(model["expected_relation"], joint["observed_values"])
                    valid = (
                        valid
                        and type(relation) is bool
                        and (relation == (joint["result"] == "pass"))
                    )
                except ModelError:
                    valid = False
                if valid:
                    completed.add(joint["group_run_id"])
                    used_trial_runs.update(ids)
            required, kind = model["trial_budget"], "joint_trials"
        result.append(
            {
                "model_ref": key,
                "metric_kind": kind,
                "required": required,
                "actual": len(completed),
                "status": "met" if len(completed) >= required else "unmet",
            }
        )
    return result


def build_coverage_report(
    test_model: dict,
    technique_plan: dict,
    manual_case_set: dict,
    execution_evidence: list[dict] | None = None,
    *,
    build_id: str = "unexecuted",
) -> dict:
    """設計内容を再検証するため、obligationリスト単体での自己申告集計は許さない。"""
    from bb_harness.evidence_revisions import verify_case_set, verify_execution_revision

    binding_mode = verify_case_set(manual_case_set, test_model)
    validation = validate_case_coverage(manual_case_set, test_model, technique_plan)
    feature_id = test_model["feature_id"]
    evidence, latest = _select_evidence(
        execution_evidence or [],
        feature_id,
        build_id,
        {case["tc_id"] for case in manual_case_set["manual_cases"]},
    )
    known_ids = {item["id"] for item in validation["obligations"]}
    for item in evidence:
        verify_execution_revision(item, manual_case_set)
        if set(item.get("coverage_obligation_ids", [])) - known_ids:
            raise ModelError("evidence references unknown coverage obligations")
    rows, required, designed, executed, passed = [], [], [], [], []
    for obligation in validation["obligations"]:
        key = obligation["id"]
        mapped = validation["case_mapping"][key]
        executed_cases = [
            latest[case_id]
            for case_id in mapped
            if case_id in latest
            and latest[case_id]["result"] in {"pass", "fail"}
            and (
                "coverage_obligation_ids" not in latest[case_id]
                or key in latest[case_id]["coverage_obligation_ids"]
            )
        ]
        is_pass = bool(executed_cases) and all(item["result"] == "pass" for item in executed_cases)
        rows.append(
            {
                "id": key,
                "design": ("covered" if mapped else "uncovered")
                if obligation["feasibility"] == "feasible"
                else obligation["feasibility"],
                "case_ids": mapped,
                "executed": bool(executed_cases),
                "passed": is_pass,
            }
        )
        if obligation["required"] and obligation["feasibility"] == "feasible":
            required.append(key)
            if mapped:
                designed.append(key)
            if executed_cases:
                executed.append(key)
            if is_pass:
                passed.append(key)
    count = len(required)
    report = {
        "schema_version": VERSION,
        "id": "COVREPORT-"
        + digest([model_hash(test_model), digest(manual_case_set), build_id, evidence])[:20],
        "feature_id": feature_id,
        "build_id": build_id,
        "model_hash": model_hash(test_model),
        "case_hash": digest(manual_case_set),
        "evidence_binding_mode": binding_mode,
        "plan_hash": digest(technique_plan),
        "mode": "shadow",
        "design": {
            "required_feasible": count,
            "covered_by_cases": len(designed),
            "rate": round(len(designed) * 100 / count, 2) if count else None,
            "uncovered_ids": sorted(set(required) - set(designed)),
        },
        "execution": {
            "required_feasible": count,
            "executed": len(executed),
            "passed": len(passed),
            "rate": round(len(executed) * 100 / count, 2) if count else None,
            "unexecuted_ids": sorted(set(required) - set(executed)),
        },
        "results": rows,
        "unknown_ids": [row["id"] for row in rows if row["design"] == "unknown"],
        "infeasible_ids": [row["id"] for row in rows if row["design"] == "infeasible"],
        "errors": validation["errors"],
        "exit_criteria": _exit_results(test_model, technique_plan, manual_case_set, evidence),
        "blocked_selections": [
            selection["id"]
            for selection in technique_plan["selections"]
            if selection["status"] in {"blocked_by_missing_information", "deferred"}
        ],
    }
    validate_artifact(report, "coverage_report.schema.json")
    return report


def coverage_summary(report: dict, *, feature_id: str, build_id: str) -> dict:
    validate_artifact(report, "coverage_report.schema.json")
    if report["feature_id"] != feature_id or report["build_id"] != build_id:
        raise ModelError("coverage report feature/build mismatch")
    return {
        "required_obligation_design_rate": report["design"]["rate"],
        "required_obligation_execution_rate": report["execution"]["rate"],
        "coverage_exit_criteria_met": not report["blocked_selections"]
        and not report["unknown_ids"]
        and not report["errors"]
        and all(item["status"] == "met" for item in report["exit_criteria"]),
        "coverage_report_id": report["id"],
        "coverage_mode": "shadow",
        "coverage_unknown_count": len(report["unknown_ids"]) + len(report["blocked_selections"]),
    }
