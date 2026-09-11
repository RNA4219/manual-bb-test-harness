"""実績分析の欠測・版照合・群分離と統計計算を確認する。"""

import copy
import hashlib
import json

import pytest

from bb_harness.requirements_confidence import evaluate_requirements
from tests.test_requirements_confidence import feature
from tools import analyze_requirements_outcomes as study


def dataset(tmp_path):
    report = evaluate_requirements(feature())
    raw = json.dumps(report).encode()
    (tmp_path / "snapshot.json").write_bytes(raw)
    data = {
        "data_kind": "synthetic",
        "window_days": 30,
        "cases": [
            {
                "project_id": "sample-1",
                "split": "calibration",
                "evaluated_at": "2020-01-01",
                "window_end": "2020-01-31",
                "report_path": "snapshot.json",
                "report_sha256": hashlib.sha256(raw).hexdigest(),
                "complete": True,
                "defects": 1,
                "rework_hours": 2.5,
            }
        ],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def test_snapshot_hash_and_missing_outcome_are_not_zero(tmp_path):
    path, data = dataset(tmp_path)
    data["cases"][0]["defects"] = None
    path.write_text(json.dumps(data), encoding="utf-8")
    result = study.analyze(path)
    assert result["excluded"]["incomplete_outcomes"] == 1
    assert result["groups"]["calibration"]["cases"] == 0
    assert result["groups"]["calibration"]["thresholds"][0]["weighted_loss"] is None
    assert result["candidate"] is None
    (tmp_path / "snapshot.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        study.analyze(path)


@pytest.mark.parametrize(
    "damage", ["project", "input", "period", "negative", "nan", "boolean", "future", "escape"]
)
def test_invalid_or_duplicate_study_records_are_rejected(tmp_path, damage):
    path, data = dataset(tmp_path)
    item = data["cases"][0]
    if damage in {"project", "input"}:
        second = copy.deepcopy(item)
        second["split"] = "holdout"
        if damage == "input":
            second["project_id"] = "sample-2"
        data["cases"].append(second)
    elif damage == "period":
        item["window_end"] = "2020-02-01"
    elif damage == "negative":
        item["defects"] = -1
    elif damage == "nan":
        item["rework_hours"] = float("nan")
    elif damage == "boolean":
        item["defects"] = True
    elif damage == "future":
        item.update(evaluated_at="2999-01-01", window_end="2999-01-31")
    else:
        item["report_path"] = "../snapshot.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        study.analyze(path)


def test_spearman_handles_ties_constants_and_small_samples():
    assert study.spearman([1, 2, 2, 4], [4, 2, 2, 1]) == -1
    assert study.spearman([1, 1, 1], [1, 2, 3]) is None
    assert study.spearman([1, 2], [2, 1]) is None


def test_confusion_matrix_preserves_threshold_boundary():
    rows = [
        {"score": score, "adverse": adverse}
        for score, adverse in ((84, True), (85, True), (84, False), (85, False))
    ]
    result = study.threshold_metrics(rows, 85)
    assert result == {
        "threshold": 85,
        "true_positive": 1,
        "false_negative": 1,
        "false_positive": 1,
        "true_negative": 1,
        "weighted_loss": 1.5,
    }


@pytest.mark.parametrize("kind,sufficient", [("real", False), ("synthetic", True), ("real", True)])
def test_holdout_cannot_select_threshold_and_synthetic_never_calibrates(
    tmp_path, monkeypatch, kind, sufficient
):
    calibration = [
        {
            "score": 65 if i % 2 else 95,
            "adverse": bool(i % 2),
            "band": "medium",
            "requirements": 4,
            "defects": i % 2,
            "rework_hours": 0,
            "split": "calibration",
        }
        for i in range(20 if sufficient else 4)
    ]
    holdout = [{**row, "split": "holdout"} for row in calibration[:10]]
    meta = {
        "data_kind": kind,
        "window_days": 30,
        "total_cases": len(calibration + holdout),
        "input_sha256": "a" * 64,
    }
    monkeypatch.setattr(study, "load_cases", lambda path: (meta, calibration + holdout, {}))
    first = study.analyze(tmp_path)
    if kind == "synthetic" or not sufficient:
        assert first["candidate"] is None and not first["policy_changed"]
    else:
        # 保留群の成績だけを反転しても、調整群で選んだ閾値は変わらない。
        for row in holdout:
            row["adverse"] = not row["adverse"]
        second = study.analyze(tmp_path)
        assert first["candidate"]["threshold"] == second["candidate"]["threshold"]
        assert first["candidate"]["holdout"] != second["candidate"]["holdout"]
        assert not second["candidate"]["apply_automatically"]


def test_empty_dataset_produces_insufficient_data_and_protects_output(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"data_kind": "real", "window_days": 30, "cases": []}))
    output = tmp_path / "analysis"
    args = ["--input", str(path), "--output", str(output)]
    study.main(args)
    assert json.loads((output / "analysis.json").read_text())["status"] == "insufficient_data"
    assert "| calibration | 0 | 0 |" in (output / "summary.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="新規"):
        study.main(args)
