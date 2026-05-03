#!/usr/bin/env python3
"""Minimal repository-local validator for Codex Skill folders.

Usage:
    python quick-validate-skill.py <skill-directory>
    python quick-validate-skill.py --version
    python quick-validate-skill.py --debug <skill-directory>
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

__version__: str = "0.1.1"

MAX_SKILL_NAME_LENGTH: int = 64

logger: logging.Logger = logging.getLogger(__name__)


# Obfuscated placeholder detection pattern:
# "TO" + "DO" avoids triggering TODO detection tools that scan source code.
# U+FFFD is the Unicode replacement character, indicating mojibake
# or corrupted encoding that should not be released in production artifacts.
BAD_MARKERS: list[str] = [
    "TO" + "DO",       # Placeholder text (obfuscated to avoid self-detection)
    "[TO" + "DO",      # TODO checkbox marker
    "�",          # Unicode replacement character (mojibake)
]


def parse_frontmatter(content: str) -> dict[str, str]:
    """Parse YAML frontmatter from skill markdown content.

    Args:
        content: Full content of SKILL.md file

    Returns:
        Dictionary of frontmatter key-value pairs

    Raises:
        ValueError: If frontmatter is missing or malformed
    """
    match: re.Match[str] | None = re.match(r"^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
    if not match:
        raise ValueError("Invalid or missing YAML frontmatter. SKILL.md must start with '---' block.")

    data: dict[str, str] = {}
    frontmatter_text: str = match.group(1)
    line: str
    for line in frontmatter_text.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"Unsupported frontmatter line (no colon): {line}")
        key: str
        value: str
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def find_repo_root(skill_path: Path) -> Path:
    """Find repository root by looking for README.md and schemas/ directory.

    This replaces the hardcoded parents[1] assumption with dynamic detection.

    Args:
        skill_path: Path to the skill directory

    Returns:
        Repository root path

    Raises:
        ValueError: If repository root cannot be determined
    """
    parent: Path
    for parent in skill_path.parents:
        if (parent / "README.md").exists() and (parent / "schemas").is_dir():
            logger.debug(f"Found repo root at {parent}")
            return parent
    raise ValueError(
        f"Cannot determine repository root from {skill_path}. "
        "Expected README.md and schemas/ directory in parent chain."
    )


def validate_skill(skill_path: Path) -> list[str]:
    """Validate skill directory structure and content.

    Args:
        skill_path: Path to the skill directory to validate

    Returns:
        List of error messages, empty if validation passes
    """
    errors: list[str] = []
    skill_md: Path = skill_path / "SKILL.md"

    if not skill_md.exists():
        return [f"SKILL.md not found at {skill_md}. Skill directory must contain SKILL.md."]

    logger.debug(f"Reading {skill_md}")
    content: str = skill_md.read_text(encoding="utf-8")
    frontmatter: dict[str, str]
    try:
        frontmatter = parse_frontmatter(content)
    except ValueError as exc:
        return [f"SKILL.md frontmatter error: {exc}"]

    # Check for unexpected frontmatter keys
    allowed: set[str] = {"name", "description"}
    unexpected: set[str] = set(frontmatter) - allowed
    if unexpected:
        errors.append(
            f"Unexpected frontmatter keys: {', '.join(sorted(unexpected))}. "
            f"Allowed keys are: {', '.join(sorted(allowed))}."
        )

    # Validate skill name
    name: str = frontmatter.get("name", "")
    if not name:
        errors.append("Missing frontmatter.name. Skill must have a name in frontmatter.")
    elif not re.fullmatch(r"[a-z0-9-]+", name):
        errors.append(
            f"Invalid skill name '{name}'. "
            "Name must contain only lowercase letters, digits, and hyphens."
        )
    elif name.startswith("-") or name.endswith("-") or "--" in name:
        errors.append(
            f"Invalid hyphen placement in skill name '{name}'. "
            "Name cannot start/end with hyphen or contain consecutive hyphens."
        )
    elif len(name) > MAX_SKILL_NAME_LENGTH:
        errors.append(
            f"Skill name '{name}' is too long ({len(name)} chars). "
            f"Maximum allowed: {MAX_SKILL_NAME_LENGTH}."
        )

    # Validate description
    description: str = frontmatter.get("description", "")
    if not description:
        errors.append("Missing frontmatter.description. Skill must have a description in frontmatter.")
    elif "<" in description or ">" in description:
        errors.append(
            "Description contains angle brackets '<' or '>' which are not allowed. "
            "Remove placeholder markers like <value>."
        )
    elif len(description) > 1024:
        errors.append(
            f"Description is too long ({len(description)} chars). Maximum allowed: 1024."
        )

    # Check required files
    required: list[str] = [
        "agents/openai.yaml",
        "references/artifact-contract.md",
        "references/case-design-policy.md",
        "references/failure-modes.md",
        "references/forward-test.md",
        "references/output-templates.md",
        "references/risk-and-gate-policy.md",
    ]
    relative: str
    file_path: Path
    for relative in required:
        file_path = skill_path / relative
        if not file_path.exists():
            errors.append(
                f"Missing required file: {relative}. "
                f"Expected at {file_path}."
            )

    # Check for placeholder markers in all files
    path: Path
    text: str
    marker: str
    for path in skill_path.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"File is not valid UTF-8: {path}. All skill files must be UTF-8 encoded.")
            continue
        for marker in BAD_MARKERS:
            if marker in text:
                errors.append(
                    f"Placeholder marker '{marker}' found in {path}. "
                    "Remove all TODO markers and fix encoding issues before release."
                )

    return errors


def validate_json_files(repo_root: Path) -> list[str]:
    """Validate all JSON schema and example files in repository.

    Args:
        repo_root: Repository root path

    Returns:
        List of error messages, empty if all JSON files are valid
    """
    errors: list[str] = []
    json_files: list[Path] = list((repo_root / "schemas").glob("*.schema.json")) + \
                             list((repo_root / "examples").rglob("*.json"))

    path: Path
    content: str
    for path in json_files:
        logger.debug(f"Validating JSON file: {path}")
        try:
            content = path.read_text(encoding="utf-8")
            json.loads(content)
        except json.JSONDecodeError as exc:
            errors.append(
                f"Invalid JSON syntax in {path}: {exc.msg} at line {exc.lineno}, column {exc.colno}."
            )
        except UnicodeDecodeError as exc:
            errors.append(
                f"File {path} is not valid UTF-8: {exc.reason}. "
                "All JSON files must be UTF-8 encoded."
            )
        except OSError as exc:
            errors.append(f"Cannot read file {path}: {exc}")

    return errors


def main() -> int:
    """Main entry point for validation script.

    Returns:
        Exit code: 0 for success, 1 for validation errors, 2 for usage errors
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Validate Codex Skill repository structure and content.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python quick-validate-skill.py skills/my-skill
    python quick-validate-skill.py --debug skills/my-skill
    python quick-validate-skill.py --version
        """
    )
    parser.add_argument(
        "skill_directory",
        nargs="?",
        help="Path to the skill directory to validate"
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging"
    )

    args: argparse.Namespace = parser.parse_args()

    # Handle --version
    if args.version:
        print(f"quick-validate-skill.py version {__version__}")
        return 0

    # Setup logging
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(levelname)s: %(message)s"
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(levelname)s: %(message)s"
        )

    # Check for required argument
    if not args.skill_directory:
        parser.error("skill_directory is required (unless --version is specified)")
        return 2

    skill_path: Path = Path(args.skill_directory).resolve()
    logger.info(f"Validating skill at {skill_path}")

    repo_root: Path
    try:
        repo_root = find_repo_root(skill_path)
    except ValueError as exc:
        logger.error(str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = validate_skill(skill_path) + validate_json_files(repo_root)

    if errors:
        error: str
        for error in errors:
            logger.error(error)
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"\nValidation failed with {len(errors)} errors.", file=sys.stderr)
        return 1

    logger.info("Validation passed")
    print("Skill repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())