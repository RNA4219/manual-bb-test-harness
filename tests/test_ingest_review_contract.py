"""元の Markdown の受入条件・ルール・環境を欠落させない取り込み契約。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from bb_harness.tools.spec_ingest import ingest_markdown_spec, main

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_spec(tmp_path: Path, text: str) -> Path:
    source = tmp_path / "review-contract.md"
    source.write_text(text, encoding="utf-8")
    return source


def test_nested_exception_criteria_stay_with_their_parent(tmp_path: Path) -> None:
    source = write_spec(
        tmp_path,
        "# 注文取消\n"
        "## Acceptance Criteria\n"
        "- AC-1: 発送前の注文を取り消せる。\n"
        "### Exceptions\n"
        "- AC-2: 発送済みの注文は取り消せない。\n"
        "#### Payment timeout\n"
        "- AC-3: 返金が失敗した場合は再試行できる。\n"
        "## Business Rules\n"
        "- BR-1: 返金は一度だけ行う。\n",
    )

    result = ingest_markdown_spec(source)

    assert result["acceptance_criteria"] == [
        "AC-1: 発送前の注文を取り消せる。",
        "AC-2: 発送済みの注文は取り消せない。",
        "AC-3: 返金が失敗した場合は再試行できる。",
    ]
    assert result["business_rules"] == ["BR-1: 返金は一度だけ行う。"]


@pytest.mark.parametrize("second_heading", ["Business Rules", "BR"])
def test_repeated_rule_sections_are_merged_in_source_order(
    tmp_path: Path, second_heading: str
) -> None:
    source = write_spec(
        tmp_path,
        "## Acceptance Criteria\n- AC-1: 注文を取り消せる。\n"
        "## Business Rules\n- BR-1: 返金は一度だけ行う。\n"
        f"## {second_heading}\n- BR-2: 取消の監査記録を残す。\n",
    )

    result = ingest_markdown_spec(source)

    assert result["business_rules"] == [
        "BR-1: 返金は一度だけ行う。",
        "BR-2: 取消の監査記録を残す。",
    ]


def test_horizontal_rules_inside_body_do_not_discard_earlier_requirements(
    tmp_path: Path,
) -> None:
    source = write_spec(
        tmp_path,
        "# 注文取消\n"
        "## Acceptance Criteria\n- AC-1: 発送前に取り消せる。\n"
        "---\n"
        "- AC-2: 発送後は取り消せない。\n"
        "---\n"
        "## Business Rules\n- BR-1: 取消の監査記録を残す。\n",
    )

    result = ingest_markdown_spec(source)

    assert result["acceptance_criteria"] == [
        "AC-1: 発送前に取り消せる。",
        "AC-2: 発送後は取り消せない。",
    ]
    assert result["business_rules"] == ["BR-1: 取消の監査記録を残す。"]


def test_mobile_golden_preserves_its_declared_platforms() -> None:
    result = ingest_markdown_spec(REPO_ROOT / "goldens" / "mobile-session-resume.input.md")

    assert result["devices"] == ["iOS", "Android"]
    assert result["mobile_contexts"] == [
        "foreground", "background_resume", "offline", "push_notification_entry"
    ]
    assert len(result["acceptance_criteria"]) == 4


def test_devices_and_environment_sections_both_survive(tmp_path: Path) -> None:
    source = write_spec(
        tmp_path,
        "## Acceptance Criteria\n- AC-1: 書類を送信できる。\n"
        "## Devices\n- Web\n"
        "## Environments\n- iOS\n- Android\n",
    )

    assert ingest_markdown_spec(source)["devices"] == ["Web", "iOS", "Android"]


@pytest.mark.parametrize(
    "text",
    [
        "# 調査中\n## Summary\n受入条件はまだ決まっていない。\n",
        "## Acceptance Criteria\n\n## Business Rules\n- BR-1: 記録を残す。\n",
        "## Acceptance Criteria\n---\n***\n___\n",
    ],
)
def test_missing_or_empty_criteria_do_not_become_synthetic_acceptance_criteria(
    tmp_path: Path, text: str
) -> None:
    source = write_spec(tmp_path, text)

    with pytest.raises(ValueError, match="acceptance criteria"):
        ingest_markdown_spec(source)


@pytest.mark.parametrize("existing_output", [False, True])
def test_cli_rejects_missing_criteria_without_creating_or_overwriting_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_output: bool
) -> None:
    source = write_spec(tmp_path, "## Summary\n受入条件は未定。\n")
    output = tmp_path / "feature.json"
    original = b'{"reviewed": true}\n'
    if existing_output:
        output.write_bytes(original)
    monkeypatch.setattr(
        sys,
        "argv",
        ["spec-ingest", "--source", "markdown", "--input", str(source), "--output", str(output)],
    )

    assert main() == 1
    if existing_output:
        assert output.read_bytes() == original
    else:
        assert not output.exists()
