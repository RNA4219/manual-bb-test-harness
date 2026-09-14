"""要件定義の信頼度と、確認・解決根拠の境界を検証する。"""

import copy
import json
from pathlib import Path

import pytest

from bb_harness.cli import main
from bb_harness.requirements_confidence import (
    evaluate_requirements,
    load_input,
    render_markdown,
    review_template,
)
from bb_harness.schema_validation import validate_artifact

ROOT = Path(__file__).resolve().parents[1]


def feature(count=4):
    return {
        "feature_id": "CONF-1",
        "revision": "spec-confidence-test-rev-1",
        "title": "要件評価",
        "acceptance_criteria": [
            f"AC-{i}: 状態{i}では注文を更新できる" for i in range(1, count + 1)
        ],
        "business_rules": [],
        "source_refs": [{"id": "SPEC-1", "kind": "spec", "excerpt": "状態別の注文更新可否表"}],
        "assumptions": [],
    }


def review_for(value, *, phase=None, markers=None, confirmed=True):
    report = evaluate_requirements(value, phase=phase, markers=markers)
    review = review_template(report)
    review["reviewer"] = "要件レビュー担当"
    review["reviewed_at"] = "2026-09-11T09:00:00+09:00"
    for item in review["requirements"]:
        item.update(
            reviewed=confirmed,
            oracle="指定した状態で更新成功画面を表示する",
            source_refs=["SPEC-1"],
        )
    return review


def add_assumption(value, severity="medium", **extra):
    value["assumptions"].append(
        {"id": "ASM-1", "text": "注文更新時の通知先を確認する", "severity": severity, **extra}
    )


def phase_for(value):
    phase = json.loads(
        (ROOT / "examples/artifacts/order-cancel.phase_contract.json").read_text(encoding="utf-8")
    )
    phase["feature_id"] = value["feature_id"]
    return phase


def test_no_findings_without_review_is_provisional():
    report = evaluate_requirements(feature())
    assert report["score"] == 69
    assert report["counts"]["open_confirmations"] == 0
    assert report["status"] == "needs_confirmation"
    assert report["provisional"]
    assert len(report["next_actions"]) == 4
    template = review_template(report)
    validate_artifact(template, "requirements_review.schema.json")
    assert template["reviewer"] is None
    assert all(not item["reviewed"] for item in template["requirements"])


def test_complete_review_is_traceable_and_deterministic():
    value = feature()
    review = review_for(value)
    original = copy.deepcopy((value, review))
    report = evaluate_requirements(value, review=review)
    assert report["score"] == 100
    assert report["band"] == "high"
    assert report["status"] == "reviewed"
    assert report["provisional"] is False
    assert report["next_actions"] == []
    assert report["review"]["requirements"] == review["requirements"]
    assert report == evaluate_requirements(value, review=review)
    assert (value, review) == original


def test_weight_density_and_partial_review_calculation():
    value = feature()
    add_assumption(value)
    review = review_for(value)
    for item in review["requirements"][2:]:
        item["reviewed"] = False
    report = evaluate_requirements(value, review=review)
    assert report["metrics"] == {
        "review_coverage_percent": 50.0,
        "open_items_per_requirement": 0.25,
        "uncertainty_weight": 2,
        "normalization_capacity": 16,
        "uncertainty_points": 61.25,
        "review_points": 15.0,
        "base_score": 76.2,
    }
    assert report["score"] == 76.2
    assert report["provisional"]


@pytest.mark.parametrize(
    ("severity", "cap", "weight"),
    [
        ("critical", 39, 8),
        ("high", 69, 4),
        ("medium", 84, 2),
        ("low", 84, 1),
    ],
)
def test_many_requirements_cannot_dilute_severity_caps(severity, cap, weight):
    value = feature(100)
    add_assumption(value, severity)
    report = evaluate_requirements(value, review=review_for(value))
    assert report["score"] == cap
    assert report["metrics"]["uncertainty_weight"] == weight
    assert report["counts"]["by_severity"][severity] == 1
    assert report["status"] == ("blocked" if severity == "critical" else "needs_confirmation")


def test_partial_review_never_gets_high_band():
    value = feature(100)
    review = review_for(value)
    review["requirements"][0]["reviewed"] = False
    report = evaluate_requirements(value, review=review)
    assert report["score"] == 84
    assert report["band"] == "medium"


@pytest.mark.parametrize("placeholder", ["", "   ", "[NO ACCEPTANCE CRITERIA FOUND]"])
def test_no_real_requirements_have_no_score(placeholder):
    value = feature()
    value["acceptance_criteria"] = [placeholder]
    report = evaluate_requirements(value)
    assert report["score"] is None
    assert report["band"] == "unknown"
    assert report["status"] == "insufficient_data"
    assert report["metrics"]["review_coverage_percent"] is None


def test_duplicate_requirements_do_not_inflate_capacity():
    value = feature()
    original = evaluate_requirements(value)
    value["business_rules"] = [
        "BR-9: 状態1では注文を更新できる",
        "ＡＣ-８: 状態1では注文を更新できる",
    ]
    report = evaluate_requirements(value)
    assert report["counts"]["requirements"] == 4
    assert report["counts"]["duplicate_requirements"] == 2
    assert report["score"] == original["score"]
    assert report["metrics"]["normalization_capacity"] == 16


def test_duplicate_findings_preserve_max_severity_and_aliases():
    value = feature()
    value["acceptance_criteria"][0] = "AC-1: [要確認] 更新時の通知先"
    value["assumptions"] = [{"id": "A", "text": "[要確認] 更新時の通知先", "severity": "high"}]
    report = evaluate_requirements(value)
    assert report["counts"]["raw_findings"] == 2
    assert report["counts"]["open_confirmations"] == 1
    assert report["issues"][0]["severity"] == "high"
    assert len(report["issues"][0]["ids"]) == 2
    assert len(report["issues"][0]["locations"]) == 2


@pytest.mark.parametrize("status", ["open", "accepted", "resolved"])
def test_legacy_assumption_status_does_not_replace_resolution_evidence(status):
    value = feature()
    add_assumption(value, resolution_status=status)
    assert evaluate_requirements(value)["counts"]["open_confirmations"] == 1


def test_evidenced_resolution_improves_score_and_preserves_history():
    value = feature()
    add_assumption(value, "critical")
    review = review_for(value)
    before = evaluate_requirements(value, review=review)
    review["resolutions"] = [
        {
            "issue_id": before["issues"][0]["issue_id"],
            "decision": "通知先は購入者と確定した",
            "source_refs": ["SPEC-1"],
        }
    ]
    after = evaluate_requirements(value, review=review)
    assert after["score"] > before["score"]
    assert after["score"] == 100
    assert after["counts"]["resolved_confirmations"] == 1
    assert after["issues"][0]["resolution"] == review["resolutions"][0]


def test_phase_questions_gaps_and_blocking_flags():
    value = feature()
    phase = phase_for(value)
    phase["open_questions"][0]["severity"] = "low"
    phase["confidence"] = "high"
    phase["readiness"]["status"] = "ok"
    phase["readiness"]["decision"] = "ready"
    report = evaluate_requirements(value, phase=phase)
    assert report["status"] == "blocked"
    assert report["score"] <= 39
    assert report["counts"]["open_confirmations"] == 2
    assert report["counts"]["technical_risks"] == 1
    assert report["next_actions"][0]["owner"] == "PM"


def test_review_can_register_semantic_findings():
    value = feature()
    review = review_for(value)
    review["findings"] = [
        {
            "id": "F1",
            "kind": "contradiction",
            "severity": "high",
            "text": "同じ状態の更新可否に矛盾がある",
            "requirement_ids": [review["requirements"][0]["requirement_id"]],
            "source_refs": ["SPEC-1"],
            "owner": "PM",
            "due": "2026-09-15",
        }
    ]
    report = evaluate_requirements(value, review=review)
    assert report["counts"]["open_confirmations"] == 1
    assert report["issues"][0]["kind"] == "contradiction"
    assert report["next_actions"][0]["due"] == "2026-09-15"


@pytest.mark.parametrize(
    "change",
    [
        "fingerprint",
        "feature",
        "unknown_req",
        "duplicate_req",
        "unknown_ref",
        "empty_refs",
        "oracle",
        "reviewer",
        "timestamp",
        "naive_timestamp",
    ],
)
def test_invalid_review_is_rejected(change):
    value = feature()
    review = review_for(value)
    item = review["requirements"][0]
    if change == "fingerprint":
        review["input_sha256"] = "0" * 64
    elif change == "feature":
        review["feature_id"] = "OTHER"
    elif change == "unknown_req":
        item["requirement_id"] = "OTHER"
    elif change == "duplicate_req":
        review["requirements"].append(copy.deepcopy(item))
    elif change == "unknown_ref":
        item["source_refs"] = ["OTHER"]
    elif change == "empty_refs":
        item["source_refs"] = []
    elif change == "oracle":
        item["oracle"] = "[要確認]"
    elif change == "reviewer":
        review["reviewer"] = "   "
    elif change == "timestamp":
        review["reviewed_at"] = None
    else:
        review["reviewed_at"] = "2026-09-11T09:00:00"
    with pytest.raises(ValueError):
        evaluate_requirements(value, review=review)


@pytest.mark.parametrize(
    "change", ["unknown", "duplicate", "no_source", "pending", "duplicate_alias"]
)
def test_invalid_resolution_is_rejected(change):
    value = feature()
    value["acceptance_criteria"][0] = "[要確認] 更新時の通知先"
    value["assumptions"] = [{"id": "A", "text": "[要確認] 更新時の通知先", "severity": "high"}]
    review = review_for(value)
    issue = evaluate_requirements(value)["issues"][0]
    resolution = {
        "issue_id": issue["issue_id"],
        "decision": "購入者へ通知する",
        "source_refs": ["SPEC-1"],
    }
    review["resolutions"] = [resolution]
    if change == "unknown":
        resolution["issue_id"] = "missing"
    elif change == "duplicate":
        review["resolutions"].append(copy.deepcopy(resolution))
    elif change == "no_source":
        resolution["source_refs"] = []
    elif change == "pending":
        resolution["decision"] = "TBD"
    else:
        second = copy.deepcopy(resolution)
        second["issue_id"] = next(
            identifier for identifier in issue["ids"] if identifier != issue["issue_id"]
        )
        review["resolutions"].append(second)
    with pytest.raises(ValueError):
        evaluate_requirements(value, review=review)


@pytest.mark.parametrize(
    "change",
    [
        "source_duplicate",
        "source_conflict",
        "phase_feature",
        "question_duplicate",
        "phase_unknown_ref",
        "assumption_duplicate",
        "blank_feature",
        "blank_title",
    ],
)
def test_invalid_input_identity_is_rejected(change):
    value = feature()
    phase = phase_for(value)
    if change == "source_duplicate":
        value["source_refs"].append(value["source_refs"][0].copy())
    elif change == "source_conflict":
        phase["source_refs"][0]["id"] = "SPEC-1"
    elif change == "phase_feature":
        phase["feature_id"] = "OTHER"
    elif change == "question_duplicate":
        phase["spec_gaps"][0]["id"] = phase["open_questions"][0]["id"]
    elif change == "phase_unknown_ref":
        phase["open_questions"][0]["source_refs"] = ["MISSING"]
    elif change == "assumption_duplicate":
        add_assumption(value)
        value["assumptions"].append(value["assumptions"][0].copy())
    elif change == "blank_feature":
        value["feature_id"] = " "
    else:
        value["title"] = " "
    with pytest.raises(ValueError):
        evaluate_requirements(value, phase=phase)


def test_source_id_without_content_cannot_ground_review():
    value = feature()
    del value["source_refs"][0]["excerpt"]
    assert evaluate_requirements(value)["counts"]["by_severity"]["high"] == 1
    with pytest.raises(ValueError, match="引用内容"):
        evaluate_requirements(value, review=review_for(value))


def test_markdown_tags_japanese_headings_and_full_document_revision(tmp_path):
    path = tmp_path / "仕様.md"
    text = "# 注文\n\n## 受入条件\n- AC-1: [要確認] 通知先\n- AC-2: 更新する\n\n## 業務ルール\n- 二重更新を禁止\n\n## 検討事項\n- [要確認] 通知先\n- TODO 期限\n"
    path.write_text(text, encoding="utf-8")
    value, markers = load_input(path)
    report = evaluate_requirements(value, markers=markers)
    assert value["feature_id"].startswith("MD-")
    assert report["counts"]["requirements"] == 3
    assert report["counts"]["open_confirmations"] == 2
    assert value["source_refs"][0]["excerpt"] == text.strip()
    review = review_template(report)
    path.write_text(text + "\n## 備考\n追加の説明\n", encoding="utf-8")
    updated, updated_markers = load_input(path)
    with pytest.raises(ValueError, match="入力版"):
        evaluate_requirements(updated, review=review, markers=updated_markers)


def test_empty_markdown_is_not_high_confidence(tmp_path):
    path = tmp_path / "empty.md"
    path.write_text("# メモ\n\n## 受入条件\n", encoding="utf-8")
    value, markers = load_input(path)
    assert evaluate_requirements(value, markers=markers)["score"] is None


def test_markdown_escapes_table_content():
    value = feature()
    value["acceptance_criteria"][0] = "[要確認] A | B\n通知先"
    text = render_markdown(evaluate_requirements(value))
    assert "A \\| B 通知先" in text
    assert "正しさの確率" in text


def test_cli_outputs_and_threshold(tmp_path):
    source = tmp_path / "feature.json"
    source.write_text(json.dumps(feature()), encoding="utf-8")
    output = tmp_path / "result"
    args = ["evaluate", "requirements", "--input", str(source), "--output", str(output)]
    assert main(args + ["--fail-under", "85"]) == 2
    report = json.loads((output / "requirements_confidence.json").read_text(encoding="utf-8"))
    assert report["score"] == 69
    assert (output / "requirements-confidence.md").exists()
    template = json.loads(
        (output / "requirements_review.template.json").read_text(encoding="utf-8")
    )
    validate_artifact(template, "requirements_review.schema.json")
    snapshot = (output / "requirements_confidence.json").read_bytes()
    assert main(args) == 1
    assert snapshot == (output / "requirements_confidence.json").read_bytes()
    assert main(["evaluate", "requirements", "--input", str(source), "--output", str(source)]) == 1
    assert json.loads(source.read_text(encoding="utf-8")) == feature()


@pytest.mark.parametrize("global_flag", [False, True])
def test_cli_dry_run_does_not_write(tmp_path, global_flag):
    source = tmp_path / "spec.md"
    source.write_text("# 仕様\n\n## 要件\n- 更新できる\n", encoding="utf-8")
    output = tmp_path / "absent"
    args = ["evaluate", "requirements", "--input", str(source), "--output", str(output)]
    assert main((["--dry-run"] + args) if global_flag else (args + ["--dry-run"])) == 0
    assert not output.exists()


def test_cli_review_and_phase_inputs(tmp_path):
    value = feature()
    phase = phase_for(value)
    review = review_for(value, phase=phase)
    for name, data in (("feature", value), ("phase", phase), ("review", review)):
        (tmp_path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    assert (
        main(
            [
                "evaluate",
                "requirements",
                "--input",
                str(tmp_path / "feature.json"),
                "--phase-contract",
                str(tmp_path / "phase.json"),
                "--review",
                str(tmp_path / "review.json"),
                "--output",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )


@pytest.mark.parametrize("threshold", ["nan", "inf", "-1", "101", "text"])
def test_cli_invalid_threshold(threshold):
    with pytest.raises(SystemExit) as error:
        main(
            ["evaluate", "requirements", "--input", "x", "--output", "y", "--fail-under", threshold]
        )
    assert error.value.code == 2


@pytest.mark.parametrize(
    ("filename", "text"), [("bad.json", "{"), ("bad.json", "[]"), ("bad.txt", "text")]
)
def test_cli_invalid_input_does_not_create_output(tmp_path, filename, text):
    source = tmp_path / filename
    source.write_text(text, encoding="utf-8")
    output = tmp_path / "out"
    assert main(["evaluate", "requirements", "--input", str(source), "--output", str(output)]) == 1
    assert not output.exists()


def test_requirements_confidence_golden():
    value, markers = load_input(ROOT / "goldens/requirements-confidence.input.md")
    report = evaluate_requirements(value, markers=markers)
    assert report["score"] == 61.2
    assert report["counts"]["requirements"] == 4
    assert report["counts"]["open_confirmations"] == 1
    assert len(report["issues"][0]["locations"]) == 3  # 元配列とMarkdownの2か所
    assert report["status"] == "needs_confirmation"


def test_example_report_matches_source_and_review_template():
    base = ROOT / "examples/artifacts"
    value = json.loads((base / "order-cancel.feature_spec.json").read_text(encoding="utf-8"))
    phase = json.loads((base / "order-cancel.phase_contract.json").read_text(encoding="utf-8"))
    expected = json.loads(
        (base / "requirements/order.requirements_confidence.json").read_text(encoding="utf-8")
    )
    template = json.loads(
        (base / "requirements/order.requirements_review.json").read_text(encoding="utf-8")
    )
    assert evaluate_requirements(value, phase=phase) == expected
    assert expected["score"] == 35
    assert expected["counts"]["open_confirmations"] == 2
    assert review_template(expected) == template


def test_cross_collection_issue_id_collision_is_rejected():
    value = feature()
    phase = phase_for(value)
    phase["assumptions"] = [{"id": "A", "text": "仮定", "severity": "low"}]
    phase["open_questions"][0]["id"] = "assumption:A"
    with pytest.raises(ValueError, match="確認事項のID"):
        evaluate_requirements(value, phase=phase)


@pytest.mark.parametrize("change", ["unknown_requirement", "unknown_source", "duplicate_id"])
def test_invalid_finding_references_are_rejected(change):
    value = feature()
    review = review_for(value)
    item = {
        "id": "F1",
        "kind": "question",
        "severity": "low",
        "text": "通知文言",
        "requirement_ids": [],
        "source_refs": ["SPEC-1"],
    }
    review["findings"] = [item]
    if change == "unknown_requirement":
        item["requirement_ids"] = ["UNKNOWN"]
    elif change == "unknown_source":
        item["source_refs"] = ["UNKNOWN"]
    else:
        review["findings"].append(copy.deepcopy(item))
    with pytest.raises(ValueError):
        evaluate_requirements(value, review=review)


def test_cli_review_passes_threshold_and_empty_input_cannot(tmp_path):
    value = feature()
    for name, data in (("feature", value), ("review", review_for(value))):
        (tmp_path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    args = [
        "evaluate",
        "requirements",
        "--input",
        str(tmp_path / "feature.json"),
        "--review",
        str(tmp_path / "review.json"),
        "--output",
        str(tmp_path / "out"),
        "--fail-under",
        "100",
    ]
    assert main(args) == 0
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    assert (
        main(
            [
                "evaluate",
                "requirements",
                "--input",
                str(empty),
                "--output",
                str(tmp_path / "empty-out"),
                "--fail-under",
                "0",
            ]
        )
        == 2
    )
