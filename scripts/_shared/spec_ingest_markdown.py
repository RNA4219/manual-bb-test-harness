"""Markdown specification ingestion helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


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
    """Extract Markdown sections and their list/paragraph content."""
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    current_items: list[str] = []
    lines = content.split("\n")
    frontmatter_end = _find_frontmatter_end(lines)

    for line in lines[frontmatter_end:]:
        stripped = line.strip()
        section_match = re.match(r"^##+\s+(.+)$", stripped)
        if section_match:
            if current_section and current_items:
                sections[current_section] = current_items
            current_section = section_match.group(1).strip()
            current_items = []
            continue

        if stripped.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", stripped):
            item_text = re.sub(r"^\d+\.\s*", "", stripped.lstrip("- *").strip())
            if item_text:
                current_items.append(item_text)
            continue

        if stripped and current_section:
            current_items.append(stripped)

    if current_section and current_items:
        sections[current_section] = current_items
    return sections


def _find_frontmatter_end(lines: list[str]) -> int:
    in_frontmatter = False
    for index, line in enumerate(lines):
        if line.strip() != "---":
            continue
        if not in_frontmatter:
            in_frontmatter = True
        else:
            return index + 1
    return 0


def normalize_section_name(name: str) -> str:
    """Normalize source section names to feature_spec keys."""
    name_lower = name.lower().strip()
    exact_mappings = {
        "acceptance criteria": "acceptance_criteria",
        "ac": "acceptance_criteria",
        "business rules": "business_rules",
        "br": "business_rules",
        "requirements": "requirements",
        "actors": "actors",
        "summary": "summary",
        "devices": "devices",
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
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc

    frontmatter = parse_yaml_frontmatter(content)
    normalized_sections = {
        normalize_section_name(name): items
        for name, items in extract_markdown_sections(content).items()
    }
    feature_id = frontmatter.get("feature_id", frontmatter.get("id", ""))
    if not feature_id:
        feature_id = re.sub(r"[^A-Z0-9-]", "", path.stem.upper().replace("-", "-"))

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
    if "acceptance_criteria" in sections:
        result["acceptance_criteria"] = sections["acceptance_criteria"]
    else:
        result["acceptance_criteria"] = ["[NO ACCEPTANCE CRITERIA FOUND]"]
        result.setdefault("assumptions", []).append(
            {
                "id": "ASM-1",
                "text": "No acceptance criteria section found in source",
                "severity": "high",
            }
        )

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
