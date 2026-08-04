"""Fail-closed contract tests for manually skipped execution evidence."""

from __future__ import annotations

import pytest

from bb_harness.schema_validation import SchemaValidationError, validate_artifact


def evidence(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "run_id": "RUN-1",
        "tc_id": "TC-1",
        "feature_id": "FEATURE-1",
        "build_id": "build-1",
        "timestamp": "2026-08-04T11:00:00+09:00",
        "tester": "executor-a",
        "result": "pass",
    }
    value.update(overrides)
    return value


def approval(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "approval_id": "SKIP-APPROVAL-1",
        "approval_mode": "pre_execution",
        "reason_code": "not_applicable",
        "reason": "対象buildに条件が存在しない",
        "requested_by": "executor-a",
        "approved_by": "qa-owner",
        "approved_at": "2026-08-04T10:00:00+09:00",
        "risk_ids": ["RISK-1"],
    }
    value.update(overrides)
    return value


def test_unapproved_skip_is_rejected() -> None:
    with pytest.raises(SchemaValidationError, match="skip_approval"):
        validate_artifact(evidence(result="skip"), "execution_evidence.schema.json")


def test_preapproved_skip_is_valid() -> None:
    validate_artifact(
        evidence(result="skip", skip_approval=approval()),
        "execution_evidence.schema.json",
    )


def test_skip_approval_cannot_be_attached_to_pass() -> None:
    with pytest.raises(SchemaValidationError):
        validate_artifact(
            evidence(skip_approval=approval()),
            "execution_evidence.schema.json",
        )


def test_post_execution_approval_is_rejected() -> None:
    with pytest.raises(SchemaValidationError, match="pre_execution"):
        validate_artifact(
            evidence(
                result="skip",
                skip_approval=approval(approval_mode="post_execution"),
            ),
            "execution_evidence.schema.json",
        )


def test_duplicate_coverage_requires_replacement_evidence() -> None:
    with pytest.raises(SchemaValidationError, match="replacement_evidence_refs"):
        validate_artifact(
            evidence(
                result="skip",
                skip_approval=approval(reason_code="duplicate_coverage"),
            ),
            "execution_evidence.schema.json",
        )


def test_duplicate_coverage_with_replacement_evidence_is_valid() -> None:
    validate_artifact(
        evidence(
            result="skip",
            skip_approval=approval(
                reason_code="duplicate_coverage",
                replacement_evidence_refs=["RUN-2-TC-2"],
            ),
        ),
        "execution_evidence.schema.json",
    )


def test_skip_requires_traceable_risk() -> None:
    with pytest.raises(SchemaValidationError):
        validate_artifact(
            evidence(result="skip", skip_approval=approval(risk_ids=[])),
            "execution_evidence.schema.json",
        )
