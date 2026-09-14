"""旧artifactを上書きせず構造情報だけを移行する。"""

import copy

from bb_harness.coverage_engine import ALIASES, TECHNIQUES, VERSION
from bb_harness.schema_validation import validate_artifact
from bb_harness.techniques.common import ModelError

ROOT_ADDITIONS = {"schema_version", "generation", "migration", "evidence_binding"}
CASE_ADDITIONS = {
    "technique_refs",
    "coverage_obligation_ids",
    "coverage_inputs",
    "test_data",
}
CHARTER_ADDITIONS = {
    "technique_refs",
    "basis_refs",
    "mission",
    "resources",
    "entry_criteria",
    "exit_criteria",
    "environment",
    "limitations",
    "history_refs",
}
OBS_ADDITIONS = {"technique_refs", "model_refs", "coverage_obligation_ids", "basis_refs"}
EVIDENCE_ADDITIONS = {
    "model_hash",
    "coverage_obligation_ids",
    "relation_evaluation",
    "session_log",
    "model_ref",
    "sample_id",
    "observed_inputs",
    "observed_outputs",
}
GATE_ADDITIONS = {
    "evidence_binding_mode",
    "required_obligation_design_rate",
    "required_obligation_execution_rate",
    "coverage_exit_criteria_met",
    "coverage_report_id",
    "coverage_mode",
    "coverage_unknown_count",
}


def migrate_artifact(
    value: dict, artifact_type: str, *, artifact_version: str = "enhanced"
) -> dict:
    schema = f"{artifact_type}.schema.json"
    validate_artifact(value, schema)
    result = copy.deepcopy(value)
    if artifact_version == "legacy":
        if artifact_type in {"technique_plan", "coverage_report"}:
            raise ModelError("legacyには被覆artifactの表現がない")
        for key in ROOT_ADDITIONS:
            result.pop(key, None)
        if artifact_type == "test_model":
            for key in {*TECHNIQUES, "parameters", "integration_paths"}:
                result.pop(key, None)
        if artifact_type == "manual_case_set":
            for item in result["manual_cases"]:
                for key in CASE_ADDITIONS:
                    item.pop(key, None)
            for item in result.get("exploratory_charters", []):
                for key in CHARTER_ADDITIONS:
                    item.pop(key, None)
        if artifact_type == "observation_set":
            allowed = {
                "equivalence_partitioning",
                "boundary_value",
                "decision_table",
                "state_transition",
                "exploratory",
                "error_guessing",
                "use_case",
                "user_scenario",
            }
            for item in result["observations"]:
                if set(item["techniques"]) - allowed:
                    raise ModelError("新技法を旧observation enumへ損失なく変換できない")
                for key in OBS_ADDITIONS:
                    item.pop(key, None)
        if artifact_type == "execution_evidence":
            for key in EVIDENCE_ADDITIONS:
                result.pop(key, None)
        if artifact_type == "gate_decision":
            for key in GATE_ADDITIONS:
                result.get("evidence_summary", {}).pop(key, None)
        validate_artifact(result, schema)
        return result
    if artifact_version != "enhanced":
        raise ModelError("unknown artifact version")
    if result.get("schema_version") == VERSION:
        return result
    result["schema_version"] = VERSION
    references = {
        name: ("ISTQB CTAL-TA v4.0", reference) for name, reference, _ in TECHNIQUES.values()
    }
    references.update(
        {
            "equivalence_partitioning": ("ISTQB CTFL v4.0.1", "4.2.1"),
            "boundary_value_analysis": ("ISTQB CTFL v4.0.1", "4.2.2"),
            "error_guessing": ("ISTQB CTFL v4.0.1", "4.4.1"),
            "exploratory_testing": ("ISTQB CTFL v4.0.1", "4.4.2"),
        }
    )
    for item in result.get("observations", []) + result.get("manual_cases", []):
        refs = []
        for alias in item.get("techniques", []):
            key = ALIASES.get(alias, alias)
            if key in references:
                standard, reference = references[key]
                refs.append(
                    {
                        "key": key,
                        "standard": standard,
                        "reference": reference,
                        "legacy_alias": alias,
                    }
                )
        if refs:
            item["technique_refs"] = refs
    status = (
        "unmapped"
        if artifact_type == "manual_case_set"
        else "needs_review"
        if artifact_type == "test_model"
        else "migrated"
    )
    result["migration"] = {
        "status": status,
        "reason": "旧IDと本文を保持。文字列から精度・条件式・正式被覆を推測しない",
    }
    validate_artifact(result, schema)
    return result
