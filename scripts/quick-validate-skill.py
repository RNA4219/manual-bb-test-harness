#!/usr/bin/env python3
"""Minimal repository-local validator for Codex Skill folders."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


MAX_SKILL_NAME_LENGTH = 64


def parse_frontmatter(content: str) -> dict[str, str]:
    match = re.match(r"^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
    if not match:
        raise ValueError("Invalid or missing YAML frontmatter")

    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"Unsupported frontmatter line: {line}")
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def validate_skill(skill_path: Path) -> list[str]:
    errors: list[str] = []
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return ["SKILL.md not found"]

    content = skill_md.read_text(encoding="utf-8")
    try:
        frontmatter = parse_frontmatter(content)
    except ValueError as exc:
        return [str(exc)]

    allowed = {"name", "description"}
    unexpected = set(frontmatter) - allowed
    if unexpected:
        errors.append(f"Unexpected frontmatter keys: {', '.join(sorted(unexpected))}")

    name = frontmatter.get("name", "")
    if not name:
        errors.append("Missing frontmatter.name")
    elif not re.fullmatch(r"[a-z0-9-]+", name):
        errors.append(f"Invalid skill name: {name}")
    elif name.startswith("-") or name.endswith("-") or "--" in name:
        errors.append(f"Invalid hyphen placement in skill name: {name}")
    elif len(name) > MAX_SKILL_NAME_LENGTH:
        errors.append(f"Skill name is too long: {len(name)}")

    description = frontmatter.get("description", "")
    if not description:
        errors.append("Missing frontmatter.description")
    elif "<" in description or ">" in description:
        errors.append("Description cannot contain angle brackets")
    elif len(description) > 1024:
        errors.append(f"Description is too long: {len(description)}")

    required = [
        "agents/openai.yaml",
        "references/artifact-contract.md",
        "references/case-design-policy.md",
        "references/failure-modes.md",
        "references/forward-test.md",
        "references/output-templates.md",
        "references/risk-and-gate-policy.md",
    ]
    for relative in required:
        if not (skill_path / relative).exists():
            errors.append(f"Missing required file: {relative}")

    bad_markers = ["TO" + "DO", "[TO" + "DO", "\ufffd"]
    for path in skill_path.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"File is not valid UTF-8: {path}")
            continue
        for marker in bad_markers:
            if marker in text:
                errors.append(f"Marker found in {path}: {marker}")

    return errors


def validate_json_files(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for path in list((repo_root / "schemas").glob("*.schema.json")) + list((repo_root / "examples").rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - report any parse issue
            errors.append(f"Invalid JSON: {path}: {exc}")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: quick-validate-skill.py <skill-directory>", file=sys.stderr)
        return 2

    skill_path = Path(sys.argv[1]).resolve()
    repo_root = skill_path.parents[1]
    errors = validate_skill(skill_path) + validate_json_files(repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Skill repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
