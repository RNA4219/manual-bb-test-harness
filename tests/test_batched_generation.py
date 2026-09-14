"""分割生成の統合、有限停止、保存、終了理由と設計状態を確認する。"""

import copy
import json
from dataclasses import replace

import pytest

from bb_harness.batched_generation import (
    design_status,
    generate_cases,
    generate_risks,
    select_schema,
)
from bb_harness.cli import main
from bb_harness.efficiency_benchmark import compare_runs, summarize_run
from bb_harness.local_pipeline import LocalDesignPipeline, normalize_feature_spec, portable_schema
from bb_harness.local_runtime import LocalRuntimeError, OpenAICompatibleClient, resolve_config
from bb_harness.schema_validation import SchemaValidationError, validate_artifact
from bb_harness.techniques.common import ModelError
from bb_harness.token_budget import TokenBudgetExceeded, output_limit
from tests.test_coverage_engine import FEATURE, OBS, RISKS, domain, plan
from tests.test_local_pipeline import FakeClient, _feature_input, _responses


def batched_responses():
    original = _responses()
    typed = domain()
    core = {
        **original[0],
        "parameters": typed["parameters"],
        "selected_techniques": ["domain_models"],
    }
    first = copy.deepcopy(original[3])
    first["manual_cases"] = first["manual_cases"][:2]
    for item, x in zip(first["manual_cases"], [10, 9], strict=True):
        item["coverage_inputs"] = [
            {"model_ref": "D", "data": {"x": x}, "step_refs": [1], "expected_result_refs": [1]}
        ]
    last = {
        **copy.deepcopy(original[3]),
        "manual_cases": [copy.deepcopy(original[3]["manual_cases"][2])],
        "exploratory_charters": [],
    }
    empty_patch = {"case_updates": [], "charter_updates": []}
    return [
        core,
        {"domain_models": typed["domain_models"]},
        original[1],
        original[2],
        first,
        last,
        empty_patch,
        empty_patch,
    ]


def risk_partitions(tmp_path):
    source = _responses()
    observations = {
        "observations": [
            {**source[1]["observations"][0], "id": f"OBS-TEST-{i:02d}"} for i in range(6)
        ]
    }
    responses = [
        {
            "risks": [
                {
                    **source[2]["risks"][0],
                    "observation_ids": [
                        item["id"] for item in observations["observations"][offset : offset + 4]
                    ],
                }
            ]
        }
        for offset in (0, 4)
    ]
    pipeline = LocalDesignPipeline(
        resolve_config("generic", model="fake", generation_mode="batched"), FakeClient(responses)
    )
    pipeline.checkpoint_dir = tmp_path / "checkpoints"
    return pipeline, observations, responses


def test_risk_partitions_cover_every_required_observation_with_unique_ids(tmp_path):
    pipeline, observations, responses = risk_partitions(tmp_path)
    # Low impact observations must not be inflated to P1 in every partition.
    responses[1]["risks"][0].update(impact=1, likelihood=1)
    result = generate_risks(pipeline, FEATURE, {}, observations)
    assert [item["id"] for item in result["risks"]] == ["candidate-1", "candidate-2"]
    assert {ref for item in result["risks"] for ref in item["observation_ids"]} == {
        item["id"] for item in observations["observations"]
    }
    assert len(list(pipeline.checkpoint_dir.glob("risks-*.json"))) == 2
    assert [item["name"] for item in pipeline.stage_records] == [
        "risk_candidates__1",
        "risk_candidates__2",
    ]


@pytest.mark.parametrize("damage", ["missing", "foreign", "empty", "duplicate"])
def test_invalid_risk_partition_stops_after_one_repair_preserving_checkpoint(tmp_path, damage):
    pipeline, observations, responses = risk_partitions(tmp_path)
    target = responses[1]["risks"][0]["observation_ids"]
    if damage == "missing":
        target.pop()
    elif damage == "foreign":
        target.append("OBS-TEST-00")
    elif damage == "duplicate":
        target.append(target[0])
    else:
        responses[1]["risks"] = []
    responses.append(copy.deepcopy(responses[1]))
    with pytest.raises(SchemaValidationError):
        generate_risks(pipeline, FEATURE, {}, observations)
    assert pipeline.client.calls == 3
    assert (pipeline.checkpoint_dir / "risks-01.json").exists()
    assert not (pipeline.checkpoint_dir / "risks-02.json").exists()
    assert pipeline.meter.summary()["total_tokens"] == 90


@pytest.mark.parametrize("count", [0, 33])
def test_risk_partition_bound_stops_before_model_calls(tmp_path, count):
    pipeline, observations, _ = risk_partitions(tmp_path)
    observations["observations"] = [observations["observations"][0]] * count
    with pytest.raises(ModelError, match="1..32"):
        generate_risks(pipeline, FEATURE, {}, observations)
    assert pipeline.client.calls == 0


def test_merged_risks_still_require_existing_priority_calibration(tmp_path):
    pipeline, observations, responses = risk_partitions(tmp_path)
    for response in responses:
        response["risks"][0].update(impact=1, likelihood=1)
    with pytest.raises(SchemaValidationError, match="under-calibrated"):
        generate_risks(pipeline, FEATURE, {}, observations)


def write_valid_run(tmp_path, name="out"):
    path = tmp_path / "order-cancel.input.md"
    _feature_input(path)
    out = tmp_path / name
    client = FakeClient(batched_responses())
    config = resolve_config("generic", model="fake-local-model", generation_mode="batched")
    manifest = LocalDesignPipeline(config, client).run(path, out)
    return out, manifest, client


def test_batched_pipeline_finishes_complete_json_partitions(tmp_path):
    out, manifest, client = write_valid_run(tmp_path)
    assert manifest["design_status"] == "ready"
    assert client.calls == 8
    assert len(list((out / "checkpoints").glob("*.json"))) == 7
    assert manifest["usage_summary"]["total_tokens"] == 240
    assert manifest["comparison_config_hash"]
    for record in manifest["artifacts"].values():
        assert record["schema_valid"]
    assert summarize_run(out)["eligible_for_expanded_benchmark"]


@pytest.mark.parametrize("missing", ["parameters", "finite_values"])
def test_parameter_dependent_model_stops_during_core_repair(tmp_path, missing):
    path = tmp_path / "spec.md"
    _feature_input(path)
    core = batched_responses()[0]
    core["selected_techniques"] = ["decision_tables"]
    if missing == "parameters":
        core["parameters"] = []
    else:
        for parameter in core["parameters"]:
            parameter.pop("values", None)
    client = FakeClient([core, copy.deepcopy(core)])
    config = resolve_config("generic", model="fake", generation_mode="batched")
    with pytest.raises(ModelError, match="requires"):
        LocalDesignPipeline(config, client).run(path, tmp_path / "out")
    assert client.calls == 2
    assert not (tmp_path / "out/test_model.json").exists()


@pytest.mark.parametrize(
    "reason,kind",
    [
        ("length", "output_truncated"),
        ("content_filter", "incomplete_response"),
        ("tool_calls", "incomplete_response"),
    ],
)
def test_valid_json_with_incomplete_finish_is_rejected(reason, kind, monkeypatch):
    client = OpenAICompatibleClient(resolve_config("generic", model="fake"))
    usage = {"prompt_tokens": 5, "completion_tokens": 7}
    monkeypatch.setattr(
        client,
        "_request",
        lambda *args: {
            "choices": [{"message": {"content": "{}"}, "finish_reason": reason}],
            "usage": usage,
        },
    )
    with pytest.raises(LocalRuntimeError) as exc:
        client.complete_json(system="", user="", schema_name="test_model", schema={})
    assert exc.value.failure_kind == kind
    assert exc.value.finish_reason == reason
    assert exc.value.usage == usage


@pytest.mark.parametrize("reason", [None, "stop"])
def test_complete_or_unspecified_finish_remains_compatible(reason, monkeypatch):
    client = OpenAICompatibleClient(resolve_config("generic", model="fake"))
    monkeypatch.setattr(
        client,
        "_request",
        lambda *args: {"choices": [{"message": {"content": "{}"}, "finish_reason": reason}]},
    )
    assert (
        client.complete_json(system="", user="", schema_name="s", schema={}).finish_reason == reason
    )


def test_partition_inherits_profile_in_request_and_budget(monkeypatch):
    config = resolve_config("qwen36", generation_mode="batched")
    assert output_limit(config, "test_model__core_repair") == 3500
    assert output_limit(config, "manual_case_review__9") == 5000
    client = OpenAICompatibleClient(config)
    bodies = []

    def request(*args):
        bodies.append(args[-1])
        return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}

    monkeypatch.setattr(client, "_request", request)
    client.complete_json(system="", user="", schema_name="test_model__core_repair", schema={})
    assert bodies[0]["max_tokens"] == 3500
    assert bodies[0]["temperature"] == 0.2


def test_existing_outputs_are_untouched_before_model_calls(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    record = out / "run_manifest.json"
    record.write_bytes(b"original")
    path = tmp_path / "spec.md"
    _feature_input(path)
    client = FakeClient([])
    with pytest.raises(FileExistsError):
        LocalDesignPipeline(resolve_config("generic"), client).run(path, out)
    assert record.read_bytes() == b"original"
    assert client.calls == 0


def test_missing_input_creates_no_output(tmp_path):
    with pytest.raises(FileNotFoundError):
        LocalDesignPipeline(resolve_config("generic"), FakeClient([])).run(
            tmp_path / "missing", tmp_path / "out"
        )
    assert not (tmp_path / "out").exists()


def test_partition_failure_preserves_checkpoint_and_usage(tmp_path):
    path = tmp_path / "spec.md"
    _feature_input(path)
    config = resolve_config("generic", model="fake", generation_mode="batched")

    class FailingClient(FakeClient):
        def complete_json(self, **kwargs):
            if self.calls:
                exc = LocalRuntimeError(
                    "cut off", usage={"prompt_tokens": 3, "completion_tokens": 9}
                )
                exc.failure_kind = "output_truncated"
                exc.finish_reason = "length"
                raise exc
            return super().complete_json(**kwargs)

    with pytest.raises(LocalRuntimeError):
        LocalDesignPipeline(config, FailingClient(batched_responses())).run(path, tmp_path / "out")
    manifest = json.loads((tmp_path / "out/run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed" and manifest["design_status"] == "blocked"
    assert manifest["stop_reason"] == "output_truncated"
    assert manifest["usage_summary"]["total_tokens"] == 42
    assert (tmp_path / "out/checkpoints/test_model-core.json").is_file()
    validate_artifact(manifest, "local_run_manifest.schema.json")


def test_no_progress_stops_without_repeating_same_cases(tmp_path):
    model = domain()
    pipeline = LocalDesignPipeline(
        resolve_config("generic", model="fake", generation_mode="batched"),
        FakeClient([{"manual_cases": [], "exploratory_charters": []}]),
    )
    pipeline.technique_plan = plan(model)
    pipeline.source_ids = {"AC-1"}
    pipeline.checkpoint_dir = tmp_path / "checkpoints"
    result = generate_cases(pipeline, FEATURE, model, OBS, RISKS)
    assert result["manual_cases"] == []
    assert pipeline.client.calls == 1


def test_partial_budget_is_shared_across_partitions(tmp_path):
    path = tmp_path / "spec.md"
    _feature_input(path)
    config = resolve_config("generic", model="fake", generation_mode="batched")
    budget = LocalDesignPipeline(config).estimate(path)["first_stage_reservation"]

    class UnknownClient(FakeClient):
        def complete_json(self, **kwargs):
            return replace(super().complete_json(**kwargs), usage={})

    client = UnknownClient(batched_responses())
    with pytest.raises(TokenBudgetExceeded):
        LocalDesignPipeline(replace(config, token_budget=budget), client).run(
            path, tmp_path / "out"
        )
    assert client.calls == 1
    assert (tmp_path / "out/checkpoints/test_model-core.json").exists()


def test_selected_schema_references_are_closed_and_bounded():
    whole = portable_schema("test_model.schema.json")
    subset = select_schema(whole, ["domain_models"])
    assert "flows" not in subset["properties"]
    assert len(json.dumps(subset)) < len(json.dumps(whole))
    with pytest.raises(ModelError):
        select_schema({"properties": {"x": {"$ref": "remote.json"}}}, ["x"])


@pytest.mark.parametrize("status", ["ready", "degraded", "blocked"])
def test_cli_distinguishes_design_readiness(tmp_path, monkeypatch, status):
    path = tmp_path / "spec.md"
    _feature_input(path)
    monkeypatch.setattr(
        LocalDesignPipeline,
        "run",
        lambda *a, **k: {"model": "fake", "elapsed_seconds": 0, "design_status": status},
    )
    assert main(
        ["run", "local-design", "--input", str(path), "--output", str(tmp_path / "out")]
    ) == (0 if status == "ready" else 2)


def test_incomplete_design_cannot_be_ready():
    report = {
        "errors": [],
        "blocked_selections": [],
        "unknown_ids": [],
        "design": {"uncovered_ids": ["missing"], "rate": 50},
    }
    assert design_status({"errors": []}, report) == "degraded"
    assert design_status({"errors": ["invalid oracle"]}, report) == "blocked"


@pytest.mark.parametrize("damage", ["missing", "invalid_json", "hash", "coverage", "empty_quality"])
def test_benchmark_revalidates_real_artifacts(tmp_path, damage):
    out, _, _ = write_valid_run(tmp_path)
    target = out / "test_model.json"
    if damage == "missing":
        target.unlink()
    elif damage == "invalid_json":
        (out / "run_manifest.json").write_text("broken", encoding="utf-8")
    elif damage == "hash":
        target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")
    elif damage == "empty_quality":
        (out / "quality_report.json").write_text("{}", encoding="utf-8")
    else:
        path = out / "coverage_report.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["design"]["covered_by_cases"] = 1
        report["design"]["rate"] = 100
        path.write_text(json.dumps(report), encoding="utf-8")
    result = summarize_run(out)
    assert not result["eligible_for_expanded_benchmark"]


def test_mismatched_identity_blocks_comparison():
    value = {
        "eligible_for_expanded_benchmark": True,
        "usage": {"total_tokens": 20},
        "identity": {
            "model": "A",
            "profile": "generic",
            "input_sha256": "x",
            "common_config_hash": "y",
        },
    }
    other = copy.deepcopy(value)
    other["identity"]["model"] = "B"
    assert not compare_runs(value, other)["comparable"]


@pytest.mark.parametrize("duplicate", ["model", "parameter"])
def test_duplicate_partition_ids_are_rejected(tmp_path, duplicate):
    path = tmp_path / "spec.md"
    _feature_input(path)
    responses = batched_responses()
    target = responses[1]["domain_models"] if duplicate == "model" else responses[0]["parameters"]
    target.append(copy.deepcopy(target[0]))
    config = resolve_config("generic", model="fake", generation_mode="batched")
    with pytest.raises(ModelError, match="duplicate"):
        LocalDesignPipeline(config, FakeClient(responses)).run(path, tmp_path / "out")


def test_review_cannot_modify_case_outside_current_partition(tmp_path):
    path = tmp_path / "spec.md"
    _feature_input(path)
    responses = batched_responses()
    patch = {
        "case_updates": [{"tc_id": "TC-003", "changes": {"expected_results": ["changed"]}}],
        "charter_updates": [],
    }
    responses[6] = responses[7] = patch
    config = resolve_config("generic", model="fake", generation_mode="batched")
    with pytest.raises(ModelError, match="unknown"):
        LocalDesignPipeline(config, FakeClient(responses)).run(path, tmp_path / "out")
    saved = json.loads((tmp_path / "out/checkpoints/cases-02.json").read_text(encoding="utf-8"))
    assert saved["manual_cases"][2]["expected_results"] != ["changed"]


def test_normalization_repair_keeps_original_partition_context():
    class Client(FakeClient):
        def complete_json(self, **kwargs):
            self.last_prompt = kwargs["user"]
            return super().complete_json(**kwargs)

    value = {"feature_id": "F", "spec_revision": "rev-1", "manual_cases": []}
    client = Client([value, value])
    pipeline = LocalDesignPipeline(
        resolve_config("generic", model="fake", generation_mode="batched"), client
    )

    def normalize(value):
        if client.calls == 1:
            raise TypeError("invalid list element")
        return value

    result = pipeline._generate_custom(
        "manual_case_set__1",
        portable_schema("manual_case_set.schema.json"),
        "AC-1 original requirement",
        normalize=normalize,
    )
    assert result == value
    assert "AC-1 original requirement" in client.last_prompt
    assert pipeline.meter.records[0]["outcome"] == "invalid_artifact"
    assert pipeline.meter.summary()["repair_calls"] == 1


def test_case_partition_count_is_finite_even_when_progress_continues(tmp_path):
    from bb_harness.batched_generation import MAX_CASE_BATCHES
    from tests.test_coverage_engine import case

    model = domain()
    template = model["domain_models"][0]
    model["domain_models"] = [{**copy.deepcopy(template), "id": f"D-{i:02d}"} for i in range(30)]
    batches = []
    for i in range(MAX_CASE_BATCHES):
        items = [case({"x": x}, tc_id=f"TC-{x}") for x in (9, 10)]
        for item in items:
            item["coverage_inputs"][0]["model_ref"] = f"D-{i:02d}"
        batches.append({"feature_id": "F", "manual_cases": items, "exploratory_charters": []})
    pipeline = LocalDesignPipeline(
        resolve_config("generic", model="fake", generation_mode="batched"), FakeClient(batches)
    )
    pipeline.technique_plan = plan(model)
    pipeline.source_ids = {"AC-1"}
    pipeline.checkpoint_dir = tmp_path / "checkpoints"
    result = generate_cases(pipeline, FEATURE, model, OBS, RISKS)
    assert pipeline.client.calls == MAX_CASE_BATCHES
    assert len(result["manual_cases"]) == MAX_CASE_BATCHES * 2


def test_comparator_rejects_changed_response_model(tmp_path):
    out, manifest, _ = write_valid_run(tmp_path)
    manifest["call_records"][0]["model"] = "different-model"
    (out / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = summarize_run(out)
    assert not result["eligible_for_expanded_benchmark"]
    assert "response model identity missing or changed" in result["validation_errors"]


def test_comparison_command_accepts_verified_outputs(tmp_path, monkeypatch):
    from bb_harness import efficiency_benchmark as benchmark

    fixture = tmp_path / "order-cancel.input.md"
    _feature_input(fixture)

    class Pipeline:
        def __init__(self, config):
            self.config = config

        def run(self, path, out):
            responses = _responses()
            typed = domain()
            responses[0].update({key: typed[key] for key in ("parameters", "domain_models")})
            for item, x in zip(responses[3]["manual_cases"][:2], (10, 9), strict=True):
                item["coverage_inputs"] = [
                    {
                        "model_ref": "D",
                        "data": {"x": x},
                        "step_refs": [1],
                        "expected_result_refs": [1],
                    }
                ]
            if self.config.generation_mode == "full":
                responses[4] = responses[5] = copy.deepcopy(responses[3])
            else:
                responses = responses[:4] + [{"case_updates": [], "charter_updates": []}]
            return LocalDesignPipeline(self.config, FakeClient(responses)).run(path, out)

    monkeypatch.setattr(benchmark, "LocalDesignPipeline", Pipeline)
    out = tmp_path / "comparison"
    assert (
        benchmark.main(
            [
                "--input",
                str(fixture),
                "--output",
                str(out),
                "--profile",
                "generic",
                "--model",
                "fake-local-model",
            ]
        )
        == 0
    )
    result = json.loads((out / "comparison.json").read_text(encoding="utf-8"))
    assert result["identities_match"]
    assert result["comparable"]
    assert result["token_reduction_percent"] == 16.67
    assert result["common_config_hash"] == result["runs"]["full"]["identity"]["common_config_hash"]


def test_comparison_modes_must_be_different(tmp_path):
    from bb_harness.efficiency_benchmark import main as compare_main

    with pytest.raises(SystemExit):
        compare_main(
            [
                "--input",
                "unused",
                "--output",
                str(tmp_path / "out"),
                "--modes",
                "batched",
                "batched",
            ]
        )


@pytest.mark.parametrize("field", ["boundaries", "data_partitions", "invalid_transitions"])
def test_generation_minima_match_semantic_requirements(field, tmp_path):
    from bb_harness.batched_generation import model_core_request

    path = tmp_path / "spec.md"
    _feature_input(path)
    feature = normalize_feature_spec(path)
    schema, _ = model_core_request(feature)
    assert schema["properties"][field]["minItems"] == 1
    pipeline = LocalDesignPipeline(resolve_config("generic"))
    assert (
        pipeline._stage_schema("test_model", "test_model.schema.json")["properties"][field][
            "minItems"
        ]
        == 1
    )
