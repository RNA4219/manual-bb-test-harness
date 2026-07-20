"""3 fixtures x 3 runsのlocal benchmarkを決定的に検証する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from bb_harness import __version__
from bb_harness.local_pipeline import ARTIFACT_SCHEMAS
from bb_harness.schema_validation import validate_artifact

FIXTURES = ("order-cancel", "admin-role-change", "mobile-session-resume")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _risk_math_valid(register: dict[str, Any]) -> bool:
    for risk in register["risks"]:
        modifiers = {}
        for item in risk.get("modifiers", []):
            name, separator, raw_value = item.partition("=")
            if not separator:
                return False
            modifiers[name] = int(raw_value)
        raw = (
            4 * int(risk["impact"]) * int(risk["likelihood"])
            + 2 * modifiers.get("detectability_difficulty", 0)
            + 2 * modifiers.get("change_surface", 0)
            + 2 * modifiers.get("externality", 0)
            + 2 * modifiers.get("privilege", 0)
            - 2 * modifiers.get("auto_coverage_credit", 0)
        )
        score = round(min(100.0, raw * 100.0 / 124.0), 1)
        priority = (
            "P0"
            if score >= 70
            else "P1"
            if score >= 55
            else "P2"
            if score >= 35
            else "P3"
        )
        if float(risk.get("score", -1)) != score or risk.get("priority") != priority:
            return False
    return True


def _effort_math_valid(effort: dict[str, Any]) -> bool:
    phase_sum = round(sum(float(item["estimate_hours"]) for item in effort["phases"]), 2)
    expected = round(phase_sum * (1 + float(effort["retry_buffer_percent"]) / 100), 2)
    return float(effort["total_estimate_hours"]) == expected


def verify_run(run_dir: Path, fixture: str, run_number: int) -> dict[str, Any]:
    manifest = _load(run_dir / "run_manifest.json")
    validate_artifact(manifest, "local_run_manifest.schema.json")
    checks: dict[str, bool] = {
        "succeeded": manifest["status"] == "succeeded",
        "under_10_minutes": float(manifest["elapsed_seconds"]) <= 600,
        "all_stage_schemas": all(item["schema_valid"] for item in manifest["stages"]),
    }
    for name, schema_name in ARTIFACT_SCHEMAS.items():
        path = run_dir / f"{name}.json"
        value = _load(path)
        validate_artifact(value, schema_name)
        record = manifest["artifacts"].get(name, {})
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checks[f"{name}_schema_hash"] = (
            record.get("schema_valid") is True and record.get("sha256") == digest
        )
    lint = _load(run_dir / "lint_report.json")
    quality = _load(run_dir / "quality_report.json")
    risks = _load(run_dir / "risk_register.json")
    effort = _load(run_dir / "effort_plan.json")
    gate = _load(run_dir / "gate_decision.json")
    checks.update(
        {
            "lint_pass": lint.get("status") == "pass" and not lint.get("errors"),
            "automatic_fails_zero": not quality.get("automatic_fails"),
            "risk_math": _risk_math_valid(risks),
            "effort_math": _effort_math_valid(effort),
            "evidence_free_gate_no_go": gate.get("status") == "no_go",
        }
    )
    return {
        "fixture": fixture,
        "run": run_number,
        "elapsed_seconds": manifest["elapsed_seconds"],
        "repairs": sum(int(item["repairs"]) for item in manifest["stages"]),
        "checks": checks,
        "passed": all(checks.values()),
    }


def verify_benchmark(root: Path, scores_path: Path | None = None) -> dict[str, Any]:
    rows = [
        verify_run(root / fixture / f"run-{run_number}", fixture, run_number)
        for fixture in FIXTURES
        for run_number in range(1, 4)
    ]
    result: dict[str, Any] = {
        "root": str(root),
        "runs": rows,
        "machine_checks_passed": all(item["passed"] for item in rows),
        "max_elapsed_seconds": max(float(item["elapsed_seconds"]) for item in rows),
        "median_elapsed_seconds": statistics.median(
            float(item["elapsed_seconds"]) for item in rows
        ),
        "total_repairs": sum(int(item["repairs"]) for item in rows),
    }
    if scores_path:
        scores = _load(scores_path).get("runs", [])
        score_by_run = {
            (item["fixture"], int(item["run"])): float(item["score"]) for item in scores
        }
        expected_keys = {(fixture, run) for fixture in FIXTURES for run in range(1, 4)}
        if set(score_by_run) != expected_keys:
            raise ValueError("Independent score file must contain exactly 3 fixtures x 3 runs")
        values = list(score_by_run.values())
        fixture_medians = {
            fixture: statistics.median(score_by_run[(fixture, run)] for run in range(1, 4))
            for fixture in FIXTURES
        }
        score_checks = {
            "fixture_medians_at_least_70": all(value >= 70 for value in fixture_medians.values()),
            "overall_median_at_least_70": statistics.median(values) >= 70,
            "minimum_at_least_65": min(values) >= 65,
        }
        result["independent_scores"] = {
            "fixture_medians": fixture_medians,
            "overall_median": statistics.median(values),
            "minimum": min(values),
            "checks": score_checks,
        }
        result["accepted"] = result["machine_checks_passed"] and all(score_checks.values())
    else:
        result["accepted"] = False
        result["independent_scores"] = None
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Benchmark root directory")
    parser.add_argument("--scores", type=Path, help="Independent rubric score JSON")
    parser.add_argument("--output", type=Path, help="Write summary JSON")
    parser.add_argument("--version", action="version", version=f"verify-local-benchmark {__version__}")
    args = parser.parse_args(argv)
    try:
        result = verify_benchmark(args.input, args.scores)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if result["machine_checks_passed"] and (not args.scores or result["accepted"]) else 1
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
