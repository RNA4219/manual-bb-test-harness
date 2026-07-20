"""ローカルモデル・ベンチマーク検証器の回帰テスト。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bb_harness.tools import verify_local_benchmark as benchmark


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _write_run(root: Path, fixture: str, run_number: int) -> None:
    run_dir = root / fixture / f"run-{run_number}"
    run_dir.mkdir(parents=True)
    artifact_path = run_dir / "feature_spec.json"
    _write_json(artifact_path, {"feature_id": fixture})
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    _write_json(
        run_dir / "run_manifest.json",
        {
            "status": "succeeded",
            "elapsed_seconds": 12.5 + run_number,
            "stages": [{"schema_valid": True, "repairs": run_number % 2}],
            "artifacts": {"feature_spec": {"schema_valid": True, "sha256": digest}},
        },
    )
    _write_json(run_dir / "lint_report.json", {"status": "pass", "errors": []})
    _write_json(run_dir / "quality_report.json", {"automatic_fails": []})
    _write_json(run_dir / "risk_register.json", {"risks": []})
    _write_json(
        run_dir / "effort_plan.json",
        {
            "phases": [{"estimate_hours": 1.0}],
            "retry_buffer_percent": 20,
            "total_estimate_hours": 1.2,
        },
    )
    _write_json(run_dir / "gate_decision.json", {"status": "no_go"})


@pytest.fixture
def benchmark_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(benchmark, "ARTIFACT_SCHEMAS", {"feature_spec": "unused.json"})
    monkeypatch.setattr(benchmark, "validate_artifact", lambda *_: None)
    root = tmp_path / "benchmark"
    for fixture in benchmark.FIXTURES:
        for run_number in range(1, 4):
            _write_run(root, fixture, run_number)
    return root


def _write_scores(path: Path, score: int = 78) -> None:
    _write_json(
        path,
        {
            "runs": [
                {"fixture": fixture, "run": run_number, "score": score + run_number}
                for fixture in benchmark.FIXTURES
                for run_number in range(1, 4)
            ]
        },
    )


def test_verify_benchmark_and_cli_accept_nine_runs(
    benchmark_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scores = tmp_path / "scores.json"
    output = tmp_path / "summary.json"
    _write_scores(scores)

    result = benchmark.verify_benchmark(benchmark_root, scores)
    assert result["accepted"] is True
    assert result["machine_checks_passed"] is True
    assert result["independent_scores"]["minimum"] == 79

    assert (
        benchmark.main(
            ["--input", str(benchmark_root), "--scores", str(scores), "--output", str(output)]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["accepted"] is True
    assert '"accepted": true' in capsys.readouterr().out


def test_verify_without_scores_is_machine_only(benchmark_root: Path) -> None:
    result = benchmark.verify_benchmark(benchmark_root)
    assert result["machine_checks_passed"] is True
    assert result["accepted"] is False
    assert result["independent_scores"] is None


def test_score_file_must_have_exact_matrix(benchmark_root: Path, tmp_path: Path) -> None:
    scores = tmp_path / "scores.json"
    _write_json(scores, {"runs": [{"fixture": "order-cancel", "run": 1, "score": 90}]})
    with pytest.raises(ValueError, match="exactly 3 fixtures x 3 runs"):
        benchmark.verify_benchmark(benchmark_root, scores)


def test_cli_returns_failure_for_missing_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert benchmark.main(["--input", str(tmp_path / "missing")]) == 1
    assert "Error:" in capsys.readouterr().err


def test_risk_math_covers_all_priorities_and_rejects_invalid_values() -> None:
    def risk(impact: int, likelihood: int, priority: str) -> dict[str, object]:
        score = round(min(100.0, 4 * impact * likelihood * 100.0 / 124.0), 1)
        return {
            "impact": impact,
            "likelihood": likelihood,
            "score": score,
            "priority": priority,
            "modifiers": [],
        }

    register = {
        "risks": [
            risk(5, 5, "P0"),
            risk(5, 4, "P1"),
            risk(4, 3, "P2"),
            risk(2, 2, "P3"),
        ]
    }
    assert benchmark._risk_math_valid(register) is True

    register["risks"][0]["score"] = -1
    assert benchmark._risk_math_valid(register) is False
    register["risks"][0]["modifiers"] = ["broken"]
    assert benchmark._risk_math_valid(register) is False


def test_effort_math_rejects_wrong_total() -> None:
    assert (
        benchmark._effort_math_valid(
            {
                "phases": [{"estimate_hours": 2}],
                "retry_buffer_percent": 20,
                "total_estimate_hours": 2.0,
            }
        )
        is False
    )
