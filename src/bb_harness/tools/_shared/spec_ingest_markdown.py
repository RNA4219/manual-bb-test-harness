"""Markdown specification ingestion helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def read_markdown(path: Path) -> str:
    """先頭のUTF-8 BOMだけを除去し、本文の文字と行位置を保持する。"""
    return path.read_text(encoding="utf-8-sig")


def fallback_feature_id(stem: str) -> str:
    """既存の要件評価と互換の、場所・時刻に依存しない代替ID。"""
    content = json.dumps(stem, ensure_ascii=False).encode("utf-8")
    return "MD-" + hashlib.sha256(content).hexdigest()[:12]


def parse_yaml_frontmatter(content: str) -> dict[str, str]:
    """Parse simple YAML frontmatter from Markdown content."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}

    result: dict[str, str] = {}
    for line in match.group(1).split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def extract_markdown_sections(content: str) -> dict[str, list[str]]:
    """見出しの親子関係を保ち、同じ種別の項目を出現順に集める。"""
    sections: dict[str, list[str]] = {}
    section_titles: dict[str, str] = {}
    heading_stack: list[tuple[int, str]] = []
    current_section: str | None = None
    known_sections = {
        "acceptance_criteria", "business_rules", "requirements", "actors", "summary",
        "devices", "mobile_contexts", "changed_areas",
    }
    lines = content.split("\n")
    frontmatter_end = _find_frontmatter_end(lines)

    for line in lines[frontmatter_end:]:
        stripped = line.strip()
        section_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if section_match:
            level = len(section_match.group(1))
            name = section_match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            if normalize_section_name(name) not in known_sections and heading_stack:
                name = heading_stack[-1][1]
            heading_stack.append((level, name))
            normalized_name = normalize_section_name(name)
            current_section = section_titles.setdefault(normalized_name, name)
            continue

        if not current_section or re.fullmatch(
            r"(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,}", stripped
        ):
            continue

        if stripped.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", stripped):
            item_text = re.sub(r"^\d+\.\s*", "", stripped.lstrip("- *").strip())
            if item_text:
                sections.setdefault(current_section, []).append(item_text)
            continue

        if stripped:
            sections.setdefault(current_section, []).append(stripped)

    return sections


def _find_frontmatter_end(lines: list[str]) -> int:
    # 本文の水平線を frontmatter の区切りとして扱わない。
    if not lines or lines[0].strip() != "---":
        return 0
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index + 1
    return 0


def normalize_section_name(name: str) -> str:
    """Normalize source section names to feature_spec keys."""
    name_lower = name.lower().strip()
    exact_mappings = {
        "acceptance criteria": "acceptance_criteria",
        "受入条件": "acceptance_criteria",
        "受け入れ条件": "acceptance_criteria",
        "受入基準": "acceptance_criteria",
        "受け入れ基準": "acceptance_criteria",
        "要件": "acceptance_criteria",
        "機能要件": "acceptance_criteria",
        "ac": "acceptance_criteria",
        "business rules": "business_rules",
        "業務ルール": "business_rules",
        "br": "business_rules",
        "requirements": "requirements",
        "actors": "actors",
        "summary": "summary",
        "devices": "devices",
        "environments": "devices",
        "mobile contexts": "mobile_contexts",
        "changed areas": "changed_areas",
    }

    if name_lower in exact_mappings:
        return exact_mappings[name_lower]

    for key, value in exact_mappings.items():
        if key in name_lower and len(key) >= 3:
            return value
    return name_lower.replace(" ", "_")


def ingest_markdown_spec(path: Path) -> dict[str, Any]:
    """Ingest a feature specification from a Markdown file."""
    try:
        content = read_markdown(path)
    except OSError as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc

    frontmatter = parse_yaml_frontmatter(content)
    normalized_sections: dict[str, list[str]] = {}
    for name, items in extract_markdown_sections(content).items():
        normalized_sections.setdefault(normalize_section_name(name), []).extend(items)
    feature_id = frontmatter.get("feature_id", frontmatter.get("id", ""))
    if not feature_id:
        feature_id = re.sub(r"[^A-Z0-9-]", "", path.stem.upper().replace("-", "-"))
    if not feature_id:
        feature_id = fallback_feature_id(path.stem)

    result: dict[str, Any] = {
        "feature_id": feature_id,
        "title": frontmatter.get("title", frontmatter.get("name", path.stem)),
        "source_refs": [
            {"id": f"MD-{path.stem}", "kind": "spec", "excerpt": f"Ingested from {path.name}"}
        ],
    }

    if "summary" in frontmatter:
        result["summary"] = frontmatter["summary"]
    if "actors" in frontmatter:
        result["actors"] = [actor.strip() for actor in frontmatter["actors"].split(",")]

    _merge_markdown_sections(result, normalized_sections)
    return result


def _merge_markdown_sections(result: dict[str, Any], sections: dict[str, list[str]]) -> None:
    if not sections.get("acceptance_criteria"):
        raise ValueError("No acceptance criteria found in Markdown source")
    result["acceptance_criteria"] = sections["acceptance_criteria"]

    optional_fields = [
        "business_rules",
        "devices",
        "mobile_contexts",
        "changed_areas",
    ]
    for field in optional_fields:
        if field in sections:
            result[field] = sections[field]

    if "actors" in sections and "actors" not in result:
        result["actors"] = sections["actors"]
    if "summary" in sections and "summary" not in result:
        result["summary"] = sections["summary"][0] if sections["summary"] else ""
