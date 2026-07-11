"""Strict spec validation acceptance tests."""

from pathlib import Path

from tests.test_validate_spec import load_validate_spec_module


def complete_spec(requirements: str, acceptance: str) -> str:
    return "\n".join(
        [
            "# Spec",
            "## 概要",
            "overview",
            "## 目的",
            "purpose",
            "## 要件",
            requirements,
            "## 設計",
            "| item | value |",
            "|---|---|",
            "| design | value |",
            "## インターフェース",
            "```bash",
            "bb-harness validate",
            "```",
            "## 制約",
            "constraint",
            "## テスト観点",
            "test",
            "## 受入基準",
            acceptance,
        ]
    )


def test_zero_acceptance_items_fails_overall(tmp_path: Path) -> None:
    module = load_validate_spec_module()
    path = tmp_path / "spec-zero-ac.md"
    path.write_text(
        complete_spec(
            "| id | requirement | priority |\n|---|---|---|\n| R1 | behavior | P0 |",
            "",
        ),
        encoding="utf-8",
    )
    assert module.validate_spec(path)["summary"]["overall"] == "fail"


def test_broken_requirements_table_fails_overall(tmp_path: Path) -> None:
    module = load_validate_spec_module()
    path = tmp_path / "spec-broken-table.md"
    path.write_text(
        complete_spec("requirements without a table", "- [x] accepted"),
        encoding="utf-8",
    )
    assert module.validate_spec(path)["summary"]["overall"] == "fail"


def test_duplicate_requirement_ids_fail_overall(tmp_path: Path) -> None:
    module = load_validate_spec_module()
    path = tmp_path / "spec-duplicate.md"
    path.write_text(
        complete_spec(
            "| id | requirement | priority |\n"
            "|---|---|---|\n"
            "| R1 | first | P0 |\n"
            "| R1 | duplicate | P1 |",
            "- [x] accepted",
        ),
        encoding="utf-8",
    )
    result = module.validate_spec(path)
    assert result["requirements"]["duplicate_ids"] == ["R1"]
    assert result["summary"]["overall"] == "fail"
