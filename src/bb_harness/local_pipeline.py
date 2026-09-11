"""ローカルLLMを候補生成器として使うmanual-bb設計パイプライン。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from bb_harness.batched_generation import (
    design_status,
    generate_cases,
    generate_model,
    generate_risks,
    review_cases,
)
from bb_harness.coverage_engine import (
    build_coverage_report,
    build_technique_plan,
    coverage_summary,
    validate_case_coverage,
)
from bb_harness.efficient_generation import (
    apply_review_patch,
    compact_case_prompt,
    coverage_input_examples,
    remaining_work,
    review_patch_prompt,
)
from bb_harness.evidence_revisions import bind_case_set
from bb_harness.gate_engine import load_evidence_files
from bb_harness.gate_engine import main as evaluate_gate_main
from bb_harness.local_runtime import LocalRuntimeConfig, OpenAICompatibleClient
from bb_harness.schema_validation import (
    SchemaValidationError,
    load_schema,
    validate_artifact,
)
from bb_harness.token_budget import TokenBudgetExceeded, TokenMeter, estimate_input, output_limit
from bb_harness.tools._shared.spec_ingest_markdown import (
    extract_markdown_sections,
    fallback_feature_id,
    ingest_markdown_spec,
    normalize_section_name,
    read_markdown,
)


class LocalPipelineError(RuntimeError):
    """local-designがfail closedした場合。"""


ARTIFACT_SCHEMAS = {
    "feature_spec": "feature_spec.schema.json",
    "test_model": "test_model.schema.json",
    "observation_set": "observation_set.schema.json",
    "risk_register": "risk_register.schema.json",
    "manual_case_set": "manual_case_set.schema.json",
    "effort_plan": "effort_plan.schema.json",
    "gate_decision": "gate_decision.schema.json",
    "release_brief": "release_brief.schema.json",
    "technique_plan": "technique_plan.schema.json",
    "coverage_report": "coverage_report.schema.json",
}

RISK_CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["feature_id", "risks"],
    "properties": {
        "feature_id": {"type": "string", "minLength": 1},
        "risks": {
            "type": "array",
            "minItems": 3,
            "maxItems": 10,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "scenario",
                    "impact",
                    "likelihood",
                    "detectability_difficulty",
                    "change_surface",
                    "externality",
                    "privilege",
                    "automation_credit",
                    "rationale",
                    "observation_ids",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "scenario": {"type": "string", "minLength": 1},
                    "impact": {"type": "integer", "minimum": 1, "maximum": 5},
                    "likelihood": {"type": "integer", "minimum": 1, "maximum": 5},
                    "detectability_difficulty": {"type": "integer", "minimum": 0, "maximum": 2},
                    "change_surface": {"type": "integer", "minimum": 0, "maximum": 2},
                    "externality": {"type": "integer", "minimum": 0, "maximum": 2},
                    "privilege": {"type": "integer", "minimum": 0, "maximum": 2},
                    "automation_credit": {"type": "integer", "minimum": 0, "maximum": 2},
                    "rationale": {"type": "string", "minLength": 1},
                    "observation_ids": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

SYSTEM_PROMPT = """あなたはmanual-bbの候補生成workerです。日本語で、与えられた根拠だけを使ってください。
推測は根拠として捏造せず、必要ならassumptionまたはexploratory charterとして明示します。
JSON Schemaに完全準拠したJSONオブジェクトだけを返してください。Gate、点数計算、工数合計は行いません。"""


class LocalDesignPipeline:
    """段階生成・検証・決定的補正を統括する。"""

    def __init__(self, config: LocalRuntimeConfig, client: OpenAICompatibleClient | None = None):
        self.config = config
        self.client = client or OpenAICompatibleClient(config)
        self.stage_records: list[dict[str, Any]] = []
        self.source_ids: set[str] = set()
        self.generation: dict[str, Any] | None = None
        self.meter = TokenMeter(config.token_budget)

    def run(
        self,
        input_path: Path,
        output_dir: Path,
        *,
        evidence_path: Path | None = None,
        build_id: str = "local-design-unexecuted",
        gate_profile: str = "standard",
    ) -> dict[str, Any]:
        """1つの仕様から一式を生成する。"""
        self.stage_records = []
        self.source_ids = set()
        self.generation = None
        self.meter = TokenMeter(self.config.token_budget)
        stop_reason = None
        readiness = "blocked"
        started_monotonic = time.monotonic()
        started_at = _now()
        run_id = (
            f"local-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        )
        input_bytes = input_path.read_bytes()
        output_dir.mkdir(parents=True, exist_ok=False)
        self.checkpoint_dir = output_dir / "checkpoints"
        model = self.config.model or "unresolved"
        artifacts: dict[str, dict[str, Any]] = {}
        try:
            model = self.client.discover_model()
            feature = normalize_feature_spec(input_path)
            self.source_ids = {item["id"] for item in feature["source_refs"]}
            self.generation = {
                "generation_run_id": run_id,
                "prompt_template_id": "local-design",
                "prompt_template_version": "batched-3"
                if self.config.generation_mode == "batched"
                else "efficient-2"
                if self.config.generation_mode == "compact"
                else "coverage-2",
                "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
                "output_schema_id": "local_run_manifest.schema.json",
                "model": {"provider": "openai-compatible", "name": model, "version": None},
                "parameters": {"temperature": self.config.temperature, "seed": None},
                "generated_at": started_at,
                "review_status": "pending",
            }
            self._save_artifact(output_dir, "feature_spec", feature, artifacts)

            if self.config.generation_mode == "batched":
                test_model = generate_model(self, feature)
            else:
                test_model = self._generate_artifact(
                    "test_model",
                    "test_model.schema.json",
                    _test_model_prompt(feature),
                    normalize=lambda value: _normalize_test_model(value, feature),
                )
            self._save_artifact(output_dir, "test_model", test_model, artifacts)

            observations = self._generate_artifact(
                "observation_set",
                "observation_set.schema.json",
                _observation_prompt(feature, test_model),
                normalize=lambda value: _normalize_observations(value, feature),
            )
            self._save_artifact(output_dir, "observation_set", observations, artifacts)

            if self.config.generation_mode == "batched":
                risk_candidates = generate_risks(self, feature, test_model, observations)
            else:
                risk_candidates = self._generate_custom(
                    "risk_candidates",
                    RISK_CANDIDATE_SCHEMA,
                    _risk_prompt(feature, test_model, observations),
                    normalize=lambda value: _normalize_risk_candidates(
                        value, feature["feature_id"], observations
                    ),
                    semantic_validate=lambda value: _validate_risk_candidate_semantics(
                        value, observations
                    ),
                )
            risks = build_risk_register(feature["feature_id"], risk_candidates)
            self._save_artifact(output_dir, "risk_register", risks, artifacts)
            technique_plan = build_technique_plan(feature, test_model, observations, risks)
            self._save_artifact(output_dir, "technique_plan", technique_plan, artifacts)
            self.technique_plan = technique_plan
            self.coverage_model = test_model

            if self.config.generation_mode == "batched":
                cases = generate_cases(self, feature, test_model, observations, risks)
            else:
                cases = self._generate_artifact(
                    "manual_case_set",
                    "manual_case_set.schema.json",
                    (
                        compact_case_prompt(feature, test_model, observations, risks)
                        if self.config.generation_mode == "compact"
                        else _case_prompt(
                            feature,
                            test_model,
                            observations,
                            risks,
                            focus="P0/P1 riskと主要な正常・拒否経路",
                        )
                    ),
                    normalize=lambda value: _normalize_cases(value, feature, observations, risks),
                )
                pending = remaining_work(feature, test_model, observations, risks, cases)
                if self.config.generation_mode == "full" or any(pending.values()):
                    remainder = self._generate_artifact(
                        "manual_case_remainder",
                        "manual_case_set.schema.json",
                        (
                            compact_case_prompt(feature, test_model, observations, risks, cases)
                            if self.config.generation_mode == "compact"
                            else _case_prompt(
                                feature,
                                test_model,
                                observations,
                                risks,
                                focus="P2/P3 risk、未被覆の境界・platform・競合・弱いoracle",
                                existing=cases,
                            )
                        ),
                        normalize=lambda value: _normalize_cases(
                            value, feature, observations, risks
                        ),
                    )
                    cases = _merge_case_sets(cases, remainder, feature, observations, risks)
            draft = cases
            if self.config.generation_mode == "batched":
                cases = review_cases(self, feature, test_model, observations, risks, draft)
            elif self.config.generation_mode == "compact":

                def validate_review(patch: dict) -> None:
                    revised = apply_review_patch(draft, patch)
                    _validate_case_semantics(revised, compact=True)
                    _validate_source_grounding(revised, self.source_ids)
                    checked = validate_case_coverage(revised, test_model, technique_plan)
                    if checked["errors"]:
                        raise ValueError("; ".join(checked["errors"][:5]))

                patch = self._generate_custom(
                    "manual_case_review",
                    portable_schema("case_review_patch.schema.json"),
                    review_patch_prompt(feature, test_model, observations, risks, draft),
                    semantic_validate=validate_review,
                )
                cases = apply_review_patch(draft, patch)
            else:
                reviewed = self._generate_artifact(
                    "manual_case_review",
                    "manual_case_set.schema.json",
                    _case_review_prompt(feature, test_model, observations, risks, cases),
                    normalize=lambda value: _normalize_cases(value, feature, observations, risks),
                )
                cases = _preserve_review_cases(draft, reviewed, feature, observations, risks)
            cases = bind_case_set(cases, test_model)
            _link_risks_and_cases(risks, cases)
            validate_artifact(risks, "risk_register.schema.json")
            validate_artifact(cases, "manual_case_set.schema.json")
            self._save_artifact(output_dir, "risk_register", risks, artifacts)
            self._save_artifact(output_dir, "manual_case_set", cases, artifacts)

            effort = build_effort_plan(feature["feature_id"], cases)
            self._save_artifact(output_dir, "effort_plan", effort, artifacts)

            lint = lint_design(feature, test_model, observations, risks, cases, effort)
            coverage = build_coverage_report(
                test_model,
                technique_plan,
                cases,
                load_evidence_files(evidence_path) if evidence_path is not None else [],
                build_id=build_id,
            )
            self._save_artifact(output_dir, "coverage_report", coverage, artifacts)
            lint["errors"].extend(coverage["errors"])
            if (
                coverage["design"]["uncovered_ids"]
                or coverage["unknown_ids"]
                or coverage["blocked_selections"]
            ):
                lint["warnings"].append(
                    "形式的被覆に未設計・未解決の項目がある。coverage_reportを確認する"
                )
            lint["status"] = "fail" if lint["errors"] else "pass"
            _write_json(output_dir / "lint_report.json", lint)

            gate = self._build_gate(
                output_dir,
                feature,
                observations,
                risks,
                cases,
                evidence_path=evidence_path,
                build_id=build_id,
                gate_profile=gate_profile,
            )
            gate["evidence_summary"].update(
                coverage_summary(coverage, feature_id=feature["feature_id"], build_id=build_id)
            )
            self._save_artifact(output_dir, "gate_decision", gate, artifacts)
            brief = build_release_brief(feature, gate, risks)
            self._save_artifact(output_dir, "release_brief", brief, artifacts)

            quality = score_structure(feature, test_model, observations, risks, cases, gate, lint)
            _write_json(output_dir / "quality_report.json", quality)
            (output_dir / "manual-test-design.md").write_text(
                render_markdown(
                    feature,
                    test_model,
                    observations,
                    risks,
                    cases,
                    effort,
                    gate,
                    brief,
                    coverage=coverage,
                ),
                encoding="utf-8",
            )
            readiness = design_status(lint, coverage)
            status, error = "succeeded", None
        except Exception as exc:
            status, error = "failed", f"{type(exc).__name__}: {exc}"
            stop_reason = (
                "token_budget"
                if isinstance(exc, TokenBudgetExceeded)
                else getattr(exc, "failure_kind", "generation_error")
            )
            raise
        finally:
            manifest = {
                "run_id": run_id,
                "status": status,
                "profile": self.config.profile,
                "base_url": self.config.base_url,
                "model": model,
                "config_hash": _config_hash(self.config),
                "comparison_config_hash": _config_hash(self.config, comparison=True),
                "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
                "started_at": started_at,
                "finished_at": _now(),
                "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
                "stages": self.stage_records,
                "artifacts": artifacts,
                "generation_mode": self.config.generation_mode,
                "design_status": readiness,
                "call_records": self.meter.records,
                "usage_summary": self.meter.summary(),
                "stop_reason": stop_reason,
            }
            if error:
                manifest["error"] = error[:1000]
            if self.generation:
                manifest["generation"] = self.generation
            _write_json(output_dir / "run_manifest.json", manifest)
            validate_artifact(manifest, "local_run_manifest.schema.json")
        return manifest

    def estimate(self, input_path: Path) -> dict:
        """モデル探索・HTTP通信なしで、初段だけ見積もる。"""
        feature = normalize_feature_spec(input_path)
        schema = self._stage_schema("test_model", "test_model.schema.json")
        prompt = _test_model_prompt(feature)
        if self.config.generation_mode == "batched":
            from bb_harness.batched_generation import model_core_request

            schema, prompt = model_core_request(feature)
        estimate = estimate_input(SYSTEM_PROMPT, prompt, schema)
        caps = {
            stage: output_limit(self.config, stage)
            for stage in (
                "test_model",
                "observation_set",
                "risk_candidates",
                "manual_case_set",
                "manual_case_remainder",
                "manual_case_review",
            )
        }
        reservation = estimate + caps["test_model"]
        return {
            "generation_mode": self.config.generation_mode,
            "estimation_method": "utf8_bytes_plus_256_v1",
            "first_stage_input_estimate": estimate,
            "first_stage_reservation": reservation,
            "stage_output_limits": caps,
            "later_stage_input_estimate": None,
            "total_tokens_estimate": None,
            "token_budget": self.config.token_budget,
            "first_stage_budget_fits": self.config.token_budget is None
            or reservation <= self.config.token_budget,
            "note": "入力は推定、出力値は上限。後段・修復の入力と実際の消費量は未確定。",
        }

    def _stage_schema(self, stage_name: str, schema_name: str) -> dict:
        schema = portable_schema(schema_name)
        if stage_name == "test_model":
            for field in ("boundaries", "data_partitions", "invalid_transitions"):
                schema["properties"][field]["minItems"] = 1
            schema["required"] = list(
                dict.fromkeys(
                    schema["required"]
                    + [
                        "boundaries",
                        "valid_transitions",
                        "invalid_transitions",
                        "quality_lenses",
                    ]
                )
            )
        if stage_name in {
            "manual_case_set",
            "manual_case_remainder",
            "manual_case_review",
        }:
            schema["required"] = list(dict.fromkeys(schema["required"] + ["exploratory_charters"]))
            schema["properties"]["manual_cases"]["minItems"] = (
                3
                if self.config.generation_mode == "full"
                else 0
                if stage_name == "manual_case_remainder"
                else 1
            )
            schema["properties"]["exploratory_charters"]["minItems"] = (
                1 if self.config.generation_mode == "full" else 0
            )
            schema["properties"]["exploratory_charters"]["maxItems"] = 2

        return schema

    def _generate_artifact(
        self,
        stage_name: str,
        schema_name: str,
        prompt: str,
        *,
        normalize: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        schema = self._stage_schema(stage_name, schema_name)

        def validate(value: dict[str, Any]) -> None:
            validate_artifact(value, schema_name)
            if self.source_ids:
                _validate_source_grounding(value, self.source_ids)
            if stage_name == "test_model":
                _validate_test_model_semantics(value, feature=None)
            if stage_name in {
                "manual_case_set",
                "manual_case_remainder",
                "manual_case_review",
            }:
                if (
                    stage_name != "manual_case_remainder"
                    or self.config.generation_mode == "full"
                    or value["manual_cases"]
                ):
                    _validate_case_semantics(
                        value, compact=self.config.generation_mode == "compact"
                    )
                if hasattr(self, "coverage_model"):
                    coverage = validate_case_coverage(
                        value, self.coverage_model, self.technique_plan
                    )
                    if coverage["errors"]:
                        raise ValueError("; ".join(coverage["errors"][:5]))

        return self._generate(stage_name, schema, prompt, normalize, validate)

    def _generate_custom(
        self,
        stage_name: str,
        schema: dict[str, Any],
        prompt: str,
        normalize: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        semantic_validate: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        validator = Draft202012Validator(schema)

        def validate(value: dict[str, Any]) -> None:
            errors = sorted(validator.iter_errors(value), key=lambda item: list(item.path))
            if errors:
                raise SchemaValidationError("; ".join(error.message for error in errors[:5]))
            if semantic_validate:
                semantic_validate(value)

        return self._generate(
            stage_name, schema, prompt, normalize or (lambda value: value), validate
        )

    def _generate(
        self,
        stage_name: str,
        schema: dict[str, Any],
        prompt: str,
        normalize: Callable[[dict[str, Any]], dict[str, Any]],
        validate: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        total_elapsed = 0.0
        usage: dict[str, int] = {}
        repairs = 0
        result = self._complete(
            system=SYSTEM_PROMPT,
            user=prompt,
            schema_name=stage_name,
            schema=schema,
        )
        total_elapsed += result.elapsed_seconds
        _merge_usage(usage, result.usage)
        value = result.value
        try:
            value = normalize(value)
            validate(value)
        except (SchemaValidationError, ValueError, TypeError, KeyError) as first_error:
            self.meter.records[-1]["outcome"] = "invalid_artifact"
            repairs = 1
            repair_prompt = (
                f"次の{stage_name}は検証に失敗しました。誤りだけを修正しJSONのみ返してください。\n"
                f"検証エラー: {first_error}\n"
                f"不正な成果物: {json.dumps(value, ensure_ascii=False)}"
            )
            if self.config.generation_mode == "batched":
                repair_prompt += f"\n元の分割依頼と根拠:\n{prompt}"
            result = self._complete(
                system=SYSTEM_PROMPT,
                user=repair_prompt,
                schema_name=f"{stage_name}_repair",
                schema=schema,
            )
            total_elapsed += result.elapsed_seconds
            _merge_usage(usage, result.usage)
            value = result.value
            try:
                value = normalize(value)
                validate(value)
            except (SchemaValidationError, ValueError, TypeError, KeyError):
                self.meter.records[-1]["outcome"] = "invalid_artifact"
                self.stage_records.append(
                    {
                        "name": stage_name,
                        "elapsed_seconds": round(total_elapsed, 3),
                        "repairs": repairs,
                        "schema_valid": False,
                        "usage": usage,
                    }
                )
                raise
        self.meter.records[-1]["outcome"] = "succeeded"
        self.stage_records.append(
            {
                "name": stage_name,
                "elapsed_seconds": round(total_elapsed, 3),
                "repairs": repairs,
                "schema_valid": True,
                "usage": usage,
            }
        )
        return value

    def _complete(self, *, system: str, user: str, schema_name: str, schema: dict) -> Any:
        record = self.meter.prepare(
            schema_name, system, user, schema, output_limit(self.config, schema_name)
        )
        started = time.monotonic()
        try:
            result = self.client.complete_json(
                system=system, user=user, schema_name=schema_name, schema=schema
            )
        except Exception as exc:
            record["finish_reason"] = getattr(exc, "finish_reason", None)
            record["model"] = getattr(exc, "model", None)
            self.meter.finish(
                record,
                getattr(exc, "usage", {}),
                getattr(exc, "elapsed_seconds", time.monotonic() - started),
                getattr(exc, "failure_kind", "runtime_error"),
            )
            raise
        record["finish_reason"] = getattr(result, "finish_reason", None)
        record["model"] = result.model
        self.meter.finish(record, result.usage, result.elapsed_seconds, "returned")
        return result

    def _save_artifact(
        self,
        output_dir: Path,
        name: str,
        value: dict[str, Any],
        records: dict[str, dict[str, Any]],
    ) -> None:
        schema_name = ARTIFACT_SCHEMAS[name]
        validate_artifact(value, schema_name)
        path = output_dir / f"{name}.json"
        data = _write_json(path, value)
        records[name] = {
            "path": path.name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "schema_valid": True,
        }

    def _build_gate(
        self,
        output_dir: Path,
        feature: dict[str, Any],
        observations: dict[str, Any],
        risks: dict[str, Any],
        cases: dict[str, Any],
        *,
        evidence_path: Path | None,
        build_id: str,
        gate_profile: str,
    ) -> dict[str, Any]:
        if evidence_path is None:
            counts = {
                priority: {
                    "pass": 0,
                    "fail": 0,
                    "skip": 0,
                    "blocked": 0,
                    "unknown": 0,
                    "untested": sum(
                        1 for case in cases["manual_cases"] if case["priority"] == priority
                    ),
                    "total": sum(
                        1 for case in cases["manual_cases"] if case["priority"] == priority
                    ),
                }
                for priority in ("P0", "P1", "P2", "P3")
            }
            blocking = [risk["id"] for risk in risks["risks"] if risk["priority"] in {"P0", "P1"}]
            return {
                "feature_id": feature["feature_id"],
                "build_id": build_id,
                "status": "no_go",
                "profile": gate_profile,
                "reasons": ["手動実行証跡が未指定のためrelease判断はfail closed"],
                "evidence_summary": {
                    "evidence_binding_mode": "case_revision",
                    "manual_by_priority": counts,
                    "mandatory_observation_rate": 0,
                },
                "blocking_risks": blocking,
                "residual_risks": [risk["id"] for risk in risks["risks"]],
                "unmet_conditions": ["P0/P1 manual caseの実行証跡を収集する"],
                "required_follow_up": ["bb-harness gateで実行証跡を再評価する"],
            }
        gate_path = output_dir / "gate_decision.json"
        args = [
            "--evidence",
            str(evidence_path),
            "--risk",
            str(output_dir / "risk_register.json"),
            "--cases",
            str(output_dir / "manual_case_set.json"),
            "--feature",
            str(output_dir / "feature_spec.json"),
            "--observations",
            str(output_dir / "observation_set.json"),
            "--output",
            str(gate_path),
            "--profile",
            gate_profile,
            "--build-id",
            build_id,
        ]
        if evaluate_gate_main(args) != 0:
            raise LocalPipelineError("Existing Gate engine rejected the supplied evidence")
        return json.loads(gate_path.read_text(encoding="utf-8"))


def normalize_feature_spec(path: Path) -> dict[str, Any]:
    """Markdown intakeを根拠ID付きfeature_specへ正規化する。"""
    feature = ingest_markdown_spec(path)
    text = read_markdown(path)
    sections = {
        normalize_section_name(name): items
        for name, items in extract_markdown_sections(text).items()
    }
    h1 = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if h1:
        feature["title"] = h1.group(1).strip()
    stem = re.sub(r"\.input$", "", path.stem, flags=re.IGNORECASE)
    feature["feature_id"] = re.sub(r"[^A-Z0-9]+", "-", stem.upper()).strip("-") or (
        fallback_feature_id(path.stem)
    )
    raw_feature = sections.get("feature", [])
    if raw_feature:
        feature["summary"] = " ".join(raw_feature)
    source_refs = [
        {"id": f"SPEC-{feature['feature_id']}", "kind": "spec", "excerpt": feature["title"]}
    ]
    for field, prefix, kind in (
        ("acceptance_criteria", "AC", "ac"),
        ("business_rules", "BR", "rule"),
    ):
        normalized: list[str] = []
        for index, item in enumerate(feature.get(field, []), 1):
            match = re.match(rf"^({prefix}-\d+)\s*:\s*(.+)$", item, re.IGNORECASE)
            source_id = match.group(1).upper() if match else f"{prefix}-{index}"
            statement = match.group(2).strip() if match else item
            normalized.append(f"{source_id}: {statement}")
            source_refs.append({"id": source_id, "kind": kind, "excerpt": statement})
        if normalized:
            feature[field] = normalized
    environments = sections.get("environments", [])
    if environments:
        feature["devices"] = environments
    for index, item in enumerate(sections.get("existing_evidence", []), 1):
        source_refs.append({"id": f"AUTO-{index}", "kind": "auto_test", "excerpt": item})
    feature["source_refs"] = source_refs
    validate_artifact(feature, "feature_spec.schema.json")
    return feature


def portable_schema(schema_name: str) -> dict[str, Any]:
    """外部$refを同梱したAPI送信用schemaを返す。"""
    schema, _ = load_schema(schema_name)
    result = copy.deepcopy(schema)
    shared, _ = load_schema("shared_defs.schema.json")
    definitions = shared.get("$defs", {})
    selected = {}

    def include_refs(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                include_refs(item)
        elif isinstance(value, list):
            for item in value:
                include_refs(item)
        elif isinstance(value, str) and value.startswith("shared_defs.schema.json#/$defs/"):
            key = value.rsplit("/", 1)[-1]
            if key not in selected:
                selected[key] = copy.deepcopy(definitions[key])
                include_refs(selected[key])

    include_refs(result)
    result.setdefault("$defs", {})["shared"] = selected

    def replace(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, str) and value.startswith("shared_defs.schema.json#/$defs/"):
            return "#/$defs/shared/" + value.rsplit("/", 1)[-1]
        return value

    return replace(result)


def build_risk_register(feature_id: str, candidates: dict[str, Any]) -> dict[str, Any]:
    """モデルの因子候補からscoreとpriorityを決定的に算出する。"""
    risks = []
    for index, item in enumerate(candidates["risks"], 1):
        impact = int(item["impact"])
        likelihood = int(item["likelihood"])
        factors = {
            "detectability_difficulty": int(item["detectability_difficulty"]),
            "change_surface": int(item["change_surface"]),
            "externality": int(item["externality"]),
            "privilege": int(item["privilege"]),
            "auto_coverage_credit": int(item["automation_credit"]),
        }
        raw = (
            4 * impact * likelihood
            + 2 * factors["detectability_difficulty"]
            + 2 * factors["change_surface"]
            + 2 * factors["externality"]
            + 2 * factors["privilege"]
            - 2 * factors["auto_coverage_credit"]
        )
        score = round(min(100, raw * 100 / 124), 1)
        priority = "P0" if score >= 70 else "P1" if score >= 55 else "P2" if score >= 35 else "P3"
        risks.append(
            {
                "id": f"RISK-{index:02d}",
                "scenario": str(item["scenario"]),
                "impact": impact,
                "likelihood": likelihood,
                "modifiers": [f"{key}={value}" for key, value in factors.items()],
                "score": score,
                "priority": priority,
                "rationale": str(item["rationale"]),
                "trace_to": list(dict.fromkeys(item["observation_ids"])),
            }
        )
    result = {"feature_id": feature_id, "risks": risks}
    validate_artifact(result, "risk_register.schema.json")
    return result


def build_effort_plan(feature_id: str, cases: dict[str, Any]) -> dict[str, Any]:
    """case/charter見積りから工数を決定的に積み上げる。"""
    execution_minutes = sum(
        float(item.get("estimate_minutes", 10)) for item in cases["manual_cases"]
    )
    execution_minutes += sum(
        float(item.get("estimate_minutes", 30)) for item in cases.get("exploratory_charters", [])
    )
    execution = round(execution_minutes / 60, 2)
    prep = round(max(0.5, execution * 0.2), 2)
    evidence = round(max(0.25, execution * 0.15), 2)
    review = round(max(0.25, execution * 0.15), 2)
    cleanup = round(max(0.1, execution * 0.05), 2)
    subtotal = prep + execution + evidence + review + cleanup
    buffer_percent = 20
    total = round(subtotal * (1 + buffer_percent / 100), 2)
    phases = [
        {"phase_name": "prep", "activities": ["データ・環境準備"], "estimate_hours": prep},
        {
            "phase_name": "execution",
            "activities": ["scripted caseとcharter実行"],
            "estimate_hours": execution,
        },
        {"phase_name": "evidence", "activities": ["観測証跡の保存"], "estimate_hours": evidence},
        {"phase_name": "review", "activities": ["結果・残余リスク確認"], "estimate_hours": review},
        {"phase_name": "cleanup", "activities": ["テストデータ後始末"], "estimate_hours": cleanup},
    ]
    result = {
        "feature_id": feature_id,
        "phases": phases,
        "total_estimate_hours": total,
        "retry_buffer_percent": buffer_percent,
        "execution_order": [item["tc_id"] for item in cases["manual_cases"]]
        + [item["id"] for item in cases.get("exploratory_charters", [])],
    }
    validate_artifact(result, "effort_plan.schema.json")
    return result


def build_release_brief(
    feature: dict[str, Any], gate: dict[str, Any], risks: dict[str, Any]
) -> dict[str, Any]:
    high = [risk["id"] for risk in risks["risks"] if risk["priority"] in {"P0", "P1"}]
    result = {
        "feature_id": feature["feature_id"],
        "title": f"{feature['title']} Go/No-Go brief",
        "decision": gate["status"],
        "summary": f"実行証跡に基づくGate結果は{gate['status']}。" + " ".join(gate["reasons"][:2]),
        "evidence": [
            f"manual evidence: {gate['evidence_summary']['manual_by_priority']}",
            f"mandatory observation rate: {gate['evidence_summary']['mandatory_observation_rate']}%",
        ],
        "residual_risks": gate.get("residual_risks", high),
        "required_follow_up": gate.get("required_follow_up", []),
        "generated_at": _now(),
    }
    validate_artifact(result, "release_brief.schema.json")
    return result


def lint_design(
    feature: dict[str, Any],
    model: dict[str, Any],
    observations: dict[str, Any],
    risks: dict[str, Any],
    cases: dict[str, Any],
    effort: dict[str, Any],
) -> dict[str, Any]:
    """70点阻害要因を決定的に検査する。"""
    errors: list[str] = []
    warnings: list[str] = []
    source_ids = {item["id"] for item in feature["source_refs"]}
    observation_ids = {item["id"] for item in observations["observations"]}
    risk_ids = {item["id"] for item in risks["risks"]}
    for case in cases["manual_cases"]:
        if case["priority"] in {"P0", "P1"}:
            if not case.get("oracle", {}).get("refs"):
                errors.append(f"{case['tc_id']}: P0/P1 oracle refs missing")
            if not case.get("source_ref", {}).get("refs"):
                errors.append(f"{case['tc_id']}: P0/P1 source_ref missing")
        unknown_oracles = set(case.get("oracle", {}).get("refs", [])) - source_ids
        if unknown_oracles:
            errors.append(f"{case['tc_id']}: unknown oracle refs {sorted(unknown_oracles)}")
        trace = set(case.get("trace_to", []))
        if not trace & observation_ids:
            errors.append(f"{case['tc_id']}: observation trace missing")
        if not trace & risk_ids:
            errors.append(f"{case['tc_id']}: risk trace missing")
        if any(re.search(r"正しく|適切に|問題なく", item) for item in case["expected_results"]):
            warnings.append(f"{case['tc_id']}: expected result may be non-observable")
    case_ids = {case["tc_id"] for case in cases["manual_cases"]}
    for risk in risks["risks"]:
        if not set(risk.get("trace_to", [])) & case_ids:
            warnings.append(f"{risk['id']}: uncovered risk; scripted case mapping missing")
    text = json.dumps(feature, ensure_ascii=False).lower()
    if _is_stateful(text) and not model.get("invalid_transitions"):
        errors.append("stateful feature: invalid transition missing")
    if _is_auth(text) and not any(
        "ownership" in item.lower() or "所有" in item for item in model["role_matrix"]
    ):
        errors.append("authorization feature: ownership context missing")
    if _is_mobile(feature):
        matrix = cases.get("platform_matrix", [])
        present = {(item["platform"], item["lifecycle"], item["network"]) for item in matrix}
        if not any(lifecycle == "background_resume" for _, lifecycle, _ in present):
            errors.append("mobile feature: background_resume matrix missing")
        if not any(network in {"offline", "slow"} for _, _, network in present):
            errors.append("mobile feature: adverse network matrix missing")
        if not any("permission" in item for item in matrix):
            errors.append("mobile feature: permission matrix missing")
    race_sensitive = any(marker in text for marker in ("二重", "同時", "重複", "再試行", "競合"))
    race_corpus = json.dumps(
        {
            "model": model,
            "cases": cases.get("manual_cases", []),
            "charters": cases.get("exploratory_charters", []),
        },
        ensure_ascii=False,
    )
    if race_sensitive and not any(
        marker in race_corpus for marker in ("二重", "同時", "重複", "再試行", "競合")
    ):
        errors.append("race-sensitive feature: concurrency/retry coverage missing")
    phase_sum = round(sum(float(item["estimate_hours"]) for item in effort["phases"]), 2)
    expected_total = round(phase_sum * (1 + effort["retry_buffer_percent"] / 100), 2)
    if effort["total_estimate_hours"] != expected_total:
        errors.append("effort arithmetic mismatch")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "source_oracle_trace": not any("oracle" in item or "trace" in item for item in errors),
            "boundary": bool(model.get("boundaries")),
            "state": not (_is_stateful(text) and not model.get("invalid_transitions")),
            "authorization": not (_is_auth(text) and any("ownership" in item for item in errors)),
            "mobile": not (
                _is_mobile(feature) and any("mobile feature" in item for item in errors)
            ),
            "race": "race-sensitive feature: concurrency/retry coverage missing" not in errors,
            "effort_arithmetic": "effort arithmetic mismatch" not in errors,
        },
    }


def score_structure(
    feature: dict[str, Any],
    model: dict[str, Any],
    observations: dict[str, Any],
    risks: dict[str, Any],
    cases: dict[str, Any],
    gate: dict[str, Any],
    lint: dict[str, Any],
) -> dict[str, Any]:
    """最終rubricではなく、構造的な下限を確認するpreflight点を返す。"""
    coverage_fields = [
        "data_partitions",
        "rule_columns",
        "states",
        "role_matrix",
        "regression_edges",
        "quality_lenses",
    ]
    coverage = round(
        20 * sum(bool(model.get(key)) for key in coverage_fields) / len(coverage_fields)
    )
    observation = round(
        15
        * sum(
            bool(item.get("source_refs")) and isinstance(item.get("mandatory"), bool)
            for item in observations["observations"]
        )
        / len(observations["observations"])
    )
    risk = (
        15 if all(item.get("rationale") and item.get("trace_to") for item in risks["risks"]) else 8
    )
    manual = 20 if not any("oracle" in item or "trace" in item for item in lint["errors"]) else 8
    charters = cases.get("exploratory_charters", [])
    charter = (
        10
        if charters
        and all(item.get("questions") and item.get("estimate_minutes") for item in charters)
        else 4
    )
    gate_score = 15 if gate["status"] == "no_go" or gate["evidence_summary"] else 0
    communication = 5
    categories = {
        "coverage_model": coverage,
        "observation_quality": observation,
        "risk_quality": risk,
        "manual_cases": manual,
        "exploratory_charters": charter,
        "gate_decision": gate_score,
        "communication": communication,
    }
    automatic_fails = list(lint["errors"])
    return {
        "kind": "structural_preflight_not_independent_rubric_score",
        "score": sum(categories.values())
        if not automatic_fails
        else min(69, sum(categories.values())),
        "categories": categories,
        "automatic_fails": automatic_fails,
        "source_feature_id": feature["feature_id"],
    }


def render_markdown(
    feature: dict[str, Any],
    model: dict[str, Any],
    observations: dict[str, Any],
    risks: dict[str, Any],
    cases: dict[str, Any],
    effort: dict[str, Any],
    gate: dict[str, Any],
    brief: dict[str, Any],
    *,
    coverage: dict[str, Any] | None = None,
) -> str:
    lines = [f"# {feature['title']} 手動ブラックボックステスト設計", "", "## Coverage model", ""]
    for label, key in (
        ("Flows", "flows"),
        ("Data partitions", "data_partitions"),
        ("Boundaries", "boundaries"),
        ("Rules", "rule_columns"),
        ("States", "states"),
        ("Invalid transitions", "invalid_transitions"),
        ("Roles", "role_matrix"),
        ("Regression", "regression_edges"),
    ):
        lines.extend([f"### {label}", "", *[f"- {item}" for item in model.get(key, [])], ""])
    lines.extend(["## Observations", ""])
    for item in observations["observations"]:
        lines.append(
            f"- {item['id']} [{'mandatory' if item['mandatory'] else 'optional'}]: {item['title']}"
        )
    lines.extend(
        ["", "## Risks", "", "| ID | Priority | Score | Scenario |", "|---|---:|---:|---|"]
    )
    for item in risks["risks"]:
        lines.append(
            f"| {item['id']} | {item['priority']} | {item['score']} | {item['scenario']} |"
        )
    lines.extend(["", "## Manual cases", ""])
    for item in cases["manual_cases"]:
        lines.extend(
            [
                f"### {item['tc_id']} {item['title']} ({item['priority']})",
                "",
                f"- Oracle: {item['oracle']['type']} / {', '.join(item['oracle']['refs'])}",
                f"- Trace: {', '.join(item['trace_to'])}",
                f"- Estimate: {item.get('estimate_minutes', 0)} min",
                "- Steps: " + " / ".join(item["steps"]),
                "- Expected: " + " / ".join(item["expected_results"]),
                "",
            ]
        )
        if item.get("coverage_inputs"):
            lines.extend(
                [
                    "入力と手順・期待結果の対応:",
                    "",
                    "```json",
                    json.dumps(item["coverage_inputs"], ensure_ascii=False, indent=2),
                    "```",
                    "",
                ]
            )
    if coverage is not None:
        design = coverage["design"]
        execution = coverage["execution"]
        lines.extend(
            [
                "## 技法別被覆（shadow）",
                "",
                f"- 設計済み: {design['covered_by_cases']} / {design['required_feasible']}",
                f"- 実施済み: {execution['executed']} / {execution['required_feasible']}",
                f"- 合格: {execution['passed']}（失敗も実施済みに計上）",
                f"- 未解決: {len(coverage['unknown_ids'])}、選択不能: {len(coverage['blocked_selections'])}",
                "- [技法計画](technique_plan.json) / [被覆の詳細・不足項目](coverage_report.json)",
                "- 型付きモデルの範囲に対する値。新しい被覆指標はGate判断の参考値です。",
                "",
            ]
        )
    lines.extend(["## Exploratory charters", ""])
    for item in cases.get("exploratory_charters", []):
        lines.append(
            f"- {item['id']} ({item.get('estimate_minutes', 0)} min): {item['title']} — {item['scope']}"
        )
    lines.extend(
        [
            "",
            "## Effort",
            "",
            f"- Total: {effort['total_estimate_hours']} hours (retry buffer {effort['retry_buffer_percent']}%)",
            "",
            "## Gate",
            "",
            f"- Status: {gate['status']}",
            *[f"- {reason}" for reason in gate["reasons"]],
            "",
            "## Go/No-Go brief",
            "",
            brief["summary"],
            "",
        ]
    )
    return "\n".join(lines)


def _normalize_test_model(value: dict[str, Any], feature: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(value)
    value["feature_id"] = feature["feature_id"]
    return value


def _normalize_observations(value: dict[str, Any], feature: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(value)
    value["feature_id"] = feature["feature_id"]
    raw_items = value.get("observations")
    if not isinstance(raw_items, list):
        return value
    for index, item in enumerate(raw_items, 1):
        if not isinstance(item, dict):
            continue
        category = re.sub(r"[^A-Z]", "", str(item.get("id", "GEN")).upper()) or "GEN"
        category = category.replace("OBS", "")[:12] or "GEN"
        item["id"] = f"OBS-{category}-{index:02d}"
    return value


def _normalize_risk_candidates(
    value: dict[str, Any], feature_id: str, observations: dict[str, Any]
) -> dict[str, Any]:
    """Schema準拠候補のIDだけをhost管理値へ正規化する。"""
    del observations
    value = copy.deepcopy(value)
    value["feature_id"] = feature_id
    raw_risks = value.get("risks")
    if not isinstance(raw_risks, list):
        return value
    for index, item in enumerate(raw_risks, 1):
        if isinstance(item, dict):
            item["id"] = f"candidate-{index}"
    return value


def _normalize_cases(
    value: dict[str, Any],
    feature: dict[str, Any],
    observations: dict[str, Any],
    risks: dict[str, Any],
) -> dict[str, Any]:
    value = copy.deepcopy(value)
    source_excerpts = {item["id"]: item.get("excerpt", "") for item in feature["source_refs"]}
    del observations
    value["feature_id"] = feature["feature_id"]
    raw_cases = value.get("manual_cases")
    if not isinstance(raw_cases, list):
        return value
    for index, case in enumerate(raw_cases, 1):
        if not isinstance(case, dict):
            continue
        case["tc_id"] = f"TC-{index:03d}"
        trace = case.get("trace_to", [])
        linked_priorities = [
            risk["priority"]
            for risk in risks["risks"]
            if isinstance(trace, list) and risk["id"] in trace
        ]
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        if linked_priorities:
            case["priority"] = min(linked_priorities, key=priority_order.__getitem__)
        oracle = case.get("oracle")
        if not isinstance(oracle, dict) or not isinstance(oracle.get("refs"), list):
            continue
        case_text = case.get("title", "") + " " + " ".join(case.get("expected_results", []))
        negative_auth = any(
            marker in case_text for marker in ("他者", "他人", "権限外", "unauthorized")
        )
        oracle_source = " ".join(
            source_excerpts[ref] for ref in oracle["refs"] if ref in source_excerpts
        )
        explicit_negative = any(
            marker in oracle_source
            for marker in ("できない", "禁止", "自身", "自分", "他者", "他人", "権限外")
        )
        if oracle.get("type") == "specified" and negative_auth and not explicit_negative:
            oracle["type"] = "human"
        source_ref = case.get("source_ref")
        if isinstance(source_ref, dict) and isinstance(source_ref.get("refs"), list):
            if source_ref["refs"] and all(ref.startswith("AC-") for ref in source_ref["refs"]):
                source_ref["type"] = "acceptance"
            elif source_ref["refs"] and all(ref.startswith("BR-") for ref in source_ref["refs"]):
                source_ref["type"] = "requirement"
    raw_charters = value.get("exploratory_charters")
    if isinstance(raw_charters, list):
        for index, charter in enumerate(raw_charters, 1):
            if isinstance(charter, dict):
                charter["id"] = f"CHARTER-{index:03d}"
    if _is_mobile(feature) and not value.get("platform_matrix"):
        value["platform_matrix"] = [
            {
                "platform": "iOS",
                "lifecycle": "background_resume",
                "network": "offline",
                "permission": "denied",
            },
            {
                "platform": "Android",
                "lifecycle": "background_resume",
                "network": "slow",
                "permission": "granted",
            },
            {
                "platform": "iOS",
                "lifecycle": "foreground",
                "network": "online",
                "permission": "granted",
            },
        ]
    if _is_auth(json.dumps(feature, ensure_ascii=False).lower()) and not value.get("role_matrix"):
        value["role_matrix"] = [
            {
                "actor_role": "owner",
                "target_role": "admin",
                "action": "can_change",
                "ownership_context": "own_workspace",
            },
            {
                "actor_role": "admin",
                "target_role": "owner",
                "action": "cannot_change",
                "ownership_context": "own_workspace",
            },
            {
                "actor_role": "viewer",
                "target_role": "admin",
                "action": "cannot_change",
                "ownership_context": "other_workspace",
            },
        ]
    return value


def _merge_case_sets(
    primary: dict[str, Any],
    remainder: dict[str, Any],
    feature: dict[str, Any],
    observations: dict[str, Any],
    risks: dict[str, Any],
) -> dict[str, Any]:
    """IDと表示名以外が一致するケースだけを統合し、異なる被覆を保持する。"""
    result: dict[str, Any] = {
        "feature_id": feature["feature_id"],
        "manual_cases": [],
        "exploratory_charters": [],
    }
    seen_cases: set[str] = set()
    for item in primary.get("manual_cases", []) + remainder.get("manual_cases", []):
        key = json.dumps(
            {k: v for k, v in item.items() if k not in {"tc_id", "title"}},
            sort_keys=True,
            ensure_ascii=False,
        )
        if key not in seen_cases:
            seen_cases.add(key)
            result["manual_cases"].append(item)
    seen_charters: set[str] = set()
    for item in primary.get("exploratory_charters", []) + remainder.get("exploratory_charters", []):
        key = json.dumps(
            {k: v for k, v in item.items() if k not in {"id", "title"}},
            sort_keys=True,
            ensure_ascii=False,
        )
        if key not in seen_charters:
            seen_charters.add(key)
            result["exploratory_charters"].append(item)
    for matrix_name in ("platform_matrix", "role_matrix"):
        unique: dict[str, dict[str, Any]] = {}
        for item in primary.get(matrix_name, []) + remainder.get(matrix_name, []):
            unique[json.dumps(item, sort_keys=True, ensure_ascii=False)] = item
        if unique:
            result[matrix_name] = list(unique.values())
    return _normalize_cases(result, feature, observations, risks)


def _preserve_review_cases(
    draft: dict, reviewed: dict, feature: dict, observations: dict, risks: dict
) -> dict:
    """レビューで消えた実行条件を保持し、oracle・期待結果の訂正は採用する。"""

    def identity(case: dict) -> str:
        return json.dumps(
            {
                key: value
                for key, value in case.items()
                if key
                not in {
                    "tc_id",
                    "title",
                    "oracle",
                    "source_ref",
                    "expected_results",
                    "priority",
                    "estimate_minutes",
                }
            },
            sort_keys=True,
            ensure_ascii=False,
        )

    reviewed_keys = {identity(case) for case in reviewed["manual_cases"]}
    missing = {
        **draft,
        "manual_cases": [
            case for case in draft["manual_cases"] if identity(case) not in reviewed_keys
        ],
    }
    return _merge_case_sets(reviewed, missing, feature, observations, risks)


def _validate_source_grounding(value: dict, source_ids: set[str]) -> None:
    for observation in value.get("observations", []):
        refs = {item["id"] for item in observation.get("source_refs", [])}
        if refs - source_ids:
            raise ValueError(f"unknown observation sources: {sorted(refs - source_ids)}")
    for case in value.get("manual_cases", []):
        refs = set(case.get("oracle", {}).get("refs", [])) | set(
            case.get("source_ref", {}).get("refs", [])
        )
        if refs - source_ids:
            raise ValueError(f"unknown oracle/source refs: {sorted(refs - source_ids)}")


def _link_risks_and_cases(risks: dict[str, Any], cases: dict[str, Any]) -> None:
    """明示されたrisk参照だけを逆引きする。観点の一致は被覆の証明にならない。"""
    risk_observations = {risk["id"]: set(risk.get("trace_to", [])) for risk in risks["risks"]}
    risk_ids = set(risk_observations)
    items = cases["manual_cases"] + cases.get("exploratory_charters", [])
    for risk in risks["risks"]:
        linked = []
        for item in items:
            if risk["id"] in item.get("trace_to", []):
                linked.append(item.get("tc_id") or item.get("id"))
        risk["trace_to"] = (
            sorted(
                risk_observations[risk["id"]]
                - risk_ids
                - {item.get("tc_id") or item.get("id") for item in items}
            )
            + linked
        )
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    priority_by_risk = {risk["id"]: risk["priority"] for risk in risks["risks"]}
    for case in cases["manual_cases"]:
        linked_priorities = [
            priority_by_risk[item] for item in case["trace_to"] if item in priority_by_risk
        ]
        if linked_priorities:
            case["priority"] = min(linked_priorities, key=priority_order.__getitem__)


def _test_model_prompt(feature: dict[str, Any]) -> str:
    return """次のfeature_specから、caseを書く前にcoverage modelを作成してください。
flowsは利用者の操作経路、data_partitionsは項目名ではなく有効/無効・あり/なし等の同値クラスとして書きます。
rule_columnsは条件と結果の組合せ、boundariesは具体的な境界の直前/一致/直後として書きます。
data/rule/boundary/state(valid/invalid)/role+ownership/regression/quality lensを分解してください。
statefulなら競合・二重実行・終端後の不正遷移、mobileならOS/lifecycle/network/permissionを含めます。
数値境界はparameters(type/unit/step)、domain_models(variable_ids/partition_predicate/borders)へ構造化します。
各borderはid/operator/predicate/axis/anchorを持ち、anchorには全variableの具体値を置きます。式は許可されたASTだけを使います。
有限選択値はcombination_models、状態はstate_models(event/guard/actions/context)、条件表はdecision_tablesへ分解します。
組み合わせ・決定表で参照するparameterはparametersに有限valuesを明記します。空のparametersから参照を発明しません。
ExprNodeの定数は{"const":true}、変数は{"var":"x"}です。const/var/call/ifをopにしません。状態actionsはcontext変数の更新だけで、API呼出ではありません。
状態はfrom/toで表し、context変数に不要に複製しません。guardは状態以外の追加条件です。追加条件がなければguard/actions/contextsを省略できます。条件変数が必要なら各対象遷移の仕様に基づく初期contextsを全て列挙します。
各モデルに実在するsource_refsとcoverage_criterionを付けます。不明な精度・条件・oracleは発明せず未構造化のまま残します。
根拠のない実装詳細は作らないでください。\nfeature_spec:\n""" + json.dumps(
        feature, ensure_ascii=False
    )


def _observation_prompt(feature: dict[str, Any], model: dict[str, Any]) -> str:
    return """feature_specとtest_modelから、根拠付き観点を作成してください。
観点は表示上まとめても、異なる境界点・条件・連続遷移の被覆項目を保持します。件数の上限を理由に必須項目を削除しません。
IDはOBS-STATE-01形式。P0/P1相当、境界、不正遷移、権限、競合、復旧はmandatoryにします。
source_refsはfeature_specに実在するオブジェクトだけをそのまま使用してください。\n入力:\n""" + json.dumps(
        {"feature_spec": feature, "test_model": model}, ensure_ascii=False
    )


def _risk_prompt(
    feature: dict[str, Any], model: dict[str, Any], observations: dict[str, Any],
    *, count_hint: str = "3〜8件",
) -> str:
    return f"""失敗シナリオを{count_hint}に絞り、各因子を独立評価してください。
impact/likelihoodは1..5、modifierは0..2。自動テスト根拠が明記された時だけautomation_creditを1以上にします。
UI文言だけの不具合は通常impact 1〜2、在庫/金額/権限/重複副作用はimpact 4〜5とします。
変更対象かつ自動テスト未網羅の経路はlikelihood 4、変更対象で網羅済みなら3を目安にします。
外部serviceや競合をまたぐ場合はchange_surface/externality/detectabilityを根拠に応じて2とします。
hostは raw=4*(impact*likelihood)+2D+2C+2X+2P-2A を0..100へ正規化し、55以上をP1にします。
業務整合性・権限・重複副作用の主要riskが根拠なく全てP2/P3にならないよう較正してください。
priorityやscoreは計算せず、observation_idsは実在IDを使います。P0乱発を避けます。\n入力:\n""" + json.dumps(
        {"feature_spec": feature, "test_model": model, "observations": observations},
        ensure_ascii=False,
    )


def _case_prompt(
    feature: dict[str, Any],
    model: dict[str, Any],
    observations: dict[str, Any],
    risks: dict[str, Any],
    *,
    focus: str,
    existing: dict[str, Any] | None = None,
) -> str:
    plan = build_technique_plan(feature, model, observations, risks)
    gaps = validate_case_coverage(existing, model, plan) if existing else None
    return f"""manual caseとexploratory charterを作成してください。
今回のfocus: {focus}
technique_planのobligationsを保持し、coverage_inputsにmodel_ref、具体的data/path/sequence、step_refsとexpected_result_refs（1始まり）を付けます。
coverage_input_examplesを有効な入力形式の記入例として使い、本文へ対応付けます。決定表はaction_checksも必要です。
coverage_obligation_idsだけを申告しても被覆になりません。補完時は未被覆IDを優先し、予算超過なら未被覆を残します。
focus対象のriskをscripted caseで覆い、各caseに実在するAC/BRのoracle refsとsource_ref、OBSとRISK両方のtrace_to、観測可能なexpected_results、estimate_minutesを付けます。
正常系だけでなく境界、不正状態遷移、二重/同時操作、失敗時の副作用不発を含めます。
優先度はtrace先riskの最高priorityに合わせ、根拠なくP0へ上げません。
仕様にない正確なメッセージ文、HTTP status、rollback方式をspecified oracleとして発明しません。不明点はhuman/implicit oracleまたはcharterへ移します。
仕様でoracleが薄い復旧・競合はscope/questions/timebox付きcharterにします。
権限ならownership、mobileならiOS/Android x lifecycle x network x permissionのmatrixを含めます。\n入力:\n""" + json.dumps(
        {
            "feature_spec": feature,
            "test_model": model,
            "observations": observations,
            "risks": risks,
            "already_selected_do_not_duplicate": existing,
            "technique_plan": plan,
            "coverage_input_examples": coverage_input_examples(
                model, [item for group in plan["obligation_sets"] for item in group["obligations"]]
            ),
            "coverage_validation": gaps,
        },
        ensure_ascii=False,
    )


def _case_review_prompt(
    feature: dict[str, Any],
    model: dict[str, Any],
    observations: dict[str, Any],
    risks: dict[str, Any],
    draft: dict[str, Any],
) -> str:
    return """draft manual_case_setをセルフレビューし、修正後の全体を返してください。
確認項目:
1. sourceにない正確な文言、HTTP status、rollback/内部実装をspecified oracleとして発明していない。
2. 各caseのpriorityはtrace先riskの最高priorityと一致し、P0/P1を乱発していない。
3. oracle refsとsource_refはfeature_specに実在し、OBSとRISKのtraceが両方ある。
4. expected_resultsは画面、状態、件数、副作用の有無として観測可能である。
5. 正常、境界、不正遷移、二重/同時操作、部分失敗をriskに応じて覆う。
6. 根拠が薄い競合・復旧はhuman oracleまたはtimebox付きcharterとして扱う。
異なる入力・前提・経路・期待結果・被覆項目を持つcaseは同名でも保持してください。統合後も全被覆項目を実際に満たす必要があります。JSON以外は返しません。\n入力:\n""" + json.dumps(
        {
            "feature_spec": feature,
            "test_model": model,
            "observations": observations,
            "risks": risks,
            "draft_manual_case_set": draft,
        },
        ensure_ascii=False,
    )


def _is_stateful(text: str) -> bool:
    return any(word in text for word in ("状態", "state", "送信中", "復帰", "cancel", "role"))


def _validate_test_model_semantics(
    value: dict[str, Any], feature: dict[str, Any] | None = None
) -> None:
    if not value.get("boundaries") or any(
        item == "仕様に現れる直前/直後および最小/最大の境界" for item in value["boundaries"]
    ):
        raise SchemaValidationError("boundaries must name concrete before/at/after values")
    if not value.get("data_partitions"):
        raise SchemaValidationError("data_partitions must contain concrete equivalence classes")
    if not value.get("invalid_transitions"):
        raise SchemaValidationError("invalid_transitions must be explicit")
    if feature and _is_auth(json.dumps(feature, ensure_ascii=False).lower()):
        role_text = " ".join(value.get("role_matrix", [])).lower()
        if not any(
            marker in role_text
            for marker in ("ownership", "own_workspace", "other_workspace", "自分", "他")
        ):
            raise SchemaValidationError("authorization model must include ownership context")


def _validate_case_semantics(value: dict[str, Any], *, compact: bool = False) -> None:
    minimum = 1 if compact else 3
    if len(value.get("manual_cases", [])) < minimum:
        raise SchemaValidationError(f"at least {minimum} scripted cases are required")
    if not compact and not value.get("exploratory_charters"):
        raise SchemaValidationError("at least one exploratory charter is required")


def _validate_risk_observations(value: dict[str, Any], observations: dict[str, Any]) -> None:
    mandatory = {item["id"] for item in observations["observations"] if item.get("mandatory")}
    covered = {
        observation_id for risk in value["risks"] for observation_id in risk["observation_ids"]
    }
    unknown = sorted(covered - {item["id"] for item in observations["observations"]})
    if unknown:
        raise SchemaValidationError("unknown observations in risk analysis: " + ", ".join(unknown))
    missing = sorted(mandatory - covered)
    if missing:
        raise SchemaValidationError(
            "mandatory observations missing from risk analysis: " + ", ".join(missing)
        )


def _validate_risk_candidate_semantics(value: dict[str, Any], observations: dict[str, Any]) -> None:
    _validate_risk_observations(value, observations)
    scores = []
    for risk in value["risks"]:
        raw = (
            4 * risk["impact"] * risk["likelihood"]
            + 2 * risk["detectability_difficulty"]
            + 2 * risk["change_surface"]
            + 2 * risk["externality"]
            + 2 * risk["privilege"]
            - 2 * risk["automation_credit"]
        )
        score = min(100, raw * 100 / 124)
        scores.append(score)
    if not any(score >= 55 for score in scores):
        raise SchemaValidationError(
            "risk scale is under-calibrated: no candidate reaches P1 threshold"
        )


def _is_auth(text: str) -> bool:
    return any(word in text for word in ("role", "ロール", "権限", "owner", "admin"))


def _is_mobile(feature: dict[str, Any]) -> bool:
    devices = {str(item).lower() for item in feature.get("devices", [])}
    return bool(feature.get("mobile_contexts")) or bool(devices & {"ios", "android"})


def _write_json(path: Path, value: dict[str, Any]) -> bytes:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    return data


def _merge_usage(target: dict[str, int], usage: dict[str, Any]) -> None:
    for key, value in usage.items():
        if isinstance(value, int):
            target[key] = target.get(key, 0) + value


def _config_hash(config: LocalRuntimeConfig, *, comparison: bool = False) -> str:
    safe = asdict(config)
    safe.pop("api_key", None)
    if comparison:
        safe.pop("generation_mode", None)
    raw = json.dumps(safe, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
