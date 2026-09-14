"""同じ設定でfull/compactを順次比較し、欠測と失敗を保持する。"""

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

from bb_harness.coverage_engine import build_coverage_report, build_technique_plan
from bb_harness.local_pipeline import LocalDesignPipeline, _config_hash
from bb_harness.local_runtime import resolve_config
from bb_harness.tools.verify_local_benchmark import verify_run


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path.name}")
    return value


def summarize_run(directory: Path) -> dict:
    errors = []

    def read(name):
        try:
            return _read(directory / f"{name}.json")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{name}: {type(exc).__name__}")
            return {}

    manifest, quality, coverage = (
        read(name) for name in ("run_manifest", "quality_report", "coverage_report")
    )
    usage = manifest.get("usage_summary", {})
    if not isinstance(usage, dict):
        usage = {}
    succeeded = manifest.get("status") == "succeeded"
    checks = {}
    if succeeded:
        try:
            checks = verify_run(directory, directory.name, 1)["checks"]
            reported_models = {
                record.get("model")
                for record in manifest.get("call_records", [])
                if record.get("outcome") != "budget_blocked"
            }
            if reported_models != {manifest.get("model")} or None in reported_models:
                errors.append("response model identity missing or changed")
            feature, model, observations, risks, cases = (
                read(name)
                for name in (
                    "feature_spec",
                    "test_model",
                    "observation_set",
                    "risk_register",
                    "manual_case_set",
                )
            )
            plan = build_technique_plan(feature, model, observations, risks)
            recalculated = build_coverage_report(model, plan, cases, build_id=coverage["build_id"])
            for key in (
                "design",
                "errors",
                "unknown_ids",
                "blocked_selections",
                "model_hash",
                "case_hash",
                "plan_hash",
            ):
                if coverage.get(key) != recalculated[key]:
                    errors.append(f"coverage recalculation mismatch: {key}")
            coverage = recalculated
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append(f"artifact validation: {type(exc).__name__}")
    schema_valid = (
        succeeded
        and bool(checks)
        and not errors
        and all(
            value
            for key, value in checks.items()
            if key.endswith("_schema_hash") or key == "all_stage_schemas"
        )
    )
    structure_valid = schema_valid and quality.get("automatic_fails") == [] and all(checks.values())
    design = coverage.get("design", {})
    if not isinstance(design, dict):
        design = {}
    coverage_valid = (
        schema_valid
        and bool(coverage)
        and not any(coverage.get(key) for key in ("errors", "unknown_ids", "blocked_selections"))
        and design.get("required_feasible", 0) > 0
        and design.get("rate") == 100
    )
    return {
        "status": manifest.get("status", "failed"),
        "error": manifest.get("error"),
        "elapsed_seconds": manifest.get("elapsed_seconds"),
        "usage": usage,
        "schema_valid": schema_valid,
        "structure_valid": structure_valid,
        "automatic_fails": quality.get("automatic_fails"),
        "coverage_valid": coverage_valid,
        "design_coverage": design or None,
        "eligible_for_expanded_benchmark": succeeded
        and schema_valid
        and structure_valid
        and coverage_valid,
        "independent_quality_score": None,
        "validation_errors": errors,
        "identity": {
            "input_sha256": manifest.get("input_sha256"),
            "model": manifest.get("model"),
            "profile": manifest.get("profile"),
            "common_config_hash": manifest.get("comparison_config_hash"),
        },
    }


def compare_runs(
    full: dict, compact: dict, *, modes: tuple[str, str] = ("full", "compact")
) -> dict:
    comparable = all(run["eligible_for_expanded_benchmark"] for run in (full, compact))
    values = [run["usage"].get("total_tokens") for run in (full, compact)]
    measured = all(type(value) is int and value > 0 for value in values)
    identity = full.get("identity", {})
    identities_match = (
        bool(identity) and all(identity.values()) and identity == compact.get("identity")
    )
    comparable = comparable and identities_match
    return {
        "runs": {modes[0]: full, modes[1]: compact},
        "identities_match": bool(identities_match),
        "comparable": comparable and measured,
        "token_reduction_percent": round((1 - values[1] / values[0]) * 100, 2)
        if comparable and measured
        else None,
        "expanded_benchmark_allowed": comparable and measured,
        "note": "構造・被覆の成立は独立した意味的品質採点ではない。失敗と欠測を0消費にしない。",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="qwen36")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--token-budget", type=int)
    parser.add_argument(
        "--modes", nargs=2, choices=["compact", "full", "batched"], default=["full", "compact"]
    )
    args = parser.parse_args(argv)
    if args.modes[0] == args.modes[1]:
        parser.error("comparison requires two different modes")
    config = resolve_config(
        args.profile,
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
        token_budget=args.token_budget,
    )
    if not args.input.is_file():
        parser.error("input must be an existing file")
    if args.output.exists():
        parser.error("output must not exist")
    args.output.mkdir(parents=True)
    runs = {}
    for mode in args.modes:
        directory = args.output / mode
        print(f"Starting {mode}", flush=True)
        try:
            LocalDesignPipeline(replace(config, generation_mode=mode)).run(args.input, directory)
        except Exception as exc:
            print(f"{mode}: {type(exc).__name__}: {str(exc)[:400]}", flush=True)
        runs[mode] = summarize_run(directory)
        print(json.dumps({mode: runs[mode]}, ensure_ascii=False), flush=True)
    summary = compare_runs(runs[args.modes[0]], runs[args.modes[1]], modes=tuple(args.modes))
    common = asdict(config)
    common.pop("api_key", None)
    common.pop("generation_mode", None)
    summary.update(
        input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        common_config=common,
        common_config_hash=_config_hash(config, comparison=True),
    )
    (args.output / "comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if summary["expanded_benchmark_allowed"] else 1
