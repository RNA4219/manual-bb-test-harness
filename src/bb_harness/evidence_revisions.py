"""実行定義とモデルの版を、証跡に保存された版と照合する。"""

import copy

from bb_harness.schema_validation import validate_artifact
from bb_harness.techniques.common import ModelError, digest

COSMETIC_FIELDS = {
    "tc_id",
    "id",
    "title",
    "priority",
    "estimate_minutes",
    "trace_to",
    "techniques",
    "technique_refs",
    "case_revision",
}


def case_revision(case: dict) -> str:
    return digest({key: value for key, value in case.items() if key not in COSMETIC_FIELDS})


def model_revision(model: dict) -> str:
    return digest(
        {
            key: value
            for key, value in model.items()
            if key not in {"generation", "migration", "schema_version"}
        }
    )


def case_index(cases: dict) -> dict[str, dict]:
    items = [(case["tc_id"], case) for case in cases["manual_cases"]]
    items += [(case["id"], case) for case in cases.get("exploratory_charters", [])]
    result = dict(items)
    if len(result) != len(items):
        raise ModelError("duplicate case/charter identifiers")
    return result


def bind_case_set(cases: dict, model: dict) -> dict:
    validate_artifact(cases, "manual_case_set.schema.json")
    validate_artifact(model, "test_model.schema.json")
    if cases["feature_id"] != model["feature_id"]:
        raise ModelError("binding feature mismatch")
    result = copy.deepcopy(cases)
    result["evidence_binding"] = {"mode": "case_revision", "model_hash": model_revision(model)}
    for case in case_index(result).values():
        case["case_revision"] = case_revision(case)
    validate_artifact(result, "manual_case_set.schema.json")
    return result


def verify_case_set(cases: dict, model: dict | None = None) -> str:
    binding = cases.get("evidence_binding")
    if binding is None:
        return "legacy_unverified"
    if model is not None and binding["model_hash"] != model_revision(model):
        raise ModelError("bound cases model hash mismatch; rebind and re-execute")
    for case in case_index(cases).values():
        if case.get("case_revision") != case_revision(case):
            raise ModelError("case definition changed after binding; rebind and re-execute")
    return "case_revision"


def verify_execution_revision(evidence: dict, cases: dict) -> None:
    if "evidence_binding" not in cases:
        return
    key = evidence.get("tc_id") or evidence.get("charter_id")
    case = case_index(cases).get(key)
    if case is None:
        raise ModelError(f"execution references unknown bound case: {key}")
    if evidence.get("case_revision") != case_revision(case):
        raise ModelError(f"execution case revision missing or stale: {key}")
    if evidence.get("model_hash") != cases["evidence_binding"]["model_hash"]:
        raise ModelError(f"execution model revision missing or stale: {key}")
