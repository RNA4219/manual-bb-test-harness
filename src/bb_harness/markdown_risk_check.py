"""Markdownのリスク表を、文書化した式で検算する。

Skillを読んで設計書を直接書く場合、点数と優先度は人やモデルの手計算になる。
ここでは表の入力値（I、L、補正）から点数と優先度を計算し直し、書かれた値と比べる。
読めない行と範囲外の値は推測で補わず、検算できない行として報告する。
"""

from __future__ import annotations

import re
from typing import Any

from bb_harness.risk_policy import (
    RISK_FORMULA,
    calculate_raw_risk,
    calculate_risk_score,
    priority_for_score,
    scale_raw_risk,
)

MODIFIER_KEYS = ("D", "C", "X", "P", "A")

_COLUMN_ALIASES: dict[str, set[str]] = {
    "id": {"id", "risk_id", "risk id"},
    "impact": {"i", "impact", "影響", "影響度"},
    "likelihood": {"l", "likelihood", "起きやすさ", "発生可能性", "可能性"},
    "modifiers": {"modifiers", "modifier", "補正", "補正値"},
    "D": {"d", "detectability", "detectability_difficulty"},
    "C": {"c", "change", "change_surface"},
    "X": {"x", "externality"},
    "P": {"p", "privilege"},
    "A": {"a", "automation", "automation_credit", "auto_coverage_credit"},
    "raw": {"raw"},
    "score": {"score", "risk_score", "risk score", "スコア", "点数"},
    "priority": {"priority", "優先度"},
}

_MODIFIER_NAMES: dict[str, str] = {
    "d": "D",
    "detectability": "D",
    "detectability_difficulty": "D",
    "c": "C",
    "change": "C",
    "change_surface": "C",
    "x": "X",
    "externality": "X",
    "p": "P",
    "privilege": "P",
    "a": "A",
    "automation": "A",
    "automation_credit": "A",
    "auto_coverage_credit": "A",
}

_RANGES: dict[str, tuple[int, int]] = {
    "I": (1, 5),
    "L": (1, 5),
    "D": (0, 3),
    "C": (0, 3),
    "X": (0, 3),
    "P": (0, 3),
    "A": (0, 3),
}

_SEPARATOR_CELL = re.compile(r"^:?-+:?$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_INTEGER = re.compile(r"^-?\d+$")
_NUMBER = re.compile(r"^(\d+)(\.\d+)?$")
_MODIFIER_TOKEN = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_]+)\s*[=:＝：]?\s*(-?\d+)(?![\d.])")
_PRIORITY_TOKEN = re.compile(r"(?<![A-Za-z0-9])P[0-3](?![0-9])")
_MARKUP = str.maketrans("", "", "*`")
_PROMOTION_HINT = "。リスク表は式の帯のまま書き、上げるときはケースの優先度に理由を書く"


def _split_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", text)]


def _is_separator(line: str) -> bool:
    cells = _split_row(line)
    return bool(cells) and all(_SEPARATOR_CELL.match(cell) for cell in cells)


def _clean(cell: str) -> str:
    return cell.translate(_MARKUP).strip()


def _normalize_header(cell: str) -> str:
    text = re.split(r"[(（]", _clean(cell), maxsplit=1)[0]
    return text.strip().lower()


def _map_columns(header: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, cell in enumerate(header):
        name = _normalize_header(cell)
        for key, aliases in _COLUMN_ALIASES.items():
            if name in aliases and key not in columns:
                columns[key] = index
    return columns


def _find_tables(lines: list[str]) -> list[dict[str, Any]]:
    """コードブロックの外にあるpipe tableを、見出し行の行番号つきで返す。"""
    tables: list[dict[str, Any]] = []
    in_fence = False
    index = 0
    while index < len(lines):
        line = lines[index]
        if _FENCE.match(line):
            in_fence = not in_fence
            index += 1
            continue
        is_header = (
            not in_fence
            and line.lstrip().startswith("|")
            and index + 1 < len(lines)
            and lines[index + 1].lstrip().startswith("|")
            and _is_separator(lines[index + 1])
        )
        if not is_header:
            index += 1
            continue
        header = _split_row(line)
        body: list[tuple[int, list[str]]] = []
        cursor = index + 2
        while cursor < len(lines) and lines[cursor].lstrip().startswith("|"):
            body.append((cursor + 1, _split_row(lines[cursor])))
            cursor += 1
        tables.append({"line": index + 1, "header": header, "body": body})
        index = cursor
    return tables


def _issue(kind: str, message: str, **detail: Any) -> dict[str, Any]:
    return {"kind": kind, "message": message, **detail}


def _read_integer(cells: list[str], index: int, label: str) -> tuple[int | None, str | None]:
    text = _clean(cells[index]) if index < len(cells) else ""
    if not _INTEGER.match(text):
        return None, f"{label} を整数として読めない（{text or '空欄'}）"
    return int(text), None


def _read_modifier_cell(text: str) -> tuple[dict[str, int], list[str]]:
    values: dict[str, int] = {}
    problems: list[str] = []
    for name, number in _MODIFIER_TOKEN.findall(_clean(text)):
        key = _MODIFIER_NAMES.get(name.lower())
        if key is None:
            continue
        if key in values and values[key] != int(number):
            problems.append(f"{key} が2回あり値が違う")
            continue
        values[key] = int(number)
    missing = [key for key in MODIFIER_KEYS if key not in values]
    if missing:
        problems.append("補正を読めない（" + "・".join(missing) + " が無い）")
    return values, problems


def _read_inputs(
    cells: list[str], columns: dict[str, int]
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    inputs: dict[str, int] = {}
    issues: list[dict[str, Any]] = []
    for label, column in (("I", "impact"), ("L", "likelihood")):
        value, problem = _read_integer(cells, columns[column], label)
        if value is None:
            issues.append(_issue("unreadable", str(problem)))
        else:
            inputs[label] = value
    if "modifiers" in columns:
        index = columns["modifiers"]
        values, problems = _read_modifier_cell(cells[index] if index < len(cells) else "")
        inputs.update(values)
        issues.extend(_issue("unreadable", problem) for problem in problems)
    else:
        for key in MODIFIER_KEYS:
            if key not in columns:
                issues.append(_issue("unreadable", f"補正 {key} の列が無い"))
                continue
            value, problem = _read_integer(cells, columns[key], key)
            if value is None:
                issues.append(_issue("unreadable", str(problem)))
            else:
                inputs[key] = value
    for key, value in inputs.items():
        low, high = _RANGES[key]
        if not low <= value <= high:
            issues.append(
                _issue("out_of_range", f"{key}={value} は範囲外（{low}〜{high}）", stated=value)
            )
    return inputs, issues


def _expected(inputs: dict[str, int], one_decimal: bool) -> dict[str, Any]:
    arguments = [inputs[key] for key in ("I", "L", *MODIFIER_KEYS)]
    raw = calculate_raw_risk(*arguments)
    score: float | int = (
        round(scale_raw_risk(raw), 1) if one_decimal else calculate_risk_score(*arguments)
    )
    return {"raw": int(raw), "score": score, "priority": priority_for_score(score)}


def _check_row(line: int, cells: list[str], columns: dict[str, int]) -> dict[str, Any]:
    id_index = columns.get("id", 0)
    row: dict[str, Any] = {
        "line": line,
        "id": _clean(cells[id_index]) if id_index < len(cells) else "",
        "status": "ok",
        "issues": [],
    }
    inputs, issues = _read_inputs(cells, columns)
    row["inputs"] = inputs

    score_index = columns["score"]
    score_text = _clean(cells[score_index]) if score_index < len(cells) else ""
    score_match = _NUMBER.match(score_text)
    if not score_match:
        issues.append(_issue("unreadable", f"点数を数値として読めない（{score_text or '空欄'}）"))

    stated_priority: str | None = None
    rewritten_from: str | None = None
    if "priority" in columns:
        index = columns["priority"]
        tokens = _PRIORITY_TOKEN.findall(_clean(cells[index]) if index < len(cells) else "")
        if not tokens:
            issues.append(_issue("unreadable", "優先度を P0〜P3 として読めない"))
        else:
            # 「P3→P2」のように書き換えた跡があるセルは、最後の値を最終の優先度として扱う。
            stated_priority = tokens[-1]
            if len(set(tokens)) > 1:
                rewritten_from = tokens[0]

    if any(issue["kind"] in {"unreadable", "out_of_range"} for issue in issues):
        row["status"] = "unverifiable"
        row["issues"] = issues
        return row

    assert score_match is not None
    one_decimal = score_match.group(2) is not None
    stated_score: float | int = float(score_text) if one_decimal else int(score_text)
    expected = _expected(inputs, one_decimal)
    row["expected"] = expected
    row["stated"] = {"score": stated_score, "priority": stated_priority}

    if stated_score != expected["score"]:
        issues.append(
            _issue(
                "score_mismatch",
                f"点数 {score_text} → 式では {expected['score']}",
                stated=stated_score,
                expected=expected["score"],
            )
        )
    if stated_priority is not None and stated_priority != expected["priority"]:
        note = f"（セルで {rewritten_from} から書き換えている）" if rewritten_from else ""
        # P0 が最も高い。式の帯より高い値は、リスク表ではなくケース側で扱う決まり。
        hint = _PROMOTION_HINT if stated_priority < expected["priority"] else ""
        issues.append(
            _issue(
                "priority_mismatch",
                f"優先度 {stated_priority} → 式では {expected['priority']}{note}{hint}",
                stated=stated_priority,
                expected=expected["priority"],
            )
        )
    if "raw" in columns:
        raw_value, problem = _read_integer(cells, columns["raw"], "raw")
        if raw_value is None:
            issues.append(_issue("unreadable", str(problem)))
            row["status"] = "unverifiable"
        elif raw_value != expected["raw"]:
            row["stated"]["raw"] = raw_value
            issues.append(
                _issue(
                    "raw_mismatch",
                    f"raw {raw_value} → 式では {expected['raw']}",
                    stated=raw_value,
                    expected=expected["raw"],
                )
            )
    if row["status"] == "ok" and issues:
        row["status"] = "mismatch"
    row["issues"] = issues
    return row


def check_risk_tables(text: str) -> dict[str, Any]:
    """Markdown本文のリスク表を検算し、行ごとの結果と集計を返す。

    I・L・点数の列を持つ表をリスク表とみなす。statusは、全行が一致すれば ``ok``、
    不一致または検算できない行があれば ``mismatch``、リスク表または行が無ければ
    ``no_risk_table`` となる。
    """
    tables: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for table in _find_tables(text.splitlines()):
        columns = _map_columns(table["header"])
        if not {"impact", "likelihood", "score"} <= columns.keys():
            continue
        checked = [_check_row(line, cells, columns) for line, cells in table["body"]]
        tables.append(
            {
                "line": table["line"],
                "rows": len(checked),
                "columns": sorted(columns),
                "priority_checked": "priority" in columns,
            }
        )
        rows.extend(checked)

    kinds = [issue["kind"] for row in rows for issue in row["issues"]]
    summary = {
        "tables": len(tables),
        "rows": len(rows),
        "ok": sum(row["status"] == "ok" for row in rows),
        "mismatch": sum(row["status"] == "mismatch" for row in rows),
        "unverifiable": sum(row["status"] == "unverifiable" for row in rows),
        "score_mismatch": kinds.count("score_mismatch"),
        "priority_mismatch": kinds.count("priority_mismatch"),
        "raw_mismatch": kinds.count("raw_mismatch"),
    }
    if not rows:
        status = "no_risk_table"
    elif summary["ok"] == len(rows):
        status = "ok"
    else:
        status = "mismatch"
    return {
        "formula": RISK_FORMULA,
        "status": status,
        "summary": summary,
        "tables": tables,
        "rows": rows,
    }


def render_text(report: dict[str, Any], source: str) -> str:
    """検算結果を、人が読む短い日本語の文面にする。"""
    lines = [f"リスク表の検算: {source}"]
    summary = report["summary"]
    if report["status"] == "no_risk_table":
        lines.append("検算できるリスク表が無い（I・L・点数の列を持つ表と、その行が必要）。")
        return "\n".join(lines) + "\n"
    for row in report["rows"]:
        if row["status"] == "ok":
            continue
        mark = "不一致" if row["status"] == "mismatch" else "検算不可"
        detail = "。".join(issue["message"] for issue in row["issues"])
        inputs = " ".join(f"{key}={value}" for key, value in row["inputs"].items())
        suffix = f"（{inputs}）" if inputs and row["status"] == "mismatch" else ""
        lines.append(f"  {mark} {row['line']}行目 {row['id']}: {detail}{suffix}")
    lines.append(
        f"結果: {summary['rows']}行中、一致 {summary['ok']}・"
        f"不一致 {summary['mismatch']}・検算不可 {summary['unverifiable']}"
    )
    if any(not table["priority_checked"] for table in report["tables"]):
        lines.append("注: 優先度の列が無い表は、点数だけを検算した。")
    return "\n".join(lines) + "\n"
