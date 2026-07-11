"""Gate 2.0 acceptance tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bb_harness.gate_engine import (
    GATE_THRESHOLDS,
    GateInputError,
    artifact_for_feature,
    automation_failures,
    count_results_by_priority,
    evaluate_gate,
    extract_case_results,
    load_json,
    matching_gate_pair,
    observation_rate,
    valid_waivers,
    validate_and_select_evidence,
    validate_schema,
)

FEATURE = "FEATURE-2"
BUILD = "build-2"


def evidence(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "run_id": "RUN-1",
        "tc_id": "TC-1",
        "feature_id": FEATURE,
        "build_id": BUILD,
        "timestamp": "2026-07-11T10:00:00+09:00",
        "result": "pass",
    }
    value.update(overrides)
    return value


def valid_automation(profile: str = "standard") -> dict[str, object]:
    limits = GATE_THRESHOLDS[profile]
    return {
        "feature_id": FEATURE,
        "build_id": BUILD,
        "coverage_scope": limits["coverage_scope"],
        "coverage_percent": limits["auto_coverage"],
        "hotspot_review_percent": 100,
        "new_issues": {"blocker": 0, "critical": 0},
        "source_refs": [{"id": "CI-1", "kind": "auto_test"}],
    }


def counts(p0: str = "pass", p1: str = "pass") -> dict[str, dict[str, int]]:
    results = {
        "TC-P0": {"priority": "P0", "result": p0},
        "TC-P1": {"priority": "P1", "result": p1},
    }
    return count_results_by_priority(results)


def risk_register() -> dict[str, object]:
    return {"feature_id": FEATURE, "risks": [
        {"id": "RISK-P0", "priority": "P0", "trace_to": ["TC-P0"]},
        {"id": "RISK-1", "priority": "P1", "trace_to": ["TC-P1"]},
    ]}


def valid_waiver(*risk_ids: str) -> dict[str, object]:
    return {"feature_id": FEATURE, "build_id": BUILD, "waivers": [{
        "id": "WAIVER-1", "risk_ids": list(risk_ids), "reason": "contained",
        "owner": "qa-lead", "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "containment": "monitor", "rollback": "disable feature",
    }]}


def evaluate(
    *, manual_counts: dict[str, dict[str, int]] | None = None,
    defects: list[dict[str, object]] | None = None, feature_spec: dict[str, object] | None = None,
    automation: dict[str, object] | None = None, waiver_set: dict[str, object] | None = None,
    blocking_risks: list[str] | None = None, results: dict[str, dict[str, object]] | None = None,
    observations: dict[str, object] | None = None, risks: dict[str, object] | None = None,
) -> tuple[str, list[str], list[dict[str, object]], list[str], float]:
    effective_results = results or {
        "TC-P0": {"priority": "P0", "result": "pass", "trace_to": ["OBS-1"]},
        "TC-P1": {"priority": "P1", "result": "pass", "trace_to": ["OBS-1"]},
    }
    return evaluate_gate(
        feature_id=FEATURE, build_id=BUILD, profile="standard", counts=manual_counts or counts(),
        defects=defects or [], blocking_risks=blocking_risks or [], feature_spec=feature_spec,
        observations=observations or {"feature_id": FEATURE, "observations": [{"id": "OBS-1", "mandatory": True}]},
        automation=automation, waiver_set=waiver_set, results=effective_results,
        risk_register=risks or risk_register(),
    )


def test_unexecuted_p0_is_in_denominator_and_no_go() -> None:
    cases = {
        "manual_cases": [
            {"tc_id": "TC-P0", "priority": "P0", "trace_to": ["OBS-1"]},
        ]
    }
    result = extract_case_results([], cases)
    result_counts = count_results_by_priority(result)
    assert result_counts["P0"]["untested"] == 1
    status, reasons, _, _, _ = evaluate(
        manual_counts=result_counts,
        automation=valid_automation(),
    )
    assert status == "no_go"
    assert any("P0 pass rate" in reason for reason in reasons)


@pytest.mark.parametrize("outcome", ["fail", "blocked", "unknown", "untested"])
def test_nonpassing_p0_is_no_go(outcome: str) -> None:
    status, _, _, _, _ = evaluate(
        manual_counts=counts(p0=outcome),
        automation=valid_automation(),
    )
    assert status == "no_go"


def test_missing_automation_evidence_is_no_go() -> None:
    status, reasons, _, _, _ = evaluate(automation=None)
    assert status == "no_go"
    assert "automation evidence missing" in reasons


def test_open_critical_assumption_is_no_go() -> None:
    status, reasons, _, _, _ = evaluate(
        automation=valid_automation(),
        feature_spec={
            "assumptions": [
                {
                    "id": "ASM-1",
                    "severity": "critical",
                    "resolution_status": "open",
                }
            ]
        },
    )
    assert status == "no_go"
    assert any("critical assumptions" in reason for reason in reasons)


def test_open_blocker_defect_is_no_go() -> None:
    status, _, _, _, _ = evaluate(
        automation=valid_automation(),
        defects=[{"title": "data loss", "severity": "blocker", "status": "open"}],
    )
    assert status == "no_go"


def test_structured_waiver_can_produce_conditional_go() -> None:
    results = {
        "TC-P0": {"priority": "P0", "result": "pass", "trace_to": ["OBS-1"]},
        "TC-P1": {"priority": "P1", "result": "fail", "trace_to": ["OBS-1"]},
    }
    status, _, waivers, _, _ = evaluate(
        manual_counts=counts(p1="fail"), automation=valid_automation(),
        waiver_set=valid_waiver("RISK-1"), blocking_risks=["RISK-1"], results=results,
    )
    assert status == "conditional_go"
    assert [waiver["id"] for waiver in waivers] == ["WAIVER-1"]


@pytest.mark.parametrize(
    "mutation",
    [
        {"feature_id": "OTHER"},
        {"build_id": "OTHER"},
        {"timestamp": None},
        {"tc_id": None, "charter_id": None},
        {"tc_id": "TC-1", "charter_id": "CH-1"},
    ],
)
def test_invalid_identity_evidence_is_rejected(mutation: dict[str, object]) -> None:
    item = evidence(**mutation)
    with pytest.raises(GateInputError):
        validate_and_select_evidence([item], FEATURE, BUILD)


def test_mixed_feature_evidence_is_rejected() -> None:
    with pytest.raises(GateInputError, match="feature_id mismatch"):
        validate_and_select_evidence(
            [evidence(), evidence(tc_id="TC-2", feature_id="OTHER")],
            FEATURE,
            BUILD,
        )


def test_explicit_build_rejects_other_build_evidence() -> None:
    with pytest.raises(GateInputError, match="build_id mismatch"):
        validate_and_select_evidence(
            [evidence(), evidence(tc_id="TC-2", build_id="other-build")],
            FEATURE,
            BUILD,
        )

def test_latest_timestamp_wins() -> None:
    selected, _ = validate_and_select_evidence(
        [
            evidence(result="fail"),
            evidence(timestamp="2026-07-11T11:00:00+09:00", result="pass"),
        ],
        FEATURE,
        BUILD,
    )
    assert selected[0]["result"] == "pass"


def test_same_timestamp_duplicate_is_rejected() -> None:
    with pytest.raises(GateInputError, match="Ambiguous duplicate"):
        validate_and_select_evidence(
            [evidence(result="fail"), evidence(result="pass")],
            FEATURE,
            BUILD,
        )


@pytest.mark.parametrize("profile", ["strict", "standard", "lean"])
def test_profile_coverage_boundary(profile: str) -> None:
    automation = valid_automation(profile)
    assert automation_failures(automation, profile, FEATURE, BUILD) == []
    automation["coverage_percent"] = GATE_THRESHOLDS[profile]["auto_coverage"] - 0.1
    assert automation_failures(automation, profile, FEATURE, BUILD)


def test_json_and_timestamp_validation_errors(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(GateInputError, match="Cannot load"):
        load_json(invalid)
    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    with pytest.raises(GateInputError, match="Expected JSON object"):
        load_json(array)
    with pytest.raises(GateInputError, match="Invalid timestamp"):
        validate_and_select_evidence([evidence(timestamp="not-a-date")], FEATURE, BUILD)
    with pytest.raises(GateInputError, match="timezone"):
        validate_and_select_evidence(
            [evidence(timestamp="2026-07-11T10:00:00")], FEATURE, BUILD
        )


def test_build_inference_rejects_ambiguous_builds() -> None:
    with pytest.raises(GateInputError, match="--build-id required"):
        validate_and_select_evidence(
            [evidence(), evidence(tc_id="TC-2", build_id="build-3")], FEATURE, None
        )


def test_all_automation_policy_failures_are_reported() -> None:
    automation = valid_automation("strict")
    automation.update(
        {
            "coverage_scope": "changed",
            "coverage_percent": 0,
            "hotspot_review_percent": 0,
            "new_issues": {"blocker": 1, "critical": 1},
        }
    )
    failures = automation_failures(automation, "strict", FEATURE, BUILD)
    assert len(failures) == 5
    assert automation_failures(
        {**automation, "feature_id": "OTHER"}, "strict", FEATURE, BUILD
    ) == ["automation evidence feature/build mismatch"]


@pytest.mark.parametrize("profile", ["strict", "standard", "lean"])
def test_critical_automation_issue_is_hard_failure_for_every_profile(profile: str) -> None:
    automation = valid_automation(profile)
    automation["new_issues"] = {"blocker": 0, "critical": 1}
    assert "new critical issues exist" in automation_failures(
        automation, profile, FEATURE, BUILD
    )
    status, _, applied, unmet, _ = evaluate(
        automation=automation, waiver_set=valid_waiver("RISK-1")
    )
    assert status == "no_go"
    assert applied == []
    assert any("critical" in reason for reason in unmet)


def test_open_severe_defect_is_hard_failure_even_when_result_is_pass() -> None:
    status, _, _, _, _ = evaluate(
        automation=valid_automation(),
        defects=[{"title": "latent blocker", "severity": "blocker", "status": "open"}],
    )
    assert status == "no_go"


def test_observation_without_mandatory_items_is_complete() -> None:
    assert observation_rate({"observations": []}, {}) == 100.0


def test_invalid_waivers_are_rejected() -> None:
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    mismatch = valid_waiver("RISK-1")
    mismatch["feature_id"] = "OTHER"
    with pytest.raises(GateInputError, match="feature/build mismatch"):
        valid_waivers(mismatch, FEATURE, BUILD)
    with pytest.raises(GateInputError, match="Schema validation failed"):
        valid_waivers(
            {
                "feature_id": FEATURE,
                "build_id": BUILD,
                "waivers": [{"id": "W", "expires_at": future}],
            },
            FEATURE,
            BUILD,
        )
    with pytest.raises(GateInputError, match="Expired waiver"):
        valid_waivers(
            {
                "feature_id": FEATURE,
                "build_id": BUILD,
                "waivers": [
                    {
                        "id": "W",
                        "risk_ids": ["RISK-1"],
                        "reason": "x",
                        "owner": "x",
                        "expires_at": "2000-01-01T00:00:00+00:00",
                        "containment": "x",
                        "rollback": "x",
                    }
                ],
            },
            FEATURE,
            BUILD,
        )


def test_schema_and_discovery_ambiguity_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(GateInputError, match="Schema validation failed"):
        validate_schema({}, "gate_decision.schema.json")

    for name in ("one.risk.json", "two.risk.json"):
        (tmp_path / name).write_text(
            json.dumps({"feature_id": FEATURE}), encoding="utf-8"
        )
    for name in ("one.case.json", "two.case.json"):
        (tmp_path / name).write_text(
            json.dumps({"feature_id": FEATURE}), encoding="utf-8"
        )
    with pytest.raises(GateInputError, match="Expected one matching"):
        matching_gate_pair(tmp_path)

    for name in ("one.automation.json", "two.automation.json"):
        (tmp_path / name).write_text(
            json.dumps({"feature_id": FEATURE}), encoding="utf-8"
        )
    with pytest.raises(GateInputError, match="Multiple artifacts"):
        artifact_for_feature(tmp_path, ("*automation*.json",), FEATURE)

@pytest.mark.parametrize(
    ("profile", "expected"),
    [("strict", "no_go"), ("standard", "no_go"), ("lean", "go")],
)
def test_profile_evaluates_residual_risk(profile: str, expected: str) -> None:
    results = {
        "TC-P0": {"priority": "P0", "result": "pass", "trace_to": ["OBS-1"]},
        "TC-P1": {"priority": "P1", "result": "pass", "trace_to": ["OBS-1"]},
    }
    status, reasons, _, _, _ = evaluate_gate(
        feature_id=FEATURE,
        build_id=BUILD,
        profile=profile,
        counts=counts(),
        defects=[],
        blocking_risks=[],
        residual_risks=["RISK-P2: cosmetic degradation"],
        feature_spec=None,
        observations={"observations": [{"id": "OBS-1", "mandatory": True}]},
        automation=valid_automation(profile),
        waiver_set=None,
        results=results,
    )
    assert status == expected
    if profile != "lean":
        assert any("residual risks exceed" in reason for reason in reasons)



@pytest.mark.parametrize("p0_outcome", ["fail", "blocked", "unknown", "untested"])
def test_waiver_never_overrides_p0_failure(p0_outcome: str) -> None:
    status, _, applied, unmet, _ = evaluate(
        manual_counts=counts(p0=p0_outcome),
        automation=valid_automation(),
        waiver_set=valid_waiver("RISK-P0"),
    )
    assert status == "no_go"
    assert applied == []
    assert any("P0" in item for item in unmet)


@pytest.mark.parametrize(
    "automation",
    [None, {**valid_automation(), "coverage_percent": 74.9}],
)
def test_waiver_never_overrides_automation_failure(
    automation: dict[str, object] | None,
) -> None:
    status, _, applied, unmet, _ = evaluate(
        automation=automation,
        waiver_set=valid_waiver("RISK-1"),
    )
    assert status == "no_go"
    assert applied == []
    assert any("automation" in item for item in unmet)


def test_unrelated_waiver_cannot_cover_p1_failure() -> None:
    results = {
        "TC-P0": {"priority": "P0", "result": "pass", "trace_to": ["OBS-1"]},
        "TC-P1": {"priority": "P1", "result": "fail", "trace_to": ["OBS-1"]},
    }
    status, _, applied, unmet, _ = evaluate(
        manual_counts=counts(p1="fail"),
        automation=valid_automation(),
        waiver_set=valid_waiver("RISK-OTHER"),
        results=results,
    )
    assert status == "no_go"
    assert applied == []
    assert any("waiver missing" in item for item in unmet)


def test_traceable_mandatory_observation_waiver_is_conditional_go() -> None:
    results = {
        "TC-P0": {"priority": "P0", "result": "pass", "trace_to": ["OBS-1"]},
        "TC-P1": {"priority": "P1", "result": "pass", "trace_to": ["OBS-1"]},
        "TC-P2": {"priority": "P2", "result": "untested", "trace_to": ["OBS-MISS"]},
    }
    status, _, waivers, _, _ = evaluate(
        automation=valid_automation(),
        waiver_set=valid_waiver("RISK-OBS"),
        results=results,
        observations={
            "feature_id": FEATURE,
            "observations": [{"id": "OBS-MISS", "mandatory": True}],
        },
        risks={
            "feature_id": FEATURE,
            "risks": [{"id": "RISK-OBS", "priority": "P1", "trace_to": ["TC-P2"]}],
        },
    )
    assert status == "conditional_go"
    assert [waiver["id"] for waiver in waivers] == ["WAIVER-1"]


def test_untraceable_mandatory_observation_is_no_go() -> None:
    results = {
        "TC-P0": {"priority": "P0", "result": "pass", "trace_to": ["OBS-1"]},
        "TC-P1": {"priority": "P1", "result": "pass", "trace_to": ["OBS-1"]},
        "TC-P2": {"priority": "P2", "result": "untested", "trace_to": ["OBS-MISS"]},
    }
    status, _, applied, unmet, _ = evaluate(
        automation=valid_automation(),
        waiver_set=valid_waiver("RISK-OTHER"),
        results=results,
        observations={
            "feature_id": FEATURE,
            "observations": [{"id": "OBS-MISS", "mandatory": True}],
        },
        risks={"feature_id": FEATURE, "risks": []},
    )
    assert status == "no_go"
    assert applied == []
    assert any("mandatory observations lack traceable risks" in item for item in unmet)
