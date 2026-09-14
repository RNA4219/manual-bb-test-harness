"""要件評価snapshotと固定期間の実績を比較する。採点policyは変更しない。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path
from statistics import mean

from bb_harness.schema_validation import validate_artifact

THRESHOLDS = (60, 70, 80, 85, 90)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_cases(path: Path) -> tuple[dict, list[dict], dict]:
    raw = path.read_bytes()
    dataset = json.loads(raw)
    require(dataset["data_kind"] in {"real", "synthetic"}, "data_kindはreal/syntheticです")
    days = dataset["window_days"]
    require(type(days) is int and days > 0, "window_daysは正の整数です")
    require(isinstance(dataset["cases"], list), "casesは配列です")
    projects, fingerprints = set(), set()
    rows = []
    excluded = {"incomplete_outcomes": 0, "unscored": 0}
    for item in dataset["cases"]:
        identifier = item["project_id"]
        require(isinstance(identifier, str) and bool(identifier.strip()), "案件IDが空です")
        require(identifier not in projects, "案件IDが重複しています。群をまたいだ重複も不可です")
        projects.add(identifier)
        require(item["split"] in {"calibration", "holdout"}, "splitが不正です")
        start, end = (
            date.fromisoformat(item["evaluated_at"]),
            date.fromisoformat(item["window_end"]),
        )
        require((end - start).days == days, "観測期間がwindow_daysと一致しません")
        base = path.resolve().parent
        relative = Path(item["report_path"])
        snapshot = (base / relative).resolve()
        require(
            not relative.is_absolute() and snapshot.is_relative_to(base),
            "snapshotはdatasetディレクトリ内の相対パスにしてください",
        )
        content = snapshot.read_bytes()
        require(
            hashlib.sha256(content).hexdigest() == item["report_sha256"],
            "snapshotのSHA-256が一致しません",
        )
        report = json.loads(content)
        validate_artifact(report, "requirements_confidence.schema.json")
        fingerprint = report["input_sha256"]
        require(fingerprint not in fingerprints, "同じ入力snapshotを複数案件に重複計上できません")
        fingerprints.add(fingerprint)
        require(type(item["complete"]) is bool, "completeはbooleanです")
        defects, hours = item["defects"], item["rework_hours"]
        require(
            defects is None or type(defects) is int and defects >= 0,
            "defectsは0以上の整数またはnullです",
        )
        require(
            hours is None or type(hours) in (int, float) and math.isfinite(hours) and hours >= 0,
            "rework_hoursは0以上の有限数またはnullです",
        )
        if not item["complete"] or defects is None or hours is None:
            excluded["incomplete_outcomes"] += 1
            continue
        require(end <= date.today(), "未終了の観測期間をcompleteにできません")
        if report["score"] is None or report["counts"]["requirements"] == 0:
            excluded["unscored"] += 1
            continue
        rows.append(
            {
                "split": item["split"],
                "score": report["score"],
                "band": report["band"],
                "requirements": report["counts"]["requirements"],
                "defects": defects,
                "rework_hours": hours,
                "adverse": defects > 0 or hours > 0,
            }
        )
    return (
        {
            "data_kind": dataset["data_kind"],
            "window_days": days,
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "total_cases": len(projects),
        },
        rows,
        excluded,
    )


def ranks(values: list[float]) -> list[float]:
    positions = {}
    for number, value in enumerate(sorted(values), 1):
        positions.setdefault(value, []).append(number)
    return [mean(positions[value]) for value in values]


def spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3:
        return None
    x, y = ranks(left), ranks(right)
    avg_x, avg_y = mean(x), mean(y)
    denominator = math.sqrt(sum((v - avg_x) ** 2 for v in x) * sum((v - avg_y) ** 2 for v in y))
    return (
        round(sum((a - avg_x) * (b - avg_y) for a, b in zip(x, y, strict=True)) / denominator, 4)
        if denominator
        else None
    )


def threshold_metrics(rows: list[dict], threshold: int) -> dict:
    fn = sum(row["adverse"] and row["score"] >= threshold for row in rows)
    fp = sum(not row["adverse"] and row["score"] < threshold for row in rows)
    tp = sum(row["adverse"] and row["score"] < threshold for row in rows)
    tn = len(rows) - fn - fp - tp
    return {
        "threshold": threshold,
        "true_positive": tp,
        "false_negative": fn,
        "false_positive": fp,
        "true_negative": tn,
        "weighted_loss": round((5 * fn + fp) / len(rows), 4) if rows else None,
    }


def describe(rows: list[dict]) -> dict:
    bands = {}
    for band in ("low", "medium", "high"):
        group = [row for row in rows if row["band"] == band]
        bands[band] = {
            "cases": len(group),
            "adverse_rate": round(mean(row["adverse"] for row in group), 4) if group else None,
            "mean_defects_per_requirement": round(
                mean(row["defects"] / row["requirements"] for row in group), 4
            )
            if group
            else None,
            "mean_rework_hours": round(mean(row["rework_hours"] for row in group), 4)
            if group
            else None,
        }
    return {
        "cases": len(rows),
        "adverse_cases": sum(row["adverse"] for row in rows),
        "bands": bands,
        "thresholds": [threshold_metrics(rows, t) for t in THRESHOLDS],
        "score_defect_density_spearman": spearman(
            [row["score"] for row in rows], [row["defects"] / row["requirements"] for row in rows]
        ),
        "score_rework_density_spearman": spearman(
            [row["score"] for row in rows],
            [row["rework_hours"] / row["requirements"] for row in rows],
        ),
    }


def analyze(path: Path) -> dict:
    meta, rows, excluded = load_cases(path)
    groups = {
        key: [row for row in rows if row["split"] == key] for key in ("calibration", "holdout")
    }
    sufficient = all(
        len(group) >= minimum
        and sum(r["adverse"] for r in group) >= 3
        and sum(not r["adverse"] for r in group) >= 3
        for group, minimum in ((groups["calibration"], 20), (groups["holdout"], 10))
    )
    result = {
        **meta,
        "status": "synthetic_only"
        if meta["data_kind"] == "synthetic"
        else "exploratory_proposal"
        if sufficient
        else "insufficient_data",
        "excluded": excluded,
        "groups": {key: describe(group) for key, group in groups.items()},
        "candidate": None,
        "policy_changed": False,
        "limitations": [
            "相関は因果関係や正しさの確率を示しません。",
            "最低件数は探索の条件であり、精度を保証しません。",
            "重み・重大度上限・Ready/Gate条件は変更していません。",
        ],
    }
    if sufficient and meta["data_kind"] == "real":
        choices = result["groups"]["calibration"]["thresholds"]
        # 保留群の結果は閾値の選択へ一切使わない。
        chosen = min(
            choices,
            key=lambda row: (
                row["false_negative"] * 5 + row["false_positive"],
                row["false_negative"],
                abs(row["threshold"] - 85),
                row["threshold"],
            ),
        )
        result["candidate"] = {
            "threshold": chosen["threshold"],
            "calibration": chosen,
            "holdout": threshold_metrics(groups["holdout"], chosen["threshold"]),
            "baseline_holdout": threshold_metrics(groups["holdout"], 85),
            "apply_automatically": False,
        }
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists(), "出力先は新規ディレクトリにしてください")
    result = analyze(args.input)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 要件信頼度と実績の比較",
        "",
        f"状態: `{result['status']}`",
        "",
        f"案件数: {result['total_cases']}、除外: {sum(result['excluded'].values())}",
        "",
        "| 群 | 分析件数 | 要件起因の問題あり |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| {key} | {group['cases']} | {group['adverse_cases']} |"
        for key, group in result["groups"].items()
    )
    lines += ["", "採点policyの変更はありません。詳細はanalysis.jsonを参照してください。", ""]
    lines.extend("- " + text for text in result["limitations"])
    (args.output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(result["status"])


if __name__ == "__main__":
    main()
