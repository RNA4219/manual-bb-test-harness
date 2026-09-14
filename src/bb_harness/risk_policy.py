"""ISTQB-aligned product-risk scoring policy."""

from __future__ import annotations


def calculate_risk_score(
    impact: float,
    likelihood: float,
    detectability: float,
    change_extent: float,
    external_dependency: float,
    production_history: float,
    automated_coverage_adjustment: float,
) -> int:
    """Calculate the documented product-risk score and clamp it to 0..100."""
    raw = (
        4 * (impact * likelihood)
        + 2 * detectability
        + 2 * change_extent
        + 2 * external_dependency
        + 2 * production_history
        - 2 * automated_coverage_adjustment
    )
    return round(max(0.0, min(100.0, raw * 100 / 124)))
