"""ISTQB-aligned product-risk scoring policy."""

from __future__ import annotations

RISK_FORMULA = (
    "raw = 4*(I*L) + 2*D + 2*C + 2*X + 2*P - 2*A; "
    "risk_score = round(max(0, min(100, raw * 100 / 124)))"
)


def calculate_raw_risk(
    impact: float,
    likelihood: float,
    detectability: float,
    change_extent: float,
    external_dependency: float,
    production_history: float,
    automated_coverage_adjustment: float,
) -> float:
    """Calculate the documented raw value before it is scaled to 0..100."""
    return (
        4 * (impact * likelihood)
        + 2 * detectability
        + 2 * change_extent
        + 2 * external_dependency
        + 2 * production_history
        - 2 * automated_coverage_adjustment
    )


def scale_raw_risk(raw: float) -> float:
    """Scale a raw value to 0..100 without rounding."""
    return max(0.0, min(100.0, raw * 100 / 124))


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
    raw = calculate_raw_risk(
        impact,
        likelihood,
        detectability,
        change_extent,
        external_dependency,
        production_history,
        automated_coverage_adjustment,
    )
    return round(scale_raw_risk(raw))


def priority_for_score(score: float) -> str:
    """Return the documented priority band for a risk score."""
    if score >= 70:
        return "P0"
    if score >= 55:
        return "P1"
    if score >= 35:
        return "P2"
    return "P3"
