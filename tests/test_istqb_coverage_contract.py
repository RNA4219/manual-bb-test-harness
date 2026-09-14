"""R3/R4の網羅母集団と境界値分析契約を固定する。"""

from __future__ import annotations

import pytest

from bb_harness.evidence_policy import artifact_contract_errors
from bb_harness.gate_engine import GateInputError, validate_coverage_contract
from bb_harness.schema_validation import SchemaValidationError, validate_artifact


def coverage_item(identifier: str = "COV-STATE-SHIPPED") -> dict[str, object]:
    return {
        "id": identifier,
        "dimension": "state",
        "technique": "state_transition",
        "applicability": "applicable",
        "mandatory": True,
        "coverage_criterion": "each_transition",
        "source_refs": [{"id": "AC-1", "kind": "ac"}],
    }


def test_test_model_requires_nonempty_structured_coverage_population() -> None:
    with pytest.raises(SchemaValidationError, match="coverage_items"):
        validate_artifact(
            {
                "feature_id": "F-1",
                "flows": [],
                "data_partitions": [],
                "rule_columns": [],
                "states": [],
                "role_matrix": [],
                "regression_edges": [],
            },
            "test_model.schema.json",
        )


def test_unknown_observation_coverage_reference_is_rejected() -> None:
    with pytest.raises(GateInputError, match="coverage_item_id"):
        validate_coverage_contract(
            {"feature_id": "F-1", "coverage_items": [coverage_item()]},
            {
                "feature_id": "F-1",
                "observations": [
                    {
                        "id": "OBS-1",
                        "coverage_item_id": "COV-NOT-DEFINED",
                        "mandatory": True,
                        "view": "black",
                    }
                ],
            },
            {"feature_id": "F-1", "manual_cases": []},
            {"feature_id": "F-1", "source_refs": [{"id": "AC-1", "kind": "ac"}]},
        )


def test_mandatory_coverage_item_requires_observation_and_case_trace() -> None:
    with pytest.raises(GateInputError, match="mandatory coverage"):
        validate_coverage_contract(
            {"feature_id": "F-1", "coverage_items": [coverage_item()]},
            {"feature_id": "F-1", "observations": []},
            {"feature_id": "F-1", "manual_cases": []},
            {"feature_id": "F-1", "source_refs": [{"id": "AC-1", "kind": "ac"}]},
        )


def test_coverage_source_reference_must_exist_in_feature_spec() -> None:
    item = coverage_item()
    item["source_refs"] = [{"id": "AC-404", "kind": "ac"}]
    with pytest.raises(GateInputError, match="source"):
        validate_coverage_contract(
            {"feature_id": "F-1", "coverage_items": [item]},
            {"feature_id": "F-1", "observations": []},
            {"feature_id": "F-1", "manual_cases": []},
            {"feature_id": "F-1", "source_refs": [{"id": "AC-1", "kind": "ac"}]},
        )


def test_three_value_boundary_requires_boundary_and_both_neighbors() -> None:
    item = coverage_item("COV-DATA-LOWER")
    item.update(
        dimension="data",
        technique="boundary_value",
        boundary_spec={
            "analysis_type": "three_value",
            "partition": "invalid x<=0 / valid 1..100",
            "boundary_value": "0",
            "included": True,
            "step": "1",
            "selected_values": ["0", "1"],
            "rationale": "0の両隣を確認する",
        },
    )

    assert any("three_value" in error for error in artifact_contract_errors(
        {"feature_id": "F-1", "coverage_items": [item]}, "test_model"
    ))


def test_three_value_boundary_accepts_non_integer_steps() -> None:
    item = coverage_item("COV-DATA-DATE")
    item.update(
        dimension="data",
        technique="boundary_value",
        boundary_spec={
            "analysis_type": "three_value",
            "partition": "申込期限の前後",
            "boundary_value": "2026-09-12",
            "included": True,
            "step": "P1D",
            "selected_values": ["2026-09-11", "2026-09-12", "2026-09-13"],
            "rationale": "日付の最小刻みは1日",
        },
    )

    assert artifact_contract_errors(
        {"feature_id": "F-1", "coverage_items": [item]}, "test_model"
    ) == []
