"""RanDとの取り込み境界。参照URIや過去の原文ファイルは開かない。"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from bb_harness.schema_validation import validate_artifact

MAX_INPUT_BYTES = 16 * 1024 * 1024
PRIMARY_TYPES = {
    "requirements_packet",
    "requirements_audit_packet",
    "requirements_document",
    "downstream_handoff",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def nonblank(value: Any, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{label}: 空でない文字列が必要")
    return value


def strings(value: Any, label: str) -> list[str]:
    require(isinstance(value, list), f"{label}: 文字列配列が必要")
    for entry in value:
        nonblank(entry, label)
    return value


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def content_hash(row: dict) -> str:
    content = {
        "statement": normalize(row["statement"]),
        "acceptance_criteria": sorted({normalize(c) for c in row["acceptance_criteria"]}),
    }
    return digest(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _pairs(pairs: list[tuple]) -> dict:
    result: dict = {}
    for key, value in pairs:
        require(key not in result, f"重複JSONキー: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError(f"非有限JSON数値: {value}")


def load_input(path: Path, role: str) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    require(len(raw) <= MAX_INPUT_BYTES, f"{role}: 入力上限16 MiBを超過")
    payload = json.loads(
        raw.decode("utf-8-sig"), object_pairs_hook=_pairs, parse_constant=_constant
    )
    require(isinstance(payload, dict), f"{role}: JSON objectが必要")
    # 指数オーバーフローもJSONの非有限数として拒否する。
    from bb_harness.schema_validation import validate_finite_numbers

    validate_finite_numbers(payload)
    return {
        "role": role,
        "path": str(path.resolve()),
        "uri": path.resolve().as_uri(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "payload": payload,
    }


def envelope(payload: dict, allowed: set[str]) -> None:
    require(payload.get("schema_version") == "2.0", "RanD schema_versionは2.0のみ対応")
    require(payload.get("type") in allowed, "未対応のRanD artifact type")
    require(
        nonblank(payload.get("id"), "artifact id").startswith("rand:"), "RanD artifact idが必要"
    )


def validate_source(source: dict) -> None:
    require(isinstance(source, dict), "source objectが必要")
    path_text = nonblank(source.get("path"), "source.path")
    path: PureWindowsPath | PurePosixPath = PureWindowsPath(path_text)
    if not path.is_absolute():
        path = PurePosixPath(path_text)
    require(path.is_absolute(), "source.pathは絶対pathが必要")
    start, end = source.get("line_start"), source.get("line_end")
    require(type(start) is int and type(end) is int and 1 <= start <= end, "sourceの行範囲が不正")
    excerpt = nonblank(source.get("excerpt"), "source.excerpt")
    require(source.get("uri") == f"{path.as_uri()}#L{start}-L{end}", "source URIと行範囲が不一致")
    require(
        excerpt.replace("\r\n", "\n").replace("\r", "\n").count("\n") + 1 == end - start + 1,
        "source excerptと行数が不一致",
    )


def validate_requirement(row: dict, document_id: str) -> None:
    key = document_id.removeprefix("rand:document:")
    nonblank(row.get("statement"), "statement")
    strings(row.get("acceptance_criteria"), "acceptance_criteria")
    validate_source(row["source"])
    require(row["content_hash"] == content_hash(row), "requirement content hashが不一致")
    external = row["external_id"]
    if row["identity_basis"] == "explicit":
        require(
            isinstance(external, str)
            and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)+", external)),
            "明示ID形式が不正",
        )
        local = external
    else:
        require(external is None, "本文由来IDのexternal_idはnullが必要")
        local = "auto-" + digest(normalize(row["statement"]))[:20]
    require(row["requirement_id"] == f"rand:req:{key}:{local}", "requirement IDが不一致")


def by_id(rows: list[dict]) -> dict[str, dict]:
    require(isinstance(rows, list), "requirementsは配列が必要")
    result = {}
    for row in rows:
        require(isinstance(row, dict), "requirement objectが必要")
        key = nonblank(row.get("requirement_id"), "requirement_id")
        require(key not in result, f"重複requirement_id: {key}")
        result[key] = row
    return result


def validate_document(document: dict) -> None:
    validate_artifact(document, "rand_requirements_document.schema.json")
    key = document["document_id"].removeprefix("rand:document:")
    source = document["source"]
    require(
        document["id"] == f"rand:document-snapshot:{key}:{source['sha256'][:20]}",
        "document IDとsource hashが不一致",
    )
    for row in by_id(document["requirements"]).values():
        validate_requirement(row, document["document_id"])
        require(row["source"]["path"] == source["path"], "要求と文書のsource pathが不一致")
        require(row["source"]["line_end"] <= source["line_count"], "文書行数を超えるsource")
        require(row["source"]["uri"].split("#")[0] == source["uri"], "文書のsource URIが不一致")


def primary_rows(payload: dict) -> tuple[list[dict], bool, str]:
    envelope(payload, PRIMARY_TYPES)
    kind = payload["type"]
    candidate = kind == "requirements_packet"
    identity = payload.get("document_id") or payload.get("packet_id") or payload["id"]
    if kind == "requirements_document":
        validate_document(payload)
    if kind == "downstream_handoff":
        section = payload.get("manual_bb_test_harness")
        require(isinstance(section, dict), "manual_bb_test_harness節が必要")
        source_type = section.get("artifact_type")
        require(
            source_type in {"manual_test_model_seed", "requirements_audit_testability"},
            "未対応のmanual-bb handoff型",
        )
        candidate = source_type == "manual_test_model_seed"
        rows = section.get("requirements")
        refs = payload.get("input_refs", [])
        require(isinstance(refs, list), "handoff.input_refsは配列が必要")
        if refs:
            identity = nonblank(refs[0], "handoff.input_refs")
    else:
        rows = payload.get("requirements")
    indexed = by_id(rows)
    for row in indexed.values():
        nonblank(row.get("statement", row.get("original_text")), "要求のstatement/original_text")
        strings(row.get("acceptance_criteria", []), "acceptance_criteria")
        if "source" in row:
            validate_source(row["source"])
        if "source_refs" in row:
            strings(row["source_refs"], "source_refs")
    return [indexed[k] for k in sorted(indexed)], candidate, nonblank(identity, "文書系列ID")


def validate_diff(diff: dict, document: dict) -> dict[str, str]:
    envelope(diff, {"requirements_diff"})
    require(
        document["type"] == "requirements_document",
        "--diffにはrequirements_documentを--inputに指定する",
    )
    validate_artifact(diff, "rand_requirements_diff.schema.json")
    require(diff["document_id"] == document["document_id"], "diff文書系列が不一致")
    require(diff["current_ref"] == document["id"], "diff current_refが不一致")
    require(
        diff["current_source_sha256"] == document["source"]["sha256"],
        "diff current source hashが不一致",
    )
    key = document["document_id"].removeprefix("rand:document:")
    require(
        diff["baseline_ref"]
        == f"rand:document-snapshot:{key}:{diff['baseline_source_sha256'][:20]}",
        "diff baseline_refが不一致",
    )
    current = by_id(document["requirements"])
    added, removed = by_id(diff["added"]), by_id(diff["removed"])
    modified = by_id(diff["modified"])
    unchanged = strings(diff["unchanged"], "unchanged")
    groups = [list(added), list(removed), list(modified), unchanged]
    flattened = [key for group in groups for key in group]
    require(len(flattened) == len(set(flattened)), "diff分類集合のID重複")
    require(
        set(current) == set(added) | set(modified) | set(unchanged),
        "diffが現行要求の全件を分類していない",
    )
    require(
        diff["summary"]
        == dict(zip(["added", "removed", "modified", "unchanged"], map(len, groups), strict=True)),
        "diff summaryが不一致",
    )
    for row in list(added.values()) + list(removed.values()):
        validate_requirement(row, document["document_id"])
    for rid, row in added.items():
        require(row == current[rid], "addedと現行要求が不一致")
    for rid, entry in modified.items():
        before, after = entry["before"], entry["after"]
        for row in (before, after):
            validate_requirement(row, document["document_id"])
            require(row["requirement_id"] == rid, "modifiedの内外IDが不一致")
        require(after == current[rid], "modified.afterと現行要求が不一致")
        fields = []
        if normalize(before["statement"]) != normalize(after["statement"]):
            fields.append("statement")
        if {normalize(c) for c in before["acceptance_criteria"]} != {
            normalize(c) for c in after["acceptance_criteria"]
        }:
            fields.append("acceptance_criteria")
        require(
            bool(fields) and entry["changed_fields"] == fields, "modified.changed_fieldsが不一致"
        )
    candidates = by_id(diff["test_candidates"])
    require(
        set(candidates) == set(added) | set(modified) | set(removed), "diffテスト候補の対象が不一致"
    )
    for rid, candidate in candidates.items():
        retired = rid in removed
        row = removed[rid] if retired else current[rid]
        action = "review_retirement" if retired else "review_new_or_changed"
        require(
            candidate["action"] == action and candidate["status"] == "draft",
            "diffテスト候補のaction/statusが不一致",
        )
        require(
            candidate["acceptance_criteria"] == row["acceptance_criteria"]
            and candidate["source_refs"] == [row["source"]["uri"]],
            "diffテスト候補の原文参照/ACが不一致",
        )
    return {
        rid: name
        for name, group in zip(["added", "removed", "modified", "unchanged"], groups, strict=True)
        for rid in group
    }
