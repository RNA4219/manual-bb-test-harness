"""予算・差分レビュー・未被覆補完・失敗記録の境界を確認する。"""

import copy
import json
from dataclasses import replace

import pytest

from bb_harness.cli import main
from bb_harness.efficiency_benchmark import compare_runs, summarize_run
from bb_harness.efficient_generation import apply_review_patch, compact_case_prompt, remaining_work
from bb_harness.local_pipeline import LocalDesignPipeline
from bb_harness.local_runtime import LocalRuntimeError, OpenAICompatibleClient, resolve_config
from bb_harness.schema_validation import SchemaValidationError, validate_artifact
from bb_harness.techniques.common import ModelError
from bb_harness.token_budget import TokenBudgetExceeded, TokenMeter, estimate_input, output_limit
from tests.test_coverage_engine import FEATURE, OBS, RISKS, case, cases, domain, plan
from tests.test_local_pipeline import FakeClient, _feature_input, _responses


@pytest.mark.parametrize("budget", [0, -1, True, 1.5, "100"])
def test_budget_requires_positive_integer(budget):
    with pytest.raises(ValueError):
        TokenMeter(budget)
    with pytest.raises(LocalRuntimeError):
        resolve_config("generic", token_budget=budget)


@pytest.mark.parametrize(
    "usage",
    [
        {},
        {"prompt_tokens": -1, "completion_tokens": 2},
        {"prompt_tokens": True, "completion_tokens": 2},
        {"prompt_tokens": 1},
        {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 4},
    ],
)
def test_unknown_usage_reserves_estimate_and_never_reports_zero(usage):
    meter = TokenMeter(1000)
    record = meter.prepare("s", "日本語", "input", {}, 20)
    meter.finish(record, usage, 0.5, "runtime_error")
    summary = meter.summary()
    assert summary["total_tokens"] is None
    assert summary["unreported_calls"] == 1
    assert summary["accounted_tokens"] == record["estimated_input_tokens"] + 20
    assert record["usage_status"] == ("invalid" if usage else "unknown")


def test_exact_budget_and_repair_share_reservation():
    reservation = estimate_input("", "", {}) + 20
    meter = TokenMeter(reservation)
    record = meter.prepare("s", "", "", {}, 20)
    meter.finish(record, {"prompt_tokens": 10, "completion_tokens": 20}, 0.1, "invalid_artifact")
    with pytest.raises(TokenBudgetExceeded):
        meter.prepare("s_repair", "", "", {}, 20)
    assert meter.summary()["calls"] == 1
    assert meter.summary()["repair_calls"] == 0
    assert meter.summary()["total_tokens"] == 30
    assert meter.summary()["budget_exhausted"]
    assert meter.records[1]["outcome"] == "budget_blocked"


def test_usage_allows_reported_zero_and_tracks_repair():
    meter = TokenMeter()
    for stage in ("s", "s_repair"):
        r = meter.prepare(stage, "", "", {}, 20)
        meter.finish(
            r, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, 0, "succeeded"
        )
    assert meter.summary()["total_tokens"] == 0
    assert meter.summary()["repair_calls"] == 1
    config = resolve_config("qwen36")
    assert output_limit(config, "test_model_repair") == 3500
    with pytest.raises(ValueError):
        output_limit(replace(config, max_tokens=-1, stage_overrides={}), "s")
    with pytest.raises(LocalRuntimeError):
        resolve_config("generic", generation_mode="bad")


def test_projection_keeps_uncovered_witness_once_and_retains_constraints():
    model = domain()
    model["domain_models"].append({**copy.deepcopy(model["domain_models"][0]), "id": "OTHER"})
    initial = cases(case({"x": 10}), case({"x": 9}, tc_id="TC-2"))
    prompt = compact_case_prompt(FEATURE, model, OBS, RISKS, initial)
    context = json.loads(prompt.split("入力:\n", 1)[1])
    assert {item["model_ref"] for item in context["required_obligations"]} == {"OTHER"}
    assert [item["id"] for item in context["test_model"]["domain_models"]] == ["OTHER"]
    assert context["test_model"]["parameters"] == model["parameters"]
    assert "obligations" not in context["pending"]
    assert "steps" not in context["existing_case_index"][0]
    assert not any(remaining_work(FEATURE, domain(), OBS, RISKS, initial).values())
    assert len(plan(model)["obligation_sets"]) == 2


def test_patch_is_small_non_mutating_and_can_be_empty():
    value = cases(case())
    empty = {"case_updates": [], "charter_updates": []}
    assert apply_review_patch(value, empty) == value
    patch = {
        "case_updates": [{"tc_id": "TC-1", "changes": {"expected_results": ["訂正した期待値"]}}],
        "charter_updates": [],
    }
    result = apply_review_patch(value, patch)
    assert result["manual_cases"][0]["expected_results"] == ["訂正した期待値"]
    assert value["manual_cases"][0]["expected_results"] != ["訂正した期待値"]


@pytest.mark.parametrize(
    "change", [{"tc_id": "X"}, {"steps": []}, {"coverage_inputs": []}, {"delete": True}, {}]
)
def test_patch_rejects_structural_changes(change):
    with pytest.raises(SchemaValidationError):
        apply_review_patch(
            cases(case()),
            {"case_updates": [{"tc_id": "TC-1", "changes": change}], "charter_updates": []},
        )


@pytest.mark.parametrize("ids", [["UNKNOWN"], ["TC-1", "TC-1"]])
def test_patch_rejects_unknown_and_duplicate_ids(ids):
    with pytest.raises(ModelError):
        apply_review_patch(
            cases(case()),
            {
                "case_updates": [
                    {"tc_id": key, "changes": {"estimate_minutes": 10}} for key in ids
                ],
                "charter_updates": [],
            },
        )


def test_cli_estimate_has_no_network_or_output_side_effect(tmp_path, monkeypatch, capsys):
    path = tmp_path / "spec.md"
    _feature_input(path)

    def forbidden(*args, **kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr(OpenAICompatibleClient, "discover_model", forbidden)
    assert (
        main(
            [
                "run",
                "local-design",
                "--input",
                str(path),
                "--output",
                str(tmp_path / "out"),
                "--estimate-only",
                "--token-budget",
                "1",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["generation_mode"] == "compact"
    assert report["total_tokens_estimate"] is None
    assert not report["first_stage_budget_fits"]
    assert not (tmp_path / "out").exists()


def test_pipeline_budget_failure_keeps_manifest(tmp_path):
    path = tmp_path / "spec.md"
    _feature_input(path)
    client = FakeClient([])
    pipeline = LocalDesignPipeline(resolve_config("generic", model="fake", token_budget=1), client)
    with pytest.raises(TokenBudgetExceeded):
        pipeline.run(path, tmp_path / "out")
    manifest = json.loads((tmp_path / "out/run_manifest.json").read_text(encoding="utf-8"))
    validate_artifact(manifest, "local_run_manifest.schema.json")
    assert client.calls == 0
    assert manifest["stop_reason"] == "token_budget"
    assert manifest["status"] == "failed"
    assert "feature_spec" in manifest["artifacts"]


def test_repair_budget_failure_keeps_first_call_usage(tmp_path):
    path = tmp_path / "spec.md"
    _feature_input(path)

    class UnknownClient(FakeClient):
        def complete_json(self, **kwargs):
            return replace(super().complete_json(**kwargs), usage={})

    config = resolve_config("generic", model="fake")
    estimate = LocalDesignPipeline(config).estimate(path)
    config = replace(config, token_budget=estimate["first_stage_reservation"])
    client = UnknownClient([{}])
    with pytest.raises(TokenBudgetExceeded):
        LocalDesignPipeline(config, client).run(path, tmp_path / "out")
    manifest = json.loads((tmp_path / "out/run_manifest.json").read_text(encoding="utf-8"))
    assert client.calls == 1
    assert manifest["usage_summary"]["total_tokens"] is None
    assert manifest["call_records"][0]["outcome"] == "invalid_artifact"
    assert manifest["call_records"][1]["outcome"] == "budget_blocked"


@pytest.mark.parametrize("content", ["{broken", None])
def test_unparseable_response_preserves_actual_usage(content, monkeypatch):
    client = OpenAICompatibleClient(resolve_config("generic", model="fake"))
    usage = {"prompt_tokens": 8, "completion_tokens": 5, "total_tokens": 13}
    monkeypatch.setattr(
        client,
        "_request",
        lambda *args: {"choices": [{"message": {"content": content}}], "usage": usage},
    )
    with pytest.raises(LocalRuntimeError) as exc:
        client.complete_json(system="", user="", schema_name="s", schema={})
    assert exc.value.usage == usage


def test_compact_pipeline_uses_patch_review_and_binds_cases(tmp_path):
    path = tmp_path / "order-cancel.input.md"
    _feature_input(path)

    class CompactClient(FakeClient):
        def complete_json(self, **kwargs):
            if kwargs["schema_name"] == "manual_case_review":
                self.responses[self.calls] = {"case_updates": [], "charter_updates": []}
            return super().complete_json(**kwargs)

    client = CompactClient(_responses())
    manifest = LocalDesignPipeline(resolve_config("generic", model="fake"), client).run(
        path, tmp_path / "out"
    )
    assert manifest["status"] == "succeeded"
    assert manifest["usage_summary"]["total_tokens"] == client.calls * 30
    bound = json.loads((tmp_path / "out/manual_case_set.json").read_text(encoding="utf-8"))
    assert bound["evidence_binding"]["mode"] == "case_revision"
    assert all(item["case_revision"] for item in bound["manual_cases"])


def test_fully_covered_compact_pipeline_skips_remainder(tmp_path):
    path = tmp_path / "order-cancel.input.md"
    _feature_input(path)
    responses = _responses()
    typed = domain()
    responses[0].update({key: typed[key] for key in ("parameters", "domain_models")})
    responses[3]["manual_cases"][0]["coverage_inputs"] = [
        {"model_ref": "D", "data": {"x": x}, "step_refs": [1], "expected_result_refs": [1]}
        for x in (9, 10)
    ]
    responses[4] = {"case_updates": [], "charter_updates": []}
    client = FakeClient(responses[:5])
    manifest = LocalDesignPipeline(resolve_config("generic", model="fake"), client).run(
        path, tmp_path / "out"
    )
    assert client.calls == 5
    assert "manual_case_remainder" not in [record["stage"] for record in manifest["call_records"]]
    report = json.loads((tmp_path / "out/coverage_report.json").read_text(encoding="utf-8"))
    assert report["design"]["rate"] == 100


@pytest.mark.parametrize("kind", ["parse", "transport"])
def test_runtime_failure_manifest_preserves_reported_or_unknown_usage(tmp_path, monkeypatch, kind):
    path = tmp_path / "spec.md"
    _feature_input(path)
    config = resolve_config("generic", model="fake")
    client = OpenAICompatibleClient(config)

    def response(*args):
        if kind == "transport":
            raise LocalRuntimeError("connection failed")
        return {
            "choices": [{"message": {"content": "broken"}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 5},
        }

    monkeypatch.setattr(client, "_request", response)
    with pytest.raises(LocalRuntimeError):
        LocalDesignPipeline(config, client).run(path, tmp_path / "out")
    manifest = json.loads((tmp_path / "out/run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["usage_summary"]["total_tokens"] == (13 if kind == "parse" else None)
    assert manifest["call_records"][0]["outcome"] == (
        "json_parse_error" if kind == "parse" else "runtime_error"
    )
    validate_artifact(manifest, "local_run_manifest.schema.json")


@pytest.mark.parametrize("eligible,total", [(False, 100), (True, None), (True, 0)])
def test_failed_or_unknown_comparison_cannot_claim_reduction(eligible, total):
    valid = {"eligible_for_expanded_benchmark": True, "usage": {"total_tokens": 200}}
    other = {"eligible_for_expanded_benchmark": eligible, "usage": {"total_tokens": total}}
    assert compare_runs(valid, other)["token_reduction_percent"] is None


def test_measured_comparison_and_missing_manifest(tmp_path):
    valid = {"eligible_for_expanded_benchmark": True, "usage": {"total_tokens": 200}}
    other = {"eligible_for_expanded_benchmark": True, "usage": {"total_tokens": 150}}
    identity = {
        "model": "fake",
        "profile": "generic",
        "input_sha256": "same",
        "common_config_hash": "same",
    }
    valid["identity"] = other["identity"] = identity
    assert compare_runs(valid, other)["token_reduction_percent"] == 25
    missing = summarize_run(tmp_path)
    assert missing["status"] == "failed"
    assert missing["usage"].get("total_tokens") is None
    assert not missing["eligible_for_expanded_benchmark"]
