"""完全JSON単位の有限な分割生成。途中文字列の継ぎ足しはしない。"""

import copy
import json

from bb_harness.coverage_engine import TECHNIQUES, validate_case_coverage
from bb_harness.efficient_generation import apply_review_patch, remaining_work, review_patch_prompt
from bb_harness.schema_validation import validate_artifact
from bb_harness.techniques.common import ModelError

MAX_CASE_BATCHES = 24
BATCH_SIZE = 2
CORE_FIELDS = (
    "feature_id",
    "flows",
    "data_partitions",
    "boundaries",
    "rule_columns",
    "states",
    "valid_transitions",
    "invalid_transitions",
    "role_matrix",
    "regression_edges",
    "quality_lenses",
    "parameters",
)


def select_schema(schema: dict, properties: list | tuple) -> dict:
    """必要なpropertyと参照先のdefsだけを、再帰参照も保持して選択する。"""
    result = {
        "type": "object",
        "additionalProperties": False,
        "properties": {key: copy.deepcopy(schema["properties"][key]) for key in properties},
        "required": list(properties),
    }
    pending = []

    def visit(node):
        if isinstance(node, dict):
            if "$ref" in node:
                pending.append(node["$ref"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(result)
    seen = set()
    while pending:
        ref = pending.pop()
        if ref in seen:
            continue
        if not ref.startswith("#/$defs/"):
            raise ModelError("partition schema requires portable local references")
        seen.add(ref)
        parts = [part.replace("~1", "/").replace("~0", "~") for part in ref[2:].split("/")]
        source, target = schema, result
        for part in parts:
            source = source[part]
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = copy.deepcopy(source)
        visit(source)
    return result


def _checkpoint(pipeline, name: str, value: dict) -> None:
    from bb_harness.local_pipeline import _write_json

    pipeline.checkpoint_dir.mkdir(exist_ok=True)
    _write_json(pipeline.checkpoint_dir / f"{name}.json", value)


def model_core_request(feature: dict) -> tuple[dict, str]:
    from bb_harness.local_pipeline import (
        _test_model_prompt,
        portable_schema,
    )

    whole = portable_schema("test_model.schema.json")
    schema = select_schema(whole, CORE_FIELDS)
    for field in ("boundaries", "data_partitions", "invalid_transitions"):
        schema["properties"][field]["minItems"] = 1
    schema["properties"]["selected_techniques"] = {
        "type": "array",
        "uniqueItems": True,
        "items": {"enum": list(TECHNIQUES)},
    }
    schema["required"].append("selected_techniques")
    prompt = (
        "モデルの概要と共有parameterだけを返します。型付きモデル本文は次の呼出で生成します。\n"
        "selected_techniquesには、この仕様で根拠を持って適用する技法だけを列挙します。\n"
        "不要な技法を選択せず、不明な値を発明しません。JSONは余分な空白を省いてください。\n"
        "boundariesには数値境界と状態境界を含めます。仕様の許可状態／拒否状態の切替点も境界です。\n"
        + _test_model_prompt(feature)
    )

    return schema, prompt


def generate_model(pipeline, feature: dict) -> dict:
    from bb_harness.local_pipeline import (
        _normalize_test_model,
        _validate_test_model_semantics,
        portable_schema,
    )

    whole = portable_schema("test_model.schema.json")
    schema, prompt = model_core_request(feature)

    def validate_core(value):
        base = {key: item for key, item in value.items() if key != "selected_techniques"}
        validate_artifact(base, "test_model.schema.json")
        _validate_test_model_semantics(base, feature=None)

    core = pipeline._generate_custom(
        "test_model__core",
        schema,
        prompt,
        normalize=lambda value: _normalize_test_model(value, feature),
        semantic_validate=validate_core,
    )
    _checkpoint(pipeline, "test_model-core", core)
    selected = core.pop("selected_techniques")
    result = copy.deepcopy(core)
    for field in selected:
        part_schema = select_schema(whole, [field])
        prompt = (
            f"{field}だけを完全なJSONで返してください。他技法や概要の再出力は不要です。\n"
            "共有parameterを使い、根拠source_refsはfeature_specの実在オブジェクトを保持します。\n"
            "まだ存在しないobservation/risk IDを参照しません。\n"
            "モデルIDは技法名を含め一意にします。\n"
            "条件や精度が不明なら発明せず空配列にしてください。JSONの余分な空白は省きます。\n"
            + json.dumps({"feature_spec": feature, "model_core": core}, ensure_ascii=False)
        )
        value = pipeline._generate_custom(f"test_model__{field}", part_schema, prompt)
        result[field] = value[field]
        _checkpoint(pipeline, f"test_model-{field}", value)
    identifiers = [item["id"] for field in TECHNIQUES for item in result.get(field, [])]
    if len(set(identifiers)) != len(identifiers):
        raise ModelError("duplicate model IDs across generated partitions")
    parameter_ids = [item["id"] for item in result.get("parameters", [])]
    if len(set(parameter_ids)) != len(parameter_ids):
        raise ModelError("duplicate shared parameter IDs")
    validate_artifact(result, "test_model.schema.json")
    _validate_test_model_semantics(result, feature=None)
    return result


def pending_keys(pending: dict) -> set[str]:
    return (
        {"obligation:" + item["id"] for item in pending["obligations"]}
        | {"risk:" + key for key in pending["risk_ids"]}
        | {"observation:" + key for key in pending["observation_ids"]}
    )


def generate_cases(pipeline, feature: dict, model: dict, observations: dict, risks: dict) -> dict:
    from bb_harness.local_pipeline import (
        _merge_case_sets,
        _normalize_cases,
        _validate_source_grounding,
        portable_schema,
    )

    cases = {"feature_id": feature["feature_id"], "manual_cases": [], "exploratory_charters": []}
    schema = portable_schema("manual_case_set.schema.json")
    schema["properties"]["manual_cases"].update(minItems=0, maxItems=BATCH_SIZE)
    schema["properties"]["exploratory_charters"].update(maxItems=BATCH_SIZE)
    for number in range(MAX_CASE_BATCHES):
        pending = remaining_work(feature, model, observations, risks, cases)
        before = pending_keys(pending)
        if not before:
            break
        focused = {
            "obligations": pending["obligations"][:BATCH_SIZE],
            "risk_ids": pending["risk_ids"][:BATCH_SIZE],
            "observation_ids": pending["observation_ids"][:BATCH_SIZE],
        }
        prompt = (
            "追加ケースを最大2件、探索チャーターを最大2件、完全JSONで返します。\n"
            "focusの入力・経路をcoverage_inputsへ保持し、step_refs/expected_result_refsは1始まり。\n"
            "指定したrisk/観点の未被覆を優先し、既存ケースの再出力は不要です。\n"
            "oracle/source_refとtrace_toには実在する根拠/OBS/RISK IDだけを使います。\n"
            "仕様にない表示文言・内部実装を発明しません。期待値は具体的に観測可能にします。\n"
            "必要な追加がなければ空配列。JSONは余分な空白を省きます。\n"
            + json.dumps(
                {
                    "feature_spec": feature,
                    "test_model": model,
                    "observations": observations,
                    "risks": risks,
                    "focus": focused,
                    "existing": [
                        {"tc_id": c["tc_id"], "title": c["title"], "trace_to": c["trace_to"]}
                        for c in cases["manual_cases"]
                    ],
                },
                ensure_ascii=False,
            )
        )

        def validate(value):
            validate_artifact(value, "manual_case_set.schema.json")
            _validate_source_grounding(value, pipeline.source_ids)
            checked = validate_case_coverage(value, model, pipeline.technique_plan)
            if checked["errors"]:
                raise ModelError("; ".join(checked["errors"][:5]))

        batch = pipeline._generate_custom(
            f"manual_case_set__{number + 1}",
            schema,
            prompt,
            normalize=lambda value: _normalize_cases(value, feature, observations, risks),
            semantic_validate=validate,
        )
        cases = _merge_case_sets(cases, batch, feature, observations, risks)
        _checkpoint(pipeline, f"cases-{number + 1:02d}", cases)
        after = pending_keys(remaining_work(feature, model, observations, risks, cases))
        if not before - after:
            break
    return cases


def review_cases(
    pipeline, feature: dict, model: dict, observations: dict, risks: dict, cases: dict
) -> dict:
    from bb_harness.local_pipeline import _validate_source_grounding, portable_schema

    result = copy.deepcopy(cases)
    size = max(len(cases["manual_cases"]), len(cases.get("exploratory_charters", [])))
    for offset in range(0, size, BATCH_SIZE):
        subset = {
            "feature_id": feature["feature_id"],
            "manual_cases": result["manual_cases"][offset : offset + BATCH_SIZE],
            "exploratory_charters": result.get("exploratory_charters", [])[
                offset : offset + BATCH_SIZE
            ],
        }

        def validate(patch, subset=subset, result=result):
            apply_review_patch(subset, patch)  # 対象外IDもここで拒否する。
            updated = apply_review_patch(result, patch)
            _validate_source_grounding(updated, pipeline.source_ids)
            checked = validate_case_coverage(updated, model, pipeline.technique_plan)
            if checked["errors"]:
                raise ModelError("; ".join(checked["errors"][:5]))

        patch = pipeline._generate_custom(
            f"manual_case_review__{offset // BATCH_SIZE + 1}",
            portable_schema("case_review_patch.schema.json"),
            review_patch_prompt(feature, model, observations, risks, subset),
            semantic_validate=validate,
        )
        result = apply_review_patch(result, patch)
        _checkpoint(pipeline, f"review-{offset // BATCH_SIZE + 1:02d}", patch)
    return result


def design_status(lint: dict, coverage: dict) -> str:
    if lint["errors"] or coverage["errors"]:
        return "blocked"
    if (
        coverage["blocked_selections"]
        or coverage["unknown_ids"]
        or coverage["design"]["uncovered_ids"]
        or coverage["design"]["rate"] is None
    ):
        return "degraded"
    return "ready"
