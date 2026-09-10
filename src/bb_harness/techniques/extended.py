"""CRUD・シナリオ・経験資産と、網羅率では表さない試行予算。"""

import random

from .common import ModelError, canonical, configurations, indexed, obligation


def enumerate_crud(model: dict, parameters: dict) -> list[dict]:
    del parameters
    operations = model["operations"]
    result = [
        obligation(model, "crud_testing", {"sequence": [operation]}) for operation in operations
    ]
    if model["coverage_criterion"] == "completeness":
        return result
    if model["coverage_criterion"] != "consistency":
        raise ModelError("unsupported CRUD criterion")
    by_op = {key: [op for op in operations if op["operation"] == key] for key in "CRUD"}
    if not all(by_op.values()) or not model.get("read_paths"):
        raise ModelError("CRUD consistency requires C/R/U/D and explicit read paths")
    for read in by_op["R"]:
        result.append(
            obligation(
                model, "crud_testing", {"sequence": [read], "initial_entity_state": "absent"}
            )
        )
        for create in by_op["C"]:
            for update in by_op["U"]:
                for path in model["read_paths"]:
                    result.append(
                        obligation(
                            model,
                            "crud_testing",
                            {"sequence": [create, update, {**read, "read_path": path}]},
                        )
                    )
            for delete in by_op["D"]:
                result.append(
                    obligation(model, "crud_testing", {"sequence": [create, delete, read]})
                )
    return result


def enumerate_scenarios(model: dict, parameters: dict) -> list[dict]:
    del parameters
    indexed(model["paths"], "scenario path")
    result = []
    for path in model["paths"]:
        if path.get("feasible") is False and not path.get("reason"):
            raise ModelError("infeasible scenario requires a reason")
        result.append(
            obligation(
                model,
                "scenario_based_testing",
                {"path_id": path["id"], "nodes": path["nodes"]},
                feasibility="infeasible" if path.get("feasible") is False else "feasible",
                reason=path.get("reason", ""),
            )
        )
    indexed(model.get("loops", []), "loop")
    for loop in model.get("loops", []):
        for count in sorted({0, 1, min(2, loop["maximum"]), loop["maximum"]}):
            result.append(
                obligation(model, "scenario_based_testing", {"loop_counts": {loop["id"]: count}})
            )
    return result


def enumerate_checklist(model: dict, parameters: dict) -> list[dict]:
    del parameters
    indexed(model["items"], "checklist item")
    return [
        obligation(
            model,
            "checklist_based_testing",
            {"checklist_item_ids": [item["id"]], "version": model["version"]},
            feasibility="feasible" if item["applicable"] else "infeasible",
            reason=item["reason"],
        )
        for item in model["items"]
    ]


def random_samples(model: dict, parameters: dict) -> list[dict]:
    if model["distribution"] != "uniform":
        raise ModelError("unsupported distribution; no implicit uniform fallback")
    rows = sorted(configurations(model, parameters), key=canonical)
    count = model["sample_budget"]
    rng = random.Random(model["seed"])
    if model["duplicate_policy"] == "reject":
        if count > len(rows):
            raise ModelError("unique sample budget exceeds finite domain")
        sampled = rng.sample(rows, count)
    elif model["duplicate_policy"] == "allow":
        sampled = [rng.choice(rows) for _ in range(count)]
    else:
        raise ModelError("unknown duplicate policy")
    return [
        {"sample_id": f"{model['id']}:{index}", "data": row} for index, row in enumerate(sampled, 1)
    ]
