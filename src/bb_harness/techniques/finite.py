"""制約付き組み合わせ、状態経路、決定表の有限列挙。"""

import itertools

from .common import (
    LIMIT,
    ModelError,
    canonical,
    configurations,
    evaluate,
    holds,
    indexed,
    obligation,
    typed_data,
)


def enumerate_combinations(model: dict, parameters: dict) -> list[dict]:
    rows = configurations(model, parameters)
    ids = model["parameter_ids"]
    criterion = model["coverage_criterion"]
    if criterion == "base_choice":
        base = model.get("base_choice")
        if base not in rows:
            raise ModelError("base choice must be a complete feasible configuration")
        rows = [row for row in rows if sum(row[key] != base[key] for key in ids) <= 1]
        strength = len(ids)
    elif criterion == "all":
        strength = len(ids)
    elif criterion == "pairwise":
        strength = min(2, len(ids))
    elif criterion == "n_wise":
        strength = model.get("strength", 0)
    else:
        raise ModelError("unsupported combination criterion")
    if not 1 <= strength <= len(ids):
        raise ModelError("invalid combination strength")
    tuples = {}
    for row in rows:
        for names in itertools.combinations(ids, strength):
            values = {key: row[key] for key in names}
            tuples[canonical(values)] = values
            if len(tuples) > LIMIT:
                raise ModelError("combination obligation limit exceeded")
    return [
        obligation(model, "combinatorial_testing", {"data": value})
        for _, value in sorted(tuples.items())
    ]


def walk(model: dict, sequence: list[str], context: dict, initial: str) -> tuple[list[str], dict]:
    transitions = indexed(model["transitions"], "transition")
    states = model["states"]
    state, visited, data = initial, [initial], dict(context)
    if initial not in states:
        raise ModelError("unknown initial state")
    for index, key in enumerate(sequence):
        if key not in transitions:
            raise ModelError("unknown transition")
        transition = transitions[key]
        if transition["from"] != state or transition["to"] not in states:
            raise ModelError("non-contiguous or unknown transition state")
        if not holds([transition["guard"]] if "guard" in transition else [], data):
            raise ModelError("transition guard is false")
        if not transition["valid"]:
            if index != len(sequence) - 1:
                raise ModelError("invalid transition must end an attempted path")
            continue
        updates = {key: evaluate(expr, data) for key, expr in transition.get("actions", {}).items()}
        data.update(updates)
        state = transition["to"]
        visited.append(state)
    return visited, data


def enumerate_states(model: dict, parameters: dict) -> list[dict]:
    del parameters
    transitions = indexed(model["transitions"], "transition")
    if len(set(model["states"])) != len(model["states"]):
        raise ModelError("duplicate state IDs")
    for transition in transitions.values():
        if transition["from"] not in model["states"] or transition["to"] not in model["states"]:
            raise ModelError("transition references unknown state")
    criterion = model["coverage_criterion"]
    contexts = model.get("contexts", [{}])
    if criterion == "all_states":
        return [
            obligation(model, "state_transition_testing", {"state_id": key})
            for key in sorted(model["states"])
        ]
    if criterion in {"valid_transitions", "all_transitions"}:
        paths = [
            [key]
            for key, transition in transitions.items()
            if transition["valid"] or criterion == "all_transitions"
        ]
    elif criterion in {"n_switch", "round_trip"}:
        length = model.get("n", 0) + 1 if criterion == "n_switch" else len(model["states"])
        if length > 6:
            raise ModelError("state path length limit exceeded")
        paths, frontier = (
            [],
            [
                ([key], [item["from"], item["to"]])
                for key, item in transitions.items()
                if item["valid"]
            ],
        )
        work = 0
        while frontier:
            sequence, states = frontier.pop()
            work += 1
            if work > LIMIT:
                raise ModelError("state path enumeration limit exceeded")
            if criterion == "n_switch" and len(sequence) == length:
                paths.append(sequence)
                continue
            if criterion == "round_trip" and states[-1] == states[0]:
                paths.append(sequence)
                continue
            if len(sequence) >= length:
                continue
            for key, transition in transitions.items():
                if transition["valid"] and transition["from"] == states[-1]:
                    if criterion == "round_trip" and transition["to"] in states[1:]:
                        continue
                    frontier.append((sequence + [key], states + [transition["to"]]))
    else:
        raise ModelError("unsupported state criterion")
    result = []
    for sequence in sorted(paths):
        feasible = False
        for context in contexts:
            try:
                walk(model, sequence, context, transitions[sequence[0]]["from"])
                feasible = True
                break
            except ModelError as exc:
                if "guard is false" not in str(exc):
                    raise
        result.append(
            obligation(
                model,
                "state_transition_testing",
                {"transition_ids": sequence},
                feasibility="feasible" if feasible else "infeasible",
                reason="" if feasible else "宣言された有限contextではguardが成立しない",
            )
        )
    return result


def rule_matches(rule: dict, row: dict) -> bool:
    if set(rule["conditions"]) - set(row):
        raise ModelError("decision rule references unknown condition")
    return all(
        any(canonical(row[key]) == canonical(value) for value in values)
        for key, values in rule["conditions"].items()
    )


def enumerate_decisions(model: dict, parameters: dict) -> list[dict]:
    rows = configurations(model, parameters)
    rules = indexed(model["rules"], "rule")
    if model["coverage_criterion"] != "feasible_rules":
        raise ModelError("unsupported decision criterion")
    represented = {key: [] for key in rules}
    for rule in rules.values():
        for key, values in rule["conditions"].items():
            if key not in model["parameter_ids"] or any(
                value not in parameters[key]["values"] for value in values
            ):
                raise ModelError("decision condition outside model domain")
    for row in rows:
        matching = [rule for rule in rules.values() if rule_matches(rule, row)]
        if not matching:
            raise ModelError(f"decision completeness gap: {canonical(row)}")
        if any(rule.get("feasible") is False for rule in matching):
            raise ModelError("rule declared infeasible matches a feasible configuration")
        if len(matching) > 1:
            kind = (
                "conflict"
                if len({canonical(rule["actions"]) for rule in matching}) > 1
                else "overlap"
            )
            raise ModelError(f"decision {kind}: {canonical(row)}")
        represented[matching[0]["id"]].append(row)
    minimized = model.get("minimized_rules")
    if minimized:
        indexed(minimized, "minimized rule")
        accounted = set()
        for compact in minimized:
            ids = set(compact.get("represented_rule_ids", []))
            if not ids or ids - rules.keys() or accounted & ids:
                raise ModelError("invalid minimized rule mapping")
            if any(not represented[key] for key in ids):
                raise ModelError("minimized rule represents an infeasible original")
            expected = {canonical(row) for key in ids for row in represented[key]}
            actual = {canonical(row) for row in rows if rule_matches(compact, row)}
            if expected != actual or any(
                compact["actions"] != rules[key]["actions"] for key in ids
            ):
                raise ModelError("minimization loses feasible conditions or actions")
            accounted.update(ids)
        if accounted != {key for key, values in represented.items() if values}:
            raise ModelError("minimization completeness/checksum mismatch")
    return [
        obligation(
            model,
            "decision_table_testing",
            {"rule_id": key, "actions": rule["actions"]},
            feasibility="feasible" if represented[key] else "infeasible",
            reason="" if represented[key] else "制約下で実行可能な条件組み合わせがない",
        )
        for key, rule in sorted(rules.items())
    ]


def validate_input(model: dict, item: dict, parameters: dict) -> None:
    data = (
        typed_data(item.get("data", {}), parameters)
        if "parameter_ids" in model or "variable_ids" in model
        else item.get("data", {})
    )
    if "parameter_ids" in model:
        if set(item.get("data", {})) != set(model["parameter_ids"]):
            raise ModelError("complete parameter assignment required")
        if item["data"] not in configurations(model, parameters):
            raise ModelError("input is not a feasible configuration")
    if "variable_ids" in model and set(data) != set(model["variable_ids"]):
        raise ModelError("complete domain assignment required")
    if not holds(model.get("constraints", []), data):
        raise ModelError("case violates model constraints")
    if "transitions" in model:
        if item.get("data", {}) not in model.get("contexts", [{}]):
            raise ModelError("state input context outside declared contexts")
        walk(
            model,
            item.get("transition_ids", []),
            item.get("data", {}),
            item.get("initial_state", ""),
        )
