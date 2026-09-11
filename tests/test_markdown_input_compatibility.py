"""自己BBで見つかった日本語名・先頭BOMの入力互換性を検証する。"""

from pathlib import Path

import pytest

from bb_harness.local_pipeline import normalize_feature_spec
from bb_harness.requirements_confidence import evaluate_requirements, load_input, review_template
from bb_harness.tools._shared.spec_ingest_markdown import ingest_markdown_spec, read_markdown

BODY = "## Acceptance Criteria\n- AC-1: 保存後に完了と表示する。\n"


def test_non_ascii_feature_identity_is_stable_distinct_and_compatible(tmp_path):
    results = []
    for directory, filename in (("first", "日本語 空白.md"), ("second", "日本語 空白.md"),
                                ("third", "別の仕様.md")):
        path = tmp_path / directory / filename
        path.parent.mkdir()
        path.write_text(BODY, encoding="utf-8")
        feature, _ = load_input(path)
        local = normalize_feature_spec(path)
        ingested = ingest_markdown_spec(path)
        assert feature["feature_id"] == local["feature_id"] == ingested["feature_id"]
        results.append(feature["feature_id"])
    # 4.1.0の要件評価に実在したIDを保持し、ディレクトリ変更では別機能にしない。
    assert results[0] == results[1] == "MD-02d46ebef8cc"
    assert results[2] and results[2] != results[0]


@pytest.mark.parametrize("prefix", ["", "# 保存仕様\n\n", "---\nfeature_id: KEEP-01\ntitle: 保存仕様\n---\n"])
def test_bom_preserves_ingest_and_local_artifacts(tmp_path, prefix):
    path = tmp_path / "order-cancel.input.md"
    text = prefix + BODY
    path.write_text(text, encoding="utf-8")
    ingested, local = ingest_markdown_spec(path), normalize_feature_spec(path)
    path.write_text(text, encoding="utf-8-sig")
    assert ingest_markdown_spec(path) == ingested
    assert normalize_feature_spec(path) == local
    assert local["feature_id"] == "ORDER-CANCEL"
    assert local["acceptance_criteria"] == ["AC-1: 保存後に完了と表示する。"]
    if prefix.startswith("---"):
        assert ingested["feature_id"] == "KEEP-01"


@pytest.mark.parametrize("prefix", ["", "# 保存仕様\n\n", "---\nfeature_id: KEEP-01\ntitle: 保存仕様\n---\n"])
def test_bom_preserves_requirements_score_and_revision(tmp_path, prefix):
    path = tmp_path / "仕様.md"
    text = prefix + BODY.replace("Acceptance Criteria", "要件")
    path.write_text(text, encoding="utf-8")
    feature, markers = load_input(path)
    plain = evaluate_requirements(feature, markers=markers)
    path.write_text(text, encoding="utf-8-sig")
    feature, markers = load_input(path)
    actual = evaluate_requirements(feature, markers=markers)
    assert actual == plain
    assert actual["counts"]["requirements"] == 1
    assert actual["score"] == 69
    path.write_text(text + "\n本文の仕様を変更\n", encoding="utf-8-sig")
    changed, markers = load_input(path)
    with pytest.raises(ValueError, match="入力版"):
        evaluate_requirements(changed, markers=markers, review=review_template(actual))


def test_bom_removal_preserves_body_characters_and_lines(tmp_path: Path):
    path = tmp_path / "body.md"
    text = "# 保存\n本文内の\ufeff文字を保持\n"
    path.write_text(text, encoding="utf-8-sig")
    assert read_markdown(path) == text
