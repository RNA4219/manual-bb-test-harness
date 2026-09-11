"""記録された要確認事項とレビュー根拠から要件定義の信頼度を計算する。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from bb_harness.schema_validation import validate_artifact
from bb_harness.tools._shared.spec_ingest_markdown import read_markdown
from bb_harness.tools.spec_ingest import extract_markdown_sections, ingest_markdown_spec

WEIGHTS = {"critical": 8, "high": 4, "medium": 2, "low": 1}
POLICY = "requirements-confidence-1"
TAG = re.compile(r"\[要確認\]|【要確認】|\b(?:TBD|TODO)\b", re.IGNORECASE)
PLACEHOLDER = "[NO ACCEPTANCE CRITERIA FOUND]"
LIMITATIONS = [
    "点数は記録された不確実性とレビューのルール評価であり、正しさの確率ではありません。",
    "タグのない曖昧さ・矛盾・未記載要件は自動発見しません。意味レビューで登録してください。",
    "根拠の内容とoracleの意味的正しさは自動保証しません。高得点もReadyやリリースGoではありません。",
    "重み・閾値は初期policyであり、実案件データによる統計的な校正は未実施です。",
]


def canonical(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"^\[[ xX]\]\s*", "", text)
    text = re.sub(r"^(?:AC|BR)-\d+\s*:\s*", "", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def uncertain(text: str, *, broad: bool = False) -> bool:
    return bool(TAG.search(text) or (broad and re.search(r"未定|未確定|要確認", text)))


def _digest(value: Any) -> str:
    content = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_input(path: Path) -> tuple[dict, list[dict]]:
    """Markdownの既存取込を使い、本文の明示タグを行番号付きで補う。"""
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8")), []
    if path.suffix.lower() not in {".md", ".markdown"}:
        raise ValueError("入力はMarkdownまたはfeature_spec JSONを指定してください")
    text = read_markdown(path)
    feature = ingest_markdown_spec(path)
    aliases = {
        "受入条件": "acceptance_criteria",
        "受け入れ条件": "acceptance_criteria",
        "受入基準": "acceptance_criteria",
        "受け入れ基準": "acceptance_criteria",
        "要件": "acceptance_criteria",
        "機能要件": "acceptance_criteria",
        "requirements": "acceptance_criteria",
        "functional requirements": "acceptance_criteria",
        "業務ルール": "business_rules",
    }
    for name, items in extract_markdown_sections(text).items():
        field = aliases.get(name.strip().lower())
        if field:
            if feature.get(field) == [PLACEHOLDER]:
                feature[field] = []
                feature["assumptions"] = [
                    item
                    for item in feature.get("assumptions", [])
                    if item["text"] != "No acceptance criteria section found in source"
                ]
            feature.setdefault(field, []).extend(items)
    # 文書の未取込部分の変更でもレビューを失効させ、実内容を引用できるようにする。
    feature["source_refs"][0]["excerpt"] = text.strip()
    heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if heading:
        feature["title"] = heading[1].strip()
    # 見出しがあっても本文が空の場合、既存schema互換の取込placeholderを使う。
    if not feature.get("acceptance_criteria"):
        feature["acceptance_criteria"] = [PLACEHOLDER]
    markers = [
        {"text": canonical(line), "location": f"markdown:line:{index}"}
        for index, line in enumerate(text.splitlines(), 1)
        if uncertain(line)
    ]
    return feature, markers


def _unique(items: list[dict], key: str, label: str) -> None:
    values = [item[key] for item in items]
    if len(values) != len(set(values)):
        raise ValueError(f"{label}のIDが重複しています")


def _sources(feature: dict, phase: dict | None) -> dict[str, dict]:
    sources: dict[str, dict] = {}
    for artifact in (feature, phase):
        if artifact is None:
            continue
        _unique(artifact["source_refs"], "id", "source_refs")
        for item in artifact["source_refs"]:
            if not item["id"].strip():
                raise ValueError("空白のsource IDは使えません")
            if item["id"] in sources and sources[item["id"]] != item:
                raise ValueError(f"source IDの内容が衝突しています: {item['id']}")
            sources[item["id"]] = copy.deepcopy(item)
    return sources


def _refs(refs: list[str], sources: dict, *, citable: bool = False) -> None:
    if citable and not refs:
        raise ValueError("確認・解決には引用可能な根拠が必要です")
    for ref in refs:
        if ref not in sources:
            raise ValueError(f"未知のsource_ref: {ref}")
        if citable and not any(sources[ref].get(key, "").strip() for key in ("excerpt", "url")):
            raise ValueError(f"引用内容もURLもないsource_ref: {ref}")


def _issue(identifier: str, text: str, severity: str, kind: str, **extra: Any) -> dict:
    value = {
        "issue_id": identifier,
        "ids": [identifier],
        "kind": kind,
        "severity": severity,
        "text": canonical(text),
        "requirement_ids": [],
        "source_refs": [],
        "locations": [],
        "owner": None,
        "due": None,
        "blocks_ready": False,
        "status": "open",
        "resolution": None,
    }
    value.update(extra)
    if not value["text"]:
        raise ValueError(f"確認事項の本文が空です: {identifier}")
    return value


def _inventory(feature: dict) -> tuple[list[dict], int]:
    grouped: dict[str, dict] = {}
    raw = 0
    for field in ("acceptance_criteria", "business_rules"):
        for index, text in enumerate(feature.get(field, [])):
            text = canonical(text)
            if not text or text == PLACEHOLDER:
                continue
            raw += 1
            item = grouped.setdefault(
                text,
                {
                    "requirement_id": "REQ-" + _digest(text)[:16],
                    "text": text,
                    "locations": [],
                    "reviewed": False,
                },
            )
            item["locations"].append(f"feature/{field}/{index}")
    inventory = sorted(grouped.values(), key=lambda item: item["requirement_id"])
    _unique(inventory, "requirement_id", "要件")
    return inventory, raw


def _collect(feature: dict, phase: dict | None, markers: list[dict], inventory: list[dict]) -> list:
    issues = []
    by_text = {item["text"]: item["requirement_id"] for item in inventory}
    for item in inventory:
        if uncertain(item["text"], broad=True):
            issues.append(
                _issue(
                    "tag:" + item["requirement_id"],
                    item["text"],
                    "medium",
                    "tag",
                    requirement_ids=[item["requirement_id"]],
                    locations=item["locations"].copy(),
                )
            )
    for index, marker in enumerate(markers):
        text = canonical(marker["text"])
        issues.append(
            _issue(
                f"markdown:{index + 1}",
                text,
                "medium",
                "tag",
                locations=[marker["location"]],
                requirement_ids=[by_text[text]] if text in by_text else [],
            )
        )
    if uncertain(feature.get("summary", "")):
        issues.append(
            _issue(
                "feature:summary",
                feature["summary"],
                "medium",
                "tag",
                locations=["feature/summary"],
            )
        )
    for label, artifact in (("feature", feature), ("phase", phase)):
        if artifact is None:
            continue
        _unique(artifact.get("assumptions", []), "id", f"{label} assumptions")
        for item in artifact.get("assumptions", []):
            issues.append(
                _issue(
                    f"{label}:assumption:{item['id']}",
                    item["text"],
                    item["severity"],
                    "assumption",
                    locations=[f"{label}/assumptions/{item['id']}"],
                )
            )
    if phase:
        phase_items = phase["open_questions"] + phase["spec_gaps"]
        _unique(phase_items, "id", "phaseの確認事項")
        for field, text_key in (("open_questions", "question"), ("spec_gaps", "gap")):
            for item in phase[field]:
                issues.append(
                    _issue(
                        f"phase:{item['id']}",
                        item[text_key],
                        item["severity"],
                        text_key,
                        locations=[f"phase/{field}/{item['id']}"],
                        source_refs=item.get("source_refs", []).copy(),
                        owner=item.get("owner"),
                        due=item.get("due"),
                        blocks_ready=item.get("blocks_ready", False),
                    )
                )
    return issues


def _review_metadata(review: dict) -> None:
    reviewer = review["reviewer"]
    if not reviewer or not reviewer.strip() or uncertain(reviewer, broad=True):
        raise ValueError("レビューには評価者を記録してください")
    if not review["reviewed_at"]:
        raise ValueError("レビューにはタイムゾーン付き評価日時が必要です")


def _apply_review(
    review: dict,
    fingerprint: str,
    feature_id: str,
    inventory: list[dict],
    sources: dict,
    issues: list[dict],
) -> None:
    validate_artifact(review, "requirements_review.schema.json")
    if review["feature_id"] != feature_id or review["input_sha256"] != fingerprint:
        raise ValueError("レビューのfeatureまたは入力版が一致しません。再評価してください")
    _unique(review["requirements"], "requirement_id", "要件レビュー")
    _unique(review["findings"], "id", "レビューfinding")
    known = {item["requirement_id"]: item for item in inventory}
    for item in review["requirements"]:
        if item["requirement_id"] not in known:
            raise ValueError(f"未知の要件ID: {item['requirement_id']}")
        _refs(item["source_refs"], sources, citable=item["reviewed"])
        if item["reviewed"]:
            _review_metadata(review)
            if not item["oracle"].strip() or uncertain(item["oracle"], broad=True):
                raise ValueError("レビュー済み要件には具体的なoracleが必要です")
            known[item["requirement_id"]]["reviewed"] = True
    for item in review["findings"]:
        _review_metadata(review)
        _refs(item["source_refs"], sources, citable=True)
        if set(item["requirement_ids"]) - known.keys():
            raise ValueError("findingが未知の要件を参照しています")
        issues.append(
            _issue(
                "review:" + item["id"],
                item["text"],
                item["severity"],
                item["kind"],
                requirement_ids=item["requirement_ids"].copy(),
                source_refs=item["source_refs"].copy(),
                owner=item.get("owner"),
                due=item.get("due"),
                locations=[f"review/findings/{item['id']}"],
            )
        )


def _merge_issues(issues: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for issue in issues:
        text = canonical(issue["text"])
        if text not in grouped:
            grouped[text] = copy.deepcopy(issue)
            continue
        existing = grouped[text]
        for key in ("ids", "requirement_ids", "source_refs", "locations"):
            existing[key] = sorted(set(existing[key]) | set(issue[key]))
        if WEIGHTS[issue["severity"]] > WEIGHTS[existing["severity"]]:
            existing["severity"] = issue["severity"]
        existing["blocks_ready"] |= issue["blocks_ready"]
        for key in ("owner", "due"):
            values = sorted({value for value in (existing[key], issue[key]) if value})
            existing[key] = " / ".join(values) or None
    for item in grouped.values():
        item["issue_id"] = min(item["ids"])
    return sorted(grouped.values(), key=lambda item: item["issue_id"])


def _resolve(review: dict, issues: list[dict], sources: dict) -> None:
    _unique(review["resolutions"], "issue_id", "解決記録")
    by_id = {identifier: issue for issue in issues for identifier in issue["ids"]}
    for resolution in review["resolutions"]:
        _review_metadata(review)
        identifier = resolution["issue_id"]
        if identifier not in by_id:
            raise ValueError(f"解決記録が未知の確認事項を参照しています: {identifier}")
        issue = by_id[identifier]
        if issue["status"] == "resolved":
            raise ValueError("統合された同じ確認事項に解決記録が重複しています")
        _refs(resolution["source_refs"], sources, citable=True)
        if uncertain(resolution["decision"], broad=True):
            raise ValueError("要確認のままの判断を解決として記録できません")
        issue["status"] = "resolved"
        issue["resolution"] = copy.deepcopy(resolution)


def review_template(report: dict) -> dict:
    return {
        "schema_version": "1.0.0",
        "feature_id": report["feature_id"],
        "input_sha256": report["input_sha256"],
        "reviewer": None,
        "reviewed_at": None,
        "requirements": [
            {
                "requirement_id": item["requirement_id"],
                "reviewed": False,
                "oracle": "",
                "source_refs": [],
            }
            for item in report["requirements"]
        ],
        "findings": [],
        "resolutions": [],
    }


def evaluate_requirements(
    feature: dict,
    *,
    phase: dict | None = None,
    review: dict | None = None,
    markers: list[dict] | None = None,
) -> dict:
    validate_artifact(feature, "feature_spec.schema.json")
    if not feature["feature_id"].strip() or not feature["title"].strip():
        raise ValueError("feature IDとタイトルは空白にできません")
    if phase is not None:
        validate_artifact(phase, "phase_contract.schema.json")
        if feature["feature_id"] != phase["feature_id"]:
            raise ValueError("phase_contractのfeature_idが一致しません")
    markers = markers or []
    fingerprint = _digest({"feature": feature, "phase": phase, "markers": markers})
    inventory, raw_count = _inventory(feature)
    sources = _sources(feature, phase)
    issues = _collect(feature, phase, markers, inventory)
    if not inventory:
        issues.append(
            _issue(
                "system:empty",
                "評価できるAC・業務ルールがありません",
                "critical",
                "missing_requirements",
                blocks_ready=True,
            )
        )
    if not any(
        item.get("excerpt", "").strip() or item.get("url", "").strip() for item in sources.values()
    ):
        issues.append(
            _issue("system:source", "引用可能な仕様根拠がありません", "high", "missing_source")
        )
    for issue in issues:
        _refs(issue["source_refs"], sources)
    if review is not None:
        _apply_review(review, fingerprint, feature["feature_id"], inventory, sources, issues)
    _unique(issues, "issue_id", "確認事項")
    raw_findings = len(issues)
    issues = _merge_issues(issues)
    if review is not None:
        _resolve(review, issues, sources)
    return _report(
        feature, phase, review, fingerprint, inventory, sources, issues, raw_count, raw_findings
    )


def _report(
    feature: dict,
    phase: dict | None,
    review: dict | None,
    fingerprint: str,
    inventory: list[dict],
    sources: dict,
    issues: list[dict],
    raw_count: int,
    raw_findings: int,
) -> dict:
    total = len(inventory)
    reviewed = sum(item["reviewed"] for item in inventory)
    opened = [item for item in issues if item["status"] == "open"]
    severity = {key: sum(item["severity"] == key for item in opened) for key in WEIGHTS}
    weight = sum(WEIGHTS[item["severity"]] for item in opened)
    blocked = any(item["blocks_ready"] or item["severity"] == "critical" for item in opened)
    caps = []
    for condition, maximum, reason in (
        (blocked, 39, "重大な未解決事項または着手を妨げる確認事項が残っています"),
        (severity["high"] > 0, 69, "highの未解決事項が残っています"),
        (bool(opened), 84, "要確認事項が残っています"),
        (reviewed < total, 84, "未レビューの要件があります"),
        (reviewed == 0, 69, "レビュー済み要件がありません"),
    ):
        if condition:
            caps.append({"reason": reason, "maximum": maximum})
    uncertainty_points = 70 * max(0, 1 - weight / (4 * total)) if total else None
    review_points = 30 * reviewed / total if total else None
    base = round(uncertainty_points + review_points, 1) if total else None
    score = min([base] + [item["maximum"] for item in caps]) if total else None
    band = (
        "unknown"
        if score is None
        else "high"
        if score >= 85
        else "medium"
        if score >= 60
        else "low"
    )
    status = (
        "insufficient_data"
        if not total
        else "blocked"
        if blocked
        else "needs_confirmation"
        if opened or reviewed < total
        else "reviewed"
    )
    actions = [
        {
            "priority": "critical" if item["blocks_ready"] else item["severity"],
            "target_id": item["issue_id"],
            "text": "確認・根拠の記録: " + item["text"],
            "owner": item["owner"],
            "due": item["due"],
        }
        for item in opened
    ] + [
        {
            "priority": "medium",
            "target_id": item["requirement_id"],
            "text": "根拠・oracle・曖昧さ・矛盾をレビュー: " + item["text"],
            "owner": None,
            "due": None,
        }
        for item in inventory
        if not item["reviewed"]
    ]
    actions.sort(key=lambda item: (-WEIGHTS[item["priority"]], item["target_id"]))
    report = {
        "schema_version": "1.0.0",
        "policy_version": POLICY,
        "feature_id": feature["feature_id"],
        "input_sha256": fingerprint,
        "score": score,
        "band": band,
        "status": status,
        "provisional": not total or reviewed < total,
        "counts": {
            "requirements": total,
            "raw_requirements": raw_count,
            "duplicate_requirements": raw_count - total,
            "reviewed_requirements": reviewed,
            "unreviewed_requirements": total - reviewed,
            "raw_findings": raw_findings,
            "unique_findings": len(issues),
            "open_confirmations": len(opened),
            "resolved_confirmations": len(issues) - len(opened),
            "by_severity": severity,
            "technical_risks": len(phase["technical_risks"]) if phase else 0,
        },
        "metrics": {
            "review_coverage_percent": round(100 * reviewed / total, 1) if total else None,
            "open_items_per_requirement": round(len(opened) / total, 3) if total else None,
            "uncertainty_weight": weight,
            "normalization_capacity": 4 * total,
            "uncertainty_points": round(uncertainty_points, 4) if total else None,
            "review_points": round(review_points, 4) if total else None,
            "base_score": base,
        },
        "score_caps": caps,
        "requirements": inventory,
        "issues": issues,
        "next_actions": actions,
        "source_refs": [sources[key] for key in sorted(sources)],
        "review": {
            "reviewer": review["reviewer"] if review else None,
            "reviewed_at": review["reviewed_at"] if review else None,
            "requirements": copy.deepcopy(review["requirements"]) if review else [],
        },
        "limitations": LIMITATIONS.copy(),
    }
    validate_artifact(report, "requirements_confidence.schema.json")
    return report


def render_markdown(report: dict) -> str:
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")

    counts, metrics = report["counts"], report["metrics"]
    display = {key: "未算出" if value is None else value for key, value in metrics.items()}
    score = "評価不能" if report["score"] is None else f"{report['score']}/100"
    lines = [
        "# 要件定義の信頼度評価",
        "",
        f"信頼度: **{score}** / {report['band']} / {report['status']}",
        f"暫定評価: {'はい' if report['provisional'] else 'いいえ'}",
        "",
        "| 指標 | 値 |",
        "|---|---:|",
        f"| 要件数（重複除外） | {counts['requirements']} |",
        f"| 要確認項目数 | {counts['open_confirmations']} |",
        f"| 解決済み | {counts['resolved_confirmations']} |",
        f"| 未レビュー要件 | {counts['unreviewed_requirements']} |",
        f"| レビュー済み率（%） | {display['review_coverage_percent']} |",
        f"| 要件1件あたりの要確認数 | {display['open_items_per_requirement']} |",
        "",
    ]
    lines += [f"- {key}: {value}件" for key, value in counts["by_severity"].items()]
    lines += [
        "",
        "## 点数の根拠",
        "",
        f"不確実性分: {display['uncertainty_points']} / 70、"
        f"レビュー分: {display['review_points']} / 30、基礎点: {display['base_score']}。",
        f"未解決の重み合計: {metrics['uncertainty_weight']}、"
        f"正規化の基準量（4×要件数）: {metrics['normalization_capacity']}。",
    ]
    lines += [f"- 上限{cap['maximum']}点: {cap['reason']}" for cap in report["score_caps"]]
    lines += [
        "",
        "## 次に確認すること",
        "",
        "| 優先度 | ID | アクション | 担当 | 期限 |",
        "|---|---|---|---|---|",
    ]
    for item in report["next_actions"]:
        lines.append(
            "| "
            + " | ".join(
                cell(item[key] or "未設定")
                for key in ("priority", "target_id", "text", "owner", "due")
            )
            + " |"
        )
    lines += ["", "## 評価の範囲", ""] + ["- " + item for item in report["limitations"]]
    lines += [
        "",
        f"Policy: `{report['policy_version']}`",
        f"入力SHA256: `{report['input_sha256']}`",
        "",
        "要件一覧・確認事項の出典・解決根拠はrequirements_confidence.jsonを参照。",
        "",
    ]
    return "\n".join(lines)
