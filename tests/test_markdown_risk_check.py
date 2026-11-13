"""Markdownのリスク表の検算（`bb-harness check risk`）のテスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bb_harness.cli import main
from bb_harness.markdown_risk_check import check_risk_tables, render_text
from bb_harness.risk_policy import (
    calculate_raw_risk,
    calculate_risk_score,
    priority_for_score,
    scale_raw_risk,
)

HEADER = (
    "| id | scenario | I | L | modifiers | score | priority | rationale |\n"
    "|---|---|---:|---:|---|---:|---|---|\n"
)


def _table(*rows: str) -> str:
    return "## リスク\n\n" + HEADER + "".join(row + "\n" for row in rows)


def _row(report: dict, risk_id: str) -> dict:
    return next(row for row in report["rows"] if row["id"] == risk_id)


def _kinds(row: dict) -> list[str]:
    return [issue["kind"] for issue in row["issues"]]


class TestRiskPolicy:
    def test_raw_and_score_follow_the_documented_formula(self) -> None:
        assert calculate_raw_risk(4, 4, 2, 2, 0, 2, 0) == 76
        assert calculate_risk_score(4, 4, 2, 2, 0, 2, 0) == 61

    def test_scale_clamps_to_0_100(self) -> None:
        assert scale_raw_risk(-4) == 0.0
        assert scale_raw_risk(200) == 100.0
        assert scale_raw_risk(62) == 50.0

    @pytest.mark.parametrize(
        ("score", "priority"),
        [
            (100, "P0"),
            (70, "P0"),
            (69, "P1"),
            (55, "P1"),
            (54, "P2"),
            (35, "P2"),
            (34, "P3"),
            (0, "P3"),
        ],
    )
    def test_priority_bands(self, score: int, priority: str) -> None:
        assert priority_for_score(score) == priority

    def test_impact_5_likelihood_3_never_reaches_p0(self) -> None:
        """補正を全部最大にしても、I=5・L=3 は式では P1 に留まる。"""
        assert calculate_risk_score(5, 3, 3, 3, 3, 3, 0) == 68
        assert priority_for_score(68) == "P1"


class TestCombinedModifierColumn:
    def test_all_rows_match(self) -> None:
        report = check_risk_tables(
            _table(
                "| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P1 | 根拠 |",
                "| R2 | 二重送信 | 4 | 3 | D2/C2/X1/P0/A2 | 44 | P2 | 根拠 |",
                "| R3 | 表示崩れ | 2 | 2 | D=1 C=1 X=0 P=0 A=0 | 16 | P3 | 根拠 |",
                "| R4 | 権限外の操作 | 5 | 5 | D=3, C=3, X=3, P=3, A=0 | 100 | P0 | 根拠 |",
            )
        )
        assert report["status"] == "ok"
        assert report["summary"] == {
            "tables": 1,
            "rows": 4,
            "ok": 4,
            "mismatch": 0,
            "unverifiable": 0,
            "score_mismatch": 0,
            "priority_mismatch": 0,
            "raw_mismatch": 0,
        }
        assert _row(report, "R1")["expected"] == {"raw": 76, "score": 61, "priority": "P1"}

    def test_long_modifier_names_are_read(self) -> None:
        cell = (
            "detectability_difficulty=2, change_surface=2, externality=0, "
            "privilege=2, auto_coverage_credit=0"
        )
        report = check_risk_tables(
            _table(f"| R1 | 返金額の誤り | 4 | 4 | {cell} | 61 | P1 | 根拠 |")
        )
        assert report["status"] == "ok"
        assert _row(report, "R1")["inputs"] == {
            "I": 4,
            "L": 4,
            "D": 2,
            "C": 2,
            "X": 0,
            "P": 2,
            "A": 0,
        }

    def test_score_mismatch_also_judges_priority_against_recalculated_score(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 出荷後のキャンセル | 5 | 3 | D2 C2 X2 P2 A0 | 76 | P0 | 根拠 |")
        )
        row = _row(report, "R1")
        assert report["status"] == "mismatch"
        assert row["status"] == "mismatch"
        assert _kinds(row) == ["score_mismatch", "priority_mismatch"]
        assert row["issues"][0]["stated"] == 76
        assert row["issues"][0]["expected"] == 61
        assert row["issues"][1]["stated"] == "P0"
        assert row["issues"][1]["expected"] == "P1"
        assert report["summary"]["score_mismatch"] == 1
        assert report["summary"]["priority_mismatch"] == 1

    def test_priority_only_mismatch(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P0 | 根拠 |")
        )
        assert _kinds(_row(report, "R1")) == ["priority_mismatch"]

    def test_priority_above_band_points_to_case_level_promotion(self) -> None:
        """リスク表では昇格しない。帯より高い優先度には、ケース側で上げる案内を添える。"""
        report = check_risk_tables(
            _table("| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P0 | 根拠 |")
        )
        message = _row(report, "R1")["issues"][0]["message"]
        assert "優先度 P0 → 式では P1" in message
        assert "上げるときはケースの優先度に理由を書く" in message

    def test_priority_below_band_has_no_promotion_hint(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P2 | 根拠 |")
        )
        row = _row(report, "R1")
        assert _kinds(row) == ["priority_mismatch"]
        assert "ケースの優先度" not in row["issues"][0]["message"]

    def test_rewritten_priority_uses_last_value_and_is_reported(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 監査記録の欠落 | 3 | 3 | D1 C0 X0 P2 A2 | 31 | P3→P2 | 昇格 |")
        )
        row = _row(report, "R1")
        assert row["stated"]["priority"] == "P2"
        assert _kinds(row) == ["priority_mismatch"]
        assert "P3 から書き換えている" in row["issues"][0]["message"]

    def test_rewritten_priority_that_ends_on_the_band_is_ok(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 監査記録の欠落 | 3 | 3 | D1 C0 X0 P2 A2 | 31 | P2→P3 | 戻した |")
        )
        assert report["status"] == "ok"

    def test_missing_modifier_is_not_assumed_to_be_zero(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 導線の迷子 | 4 | 3 | D=2,C=2,P=1,A=1 | 45 | P2 | 根拠 |")
        )
        row = _row(report, "R1")
        assert report["status"] == "mismatch"
        assert row["status"] == "unverifiable"
        assert "X が無い" in row["issues"][0]["message"]
        assert "expected" not in row

    def test_conflicting_duplicate_modifier_is_unverifiable(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 導線の迷子 | 4 | 3 | D2 D3 C2 X0 P1 A1 | 45 | P2 | 根拠 |")
        )
        row = _row(report, "R1")
        assert row["status"] == "unverifiable"
        assert "D が2回" in row["issues"][0]["message"]

    def test_repeated_modifier_with_same_value_is_accepted(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 返金額の誤り | 4 | 4 | D2 D2 C2 X0 P2 A0 | 61 | P1 | 根拠 |")
        )
        assert report["status"] == "ok"

    @pytest.mark.parametrize(
        ("row", "fragment"),
        [
            ("| R1 | s | 6 | 3 | D2 C2 X0 P1 A1 | 45 | P2 | r |", "I=6 は範囲外"),
            ("| R1 | s | 4 | 0 | D2 C2 X0 P1 A1 | 45 | P2 | r |", "L=0 は範囲外"),
            ("| R1 | s | 4 | 3 | D4 C2 X0 P1 A1 | 45 | P2 | r |", "D=4 は範囲外"),
            ("| R1 | s | 4 | 3 | D2 C2 X0 P1 A-1 | 45 | P2 | r |", "A=-1 は範囲外"),
        ],
    )
    def test_out_of_range_inputs_are_unverifiable(self, row: str, fragment: str) -> None:
        report = check_risk_tables(_table(row))
        checked = _row(report, "R1")
        assert checked["status"] == "unverifiable"
        assert "out_of_range" in _kinds(checked)
        assert any(fragment in issue["message"] for issue in checked["issues"])

    @pytest.mark.parametrize(
        ("row", "fragment"),
        [
            ("| R1 | s | 高 | 3 | D2 C2 X0 P1 A1 | 45 | P2 | r |", "I を整数として読めない"),
            ("| R1 | s | 4 | 3〜4 | D2 C2 X0 P1 A1 | 45 | P2 | r |", "L を整数として読めない"),
            ("| R1 | s | 4 | 3 | D2 C2 X0 P1 A1 | 約45 | P2 | r |", "点数を数値として読めない"),
            ("| R1 | s | 4 | 3 | D2 C2 X0 P1 A1 |  | P2 | r |", "点数を数値として読めない（空欄）"),
            ("| R1 | s | 4 | 3 | D2 C2 X0 P1 A1 | 45 | 高 | r |", "優先度を P0〜P3 として読めない"),
        ],
    )
    def test_unreadable_cells_are_unverifiable(self, row: str, fragment: str) -> None:
        report = check_risk_tables(_table(row))
        checked = _row(report, "R1")
        assert checked["status"] == "unverifiable"
        assert any(fragment in issue["message"] for issue in checked["issues"])
        assert report["summary"]["unverifiable"] == 1

    def test_short_row_is_unverifiable_instead_of_crashing(self) -> None:
        report = check_risk_tables(_table("| R1 | s | 4 |"))
        row = _row(report, "R1")
        assert row["status"] == "unverifiable"
        assert len(row["issues"]) >= 3

    def test_markup_around_values_is_ignored(self) -> None:
        report = check_risk_tables(
            _table("| **R1** | 返金額の誤り | 4 | 4 | `D2 C2 X0 P2 A0` | **61** | `P1` | 根拠 |")
        )
        assert report["status"] == "ok"
        assert _row(report, "R1")["status"] == "ok"


class TestSeparateModifierColumns:
    HEADER = (
        "| id | シナリオ | I | L | D | C | X | P | A | raw | score | 優先度 | 理由 |\n"
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|\n"
    )

    def test_japanese_headers_and_raw_column(self) -> None:
        text = (
            self.HEADER
            + "| R1 | 認証の入口が通らない | 5 | 4 | 2 | 3 | 3 | 3 | 1 | 100 | 81 | P0 | 根拠 |\n"
        )
        report = check_risk_tables(text)
        assert report["status"] == "ok"
        assert "raw" in report["tables"][0]["columns"]

    def test_raw_mismatch_is_reported(self) -> None:
        text = (
            self.HEADER
            + "| R1 | 認証の入口が通らない | 5 | 4 | 2 | 3 | 3 | 3 | 1 | 102 | 81 | P0 | 根拠 |\n"
        )
        row = _row(check_risk_tables(text), "R1")
        assert row["status"] == "mismatch"
        assert _kinds(row) == ["raw_mismatch"]
        assert row["stated"]["raw"] == 102

    def test_unreadable_raw_is_unverifiable(self) -> None:
        text = (
            self.HEADER
            + "| R1 | 認証の入口が通らない | 5 | 4 | 2 | 3 | 3 | 3 | 1 | - | 81 | P0 | 根拠 |\n"
        )
        row = _row(check_risk_tables(text), "R1")
        assert row["status"] == "unverifiable"
        assert "raw を整数として読めない" in row["issues"][0]["message"]

    def test_missing_modifier_column_is_unverifiable(self) -> None:
        text = (
            "| id | I | L | D | C | P | A | score | priority |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
            "| R1 | 4 | 3 | 2 | 2 | 1 | 1 | 45 | P2 |\n"
        )
        row = _row(check_risk_tables(text), "R1")
        assert row["status"] == "unverifiable"
        assert "補正 X の列が無い" in row["issues"][0]["message"]

    def test_unreadable_modifier_column_value(self) -> None:
        text = self.HEADER + "| R1 | s | 5 | 4 | 中 | 3 | 3 | 3 | 1 | 100 | 81 | P0 | r |\n"
        row = _row(check_risk_tables(text), "R1")
        assert row["status"] == "unverifiable"
        assert "D を整数として読めない" in row["issues"][0]["message"]

    def test_header_annotations_in_parentheses_are_ignored(self) -> None:
        text = (
            "| id | I（影響） | L (likelihood) | 補正 | スコア | 優先度 |\n"
            "|---|---|---|---|---|---|\n"
            "| R1 | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P1 |\n"
        )
        assert check_risk_tables(text)["status"] == "ok"


class TestScorePrecision:
    """整数の点数は文書の式、小数1桁の点数は Local Mode の出力に合わせて検算する。"""

    def test_one_decimal_score_is_checked_at_one_decimal(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61.3 | P1 | 根拠 |")
        )
        assert report["status"] == "ok"
        assert _row(report, "R1")["expected"]["score"] == 61.3

    def test_one_decimal_mismatch(self) -> None:
        report = check_risk_tables(
            _table("| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61.0 | P1 | 根拠 |")
        )
        assert _kinds(_row(report, "R1")) == ["score_mismatch"]

    def test_band_edge_follows_the_precision_of_the_stated_score(self) -> None:
        """raw=68 は 54.84。整数なら 55 で P1、小数1桁なら 54.8 で P2。"""
        integer = check_risk_tables(_table("| R1 | s | 4 | 4 | D2 C0 X0 P0 A0 | 55 | P1 | r |"))
        decimal = check_risk_tables(_table("| R1 | s | 4 | 4 | D2 C0 X0 P0 A0 | 54.8 | P2 | r |"))
        crossed = check_risk_tables(_table("| R1 | s | 4 | 4 | D2 C0 X0 P0 A0 | 55 | P2 | r |"))
        assert integer["status"] == "ok"
        assert decimal["status"] == "ok"
        assert _kinds(_row(crossed, "R1")) == ["priority_mismatch"]

    def test_automation_credit_can_clamp_score_to_zero(self) -> None:
        report = check_risk_tables(_table("| R1 | s | 1 | 1 | D0 C0 X0 P0 A3 | 0 | P3 | r |"))
        assert report["status"] == "ok"
        assert _row(report, "R1")["expected"]["raw"] == -2


class TestTableDiscovery:
    def test_document_without_risk_table(self) -> None:
        report = check_risk_tables("# 設計\n\n| tc_id | priority |\n|---|---|\n| TC-1 | P0 |\n")
        assert report["status"] == "no_risk_table"
        assert report["summary"]["rows"] == 0

    def test_header_only_risk_table_is_not_ok(self) -> None:
        report = check_risk_tables(HEADER)
        assert report["status"] == "no_risk_table"
        assert report["summary"]["tables"] == 1

    def test_tables_inside_code_fences_are_ignored(self) -> None:
        text = "```md\n" + HEADER + "| R1 | s | 5 | 3 | D2 C2 X2 P2 A0 | 76 | P0 | r |\n```\n"
        assert check_risk_tables(text)["status"] == "no_risk_table"

    def test_tilde_fence_is_ignored_and_later_table_is_checked(self) -> None:
        text = (
            "~~~\n"
            + HEADER
            + "| R0 | s | 5 | 3 | D2 C2 X2 P2 A0 | 76 | P0 | r |\n~~~\n\n"
            + _table("| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P1 | 根拠 |")
        )
        report = check_risk_tables(text)
        assert [row["id"] for row in report["rows"]] == ["R1"]
        assert report["status"] == "ok"

    def test_multiple_risk_tables_and_line_numbers(self) -> None:
        text = (
            _table("| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P1 | 根拠 |")
            + "\n本文\n\n"
            + HEADER
            + "| R2 | 出荷後のキャンセル | 5 | 3 | D2 C2 X2 P2 A0 | 76 | P0 | 根拠 |\n"
        )
        report = check_risk_tables(text)
        assert report["summary"]["tables"] == 2
        assert [table["line"] for table in report["tables"]] == [3, 9]
        assert _row(report, "R1")["line"] == 5
        assert _row(report, "R2")["line"] == 11
        assert report["status"] == "mismatch"

    def test_table_without_priority_column_checks_score_only(self) -> None:
        text = (
            "| id | I | L | modifiers | score |\n|---|---|---|---|---|\n"
            "| R1 | 4 | 4 | D2 C2 X0 P2 A0 | 61 |\n"
        )
        report = check_risk_tables(text)
        assert report["status"] == "ok"
        assert report["tables"][0]["priority_checked"] is False
        assert "点数だけを検算した" in render_text(report, "design.md")

    def test_table_without_score_column_is_not_a_risk_table(self) -> None:
        text = "| id | I | L |\n|---|---|---|\n| R1 | 4 | 4 |\n"
        assert check_risk_tables(text)["status"] == "no_risk_table"

    def test_pipe_line_without_separator_is_not_a_table(self) -> None:
        text = "| id | I | L | modifiers | score |\n| R1 | 4 | 4 | D2 C2 X0 P2 A0 | 61 |\n"
        assert check_risk_tables(text)["status"] == "no_risk_table"

    def test_escaped_pipe_stays_inside_the_cell(self) -> None:
        report = check_risk_tables(
            _table(r"| R1 | A \| B の取り違え | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P1 | 根拠 |")
        )
        assert report["status"] == "ok"

    def test_first_column_is_used_when_there_is_no_id_column(self) -> None:
        text = (
            "| リスク | I | L | modifiers | score | priority |\n|---|---|---|---|---|---|\n"
            "| 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P1 |\n"
        )
        report = check_risk_tables(text)
        assert report["rows"][0]["id"] == "返金額の誤り"


class TestRenderText:
    def test_lists_only_rows_that_need_attention(self) -> None:
        report = check_risk_tables(
            _table(
                "| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P1 | 根拠 |",
                "| R2 | 出荷後のキャンセル | 5 | 3 | D2 C2 X2 P2 A0 | 76 | P0 | 根拠 |",
                "| R3 | 導線の迷子 | 4 | 3 | D=2,C=2,P=1,A=1 | 45 | P2 | 根拠 |",
            )
        )
        text = render_text(report, "design.md")
        assert "リスク表の検算: design.md" in text
        assert "R1" not in text
        assert "不一致 6行目 R2: 点数 76 → 式では 61。優先度 P0 → 式では P1" in text
        assert "I=5 L=3 D=2 C=2 X=2 P=2 A=0" in text
        assert "検算不可 7行目 R3: 補正を読めない（X が無い）" in text
        assert "結果: 3行中、一致 1・不一致 1・検算不可 1" in text

    def test_no_risk_table_message(self) -> None:
        text = render_text(check_risk_tables("本文だけ\n"), "design.md")
        assert "検算できるリスク表が無い" in text


class TestCli:
    def _write(self, tmp_path: Path, text: str) -> Path:
        path = tmp_path / "design.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_ok_returns_0(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = self._write(
            tmp_path, _table("| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P1 | 根拠 |")
        )
        assert main(["check", "risk", "--input", str(path)]) == 0
        assert "結果: 1行中、一致 1・不一致 0・検算不可 0" in capsys.readouterr().out

    def test_mismatch_returns_2(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = self._write(
            tmp_path,
            _table("| R1 | 出荷後のキャンセル | 5 | 3 | D2 C2 X2 P2 A0 | 76 | P0 | 根拠 |"),
        )
        assert main(["check", "risk", "--input", str(path)]) == 2
        assert "不一致 5行目 R1" in capsys.readouterr().out

    def test_unverifiable_returns_2(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path, _table("| R1 | 導線の迷子 | 4 | 3 | D=2,C=2,P=1,A=1 | 45 | P2 | r |")
        )
        assert main(["check", "risk", "--input", str(path)]) == 2

    def test_no_risk_table_returns_2(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, "# 設計\n\n本文だけ\n")
        assert main(["check", "risk", "--input", str(path)]) == 2

    def test_json_format(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = self._write(
            tmp_path,
            _table("| R1 | 出荷後のキャンセル | 5 | 3 | D2 C2 X2 P2 A0 | 76 | P0 | 根拠 |"),
        )
        assert main(["check", "risk", "--input", str(path), "--format", "json"]) == 2
        payload = json.loads(capsys.readouterr().out)
        assert payload["input"] == str(path)
        assert payload["status"] == "mismatch"
        assert payload["formula"].startswith("raw = 4*(I*L)")
        assert payload["rows"][0]["expected"] == {"raw": 76, "score": 61, "priority": "P1"}

    def test_missing_file_returns_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["check", "risk", "--input", str(tmp_path / "missing.md")]) == 1
        assert "Error:" in capsys.readouterr().err

    def test_non_utf8_file_returns_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "design.md"
        path.write_bytes("リスク".encode("shift_jis"))
        assert main(["check", "risk", "--input", str(path)]) == 1
        assert "Error:" in capsys.readouterr().err

    def test_global_flags_do_not_change_the_result(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path, _table("| R1 | 返金額の誤り | 4 | 4 | D2 C2 X0 P2 A0 | 61 | P1 | 根拠 |")
        )
        assert main(["--dry-run", "--verbose", "check", "risk", "--input", str(path)]) == 0

    def test_repository_example_passes(self, capsys: pytest.CaptureFixture[str]) -> None:
        example = Path(__file__).parent.parent / "examples/markdown/order-cancel.risk-table.md"
        assert main(["check", "risk", "--input", str(example)]) == 0
        assert "結果: 4行中、一致 4・不一致 0・検算不可 0" in capsys.readouterr().out

    def test_target_is_required(self) -> None:
        with pytest.raises(SystemExit) as error:
            main(["check"])
        assert error.value.code == 2

    def test_file_is_not_modified(self, tmp_path: Path) -> None:
        text = _table("| R1 | 出荷後のキャンセル | 5 | 3 | D2 C2 X2 P2 A0 | 76 | P0 | 根拠 |")
        path = self._write(tmp_path, text)
        main(["check", "risk", "--input", str(path)])
        assert path.read_text(encoding="utf-8") == text
