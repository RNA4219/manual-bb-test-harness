"""未被覆項目に絞った入力と、全件再生成しないレビュー差分。"""

import copy
import json

from bb_harness.coverage_engine import TECHNIQUES, build_technique_plan, validate_case_coverage
from bb_harness.schema_validation import validate_artifact
from bb_harness.techniques.common import ModelError


def remaining_work(
    feature: dict, model: dict, observations: dict, risks: dict, cases: dict
) -> dict:
    plan = build_technique_plan(feature, model, observations, risks)
    validation = validate_case_coverage(cases, model, plan)
    traced = {ref for case in cases["manual_cases"] for ref in case["trace_to"]}
    return {
        "obligations": [
            item
            for item in validation["obligations"]
            if item["required"]
            and item["feasibility"] == "feasible"
            and not validation["case_mapping"][item["id"]]
        ],
        "risk_ids": [risk["id"] for risk in risks["risks"] if risk["id"] not in traced],
        "observation_ids": [
            obs["id"]
            for obs in observations["observations"]
            if obs["mandatory"] and obs["id"] not in traced
        ],
        "unresolved": validation["errors"]
        + [item["rationale"] for item in plan["selections"] if item["status"] != "selected"]
        + [
            item.get("reason", "unknown obligation")
            for item in validation["obligations"]
            if item["feasibility"] == "unknown"
        ],
    }


def compact_case_prompt(
    feature: dict, model: dict, observations: dict, risks: dict, existing: dict | None = None
) -> str:
    plan = build_technique_plan(feature, model, observations, risks)
    if existing is None:
        obligations = [item for group in plan["obligation_sets"] for item in group["obligations"]]
        pending = {
            "risk_ids": [item["id"] for item in risks["risks"]],
            "observation_ids": [item["id"] for item in observations["observations"]],
            "unresolved": [],
        }
    else:
        pending = remaining_work(feature, model, observations, risks, existing)
        obligations = pending.pop("obligations")
    risk_ids = set(pending["risk_ids"]) | {key for item in obligations for key in item["risk_ids"]}
    obs_ids = set(pending["observation_ids"]) | {
        key for item in obligations for key in item["observation_ids"]
    }
    selected_risks = [item for item in risks["risks"] if item["id"] in risk_ids]
    obs_ids.update(
        ref for item in selected_risks for ref in item.get("trace_to", []) if ref.startswith("OBS-")
    )
    selected_observations = [item for item in observations["observations"] if item["id"] in obs_ids]
    wanted = {item["model_ref"] for item in obligations}
    wanted.update(ref for item in selected_observations for ref in item.get("model_refs", []))
    # 未解決のriskやlegacyモデルは、根拠を落とさないため全モデルを保持する。
    projected = copy.deepcopy(model)
    if wanted and not pending["risk_ids"] and not pending["unresolved"]:
        for field in TECHNIQUES:
            if field in projected:
                projected[field] = [item for item in projected[field] if item["id"] in wanted]
        # 条件式・制約に間接参照されるparameterも必要なので、その定義は保持する。
    context = {
        "feature_spec": feature,
        "test_model": projected,
        "observations": selected_observations,
        "risks": selected_risks,
        "required_obligations": obligations,
        "pending": pending,
        "existing_case_index": []
        if existing is None
        else [
            {
                key: item[key]
                for key in ("tc_id", "title", "trace_to", "coverage_inputs")
                if key in item
            }
            for item in existing["manual_cases"]
        ],
    }
    return """根拠付きmanual_case_setをJSONで返してください。
required_obligationsの具体的入力・経路をcoverage_inputsへ保持し、step_refs/expected_result_refs（1始まり）を本文の手順・期待値と対応させます。
各caseに実在するsource_ref、oracle、OBS/RISKのtrace_to、観測可能なexpected_results、estimate_minutesを付けます。priorityは参照riskに合わせます。
正常・拒否・境界・二重/同時操作・部分失敗・対象platformを仕様に即して設計します。
仕様にない表示文言・HTTP status・内部実装を発明しません。
未被覆の義務とpendingを優先してください。補完では追加分だけ返し、既存caseを再出力しません。必要な追加がなければ空配列で構いません。
探索は根拠の薄いoracleに対しscope/questions/timeboxを明示し、根拠不足は残してください。
入力:\n""" + json.dumps(context, ensure_ascii=False, separators=(",", ":"))


def review_patch_prompt(
    feature: dict, model: dict, observations: dict, risks: dict, cases: dict
) -> str:
    return """case_review_patchとして修正が必要なIDとchangesだけを返してください。
修正なしならcase_updates/charter_updatesを空配列にします。
確認事項: sourceに実在するoracle/source_ref、仕様で観測可能なexpected_results、
参照riskに対応するpriority、妥当な工数。
ケースの追加・削除、ID、入力・前提・手順・経路・被覆の変更は禁止です。expectedの訂正に伴って入力変更が必要なら、このpatchで行わず元の設計を保持します。
入力:\n""" + json.dumps(
        {
            "feature_spec": feature,
            "test_model": model,
            "observations": observations,
            "risks": risks,
            "draft_manual_case_set": cases,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def apply_review_patch(cases: dict, patch: dict) -> dict:
    validate_artifact(patch, "case_review_patch.schema.json")
    result = copy.deepcopy(cases)
    for collection, updates, id_key in (
        ("manual_cases", "case_updates", "tc_id"),
        ("exploratory_charters", "charter_updates", "id"),
    ):
        targets = {item[id_key]: item for item in result.get(collection, [])}
        seen = set()
        for update in patch[updates]:
            key = update[id_key]
            if key not in targets or key in seen:
                raise ModelError(f"unknown or duplicate patch ID: {key}")
            seen.add(key)
            targets[key].update(copy.deepcopy(update["changes"]))
    validate_artifact(result, "manual_case_set.schema.json")
    return result
