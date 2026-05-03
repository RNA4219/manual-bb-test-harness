"""Unit tests for quick-validate-skill.py - consolidated."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Load module dynamically from scripts directory
spec = importlib.util.spec_from_file_location(
    "quick_validate_skill",
    Path(__file__).parent.parent / "scripts" / "quick-validate-skill.py"
)
quick_validate_skill = importlib.util.module_from_spec(spec)
sys.modules["quick_validate_skill"] = quick_validate_skill
spec.loader.exec_module(quick_validate_skill)

MAX_SKILL_NAME_LENGTH = quick_validate_skill.MAX_SKILL_NAME_LENGTH
parse_frontmatter = quick_validate_skill.parse_frontmatter
find_repo_root = quick_validate_skill.find_repo_root
validate_json_files = quick_validate_skill.validate_json_files
validate_skill = quick_validate_skill.validate_skill
main = quick_validate_skill.main


# ============== Frontmatter Tests ==============

class TestParseFrontmatter:
    """Tests for frontmatter parsing."""

    def test_valid(self) -> None:
        content = "---\nname: test-skill\ndescription: Test\n---\nBody"
        result = parse_frontmatter(content)
        assert result["name"] == "test-skill"

    def test_valid_crlf(self) -> None:
        content = "---\r\nname: test-skill\r\ndescription: Test\r\n---\r\nBody"
        assert parse_frontmatter(content)["name"] == "test-skill"

    def test_missing(self) -> None:
        with pytest.raises(ValueError, match="Invalid or missing"):
            parse_frontmatter("No frontmatter")

    def test_malformed(self) -> None:
        with pytest.raises(ValueError, match="Invalid or missing"):
            parse_frontmatter("---\nname: test\nNo closing")

    def test_no_colon(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            parse_frontmatter("---\nname: test-skill\ninvalidline\n---")

    def test_empty_value(self) -> None:
        result = parse_frontmatter("---\nname: test-skill\nemptykey:\n---")
        assert result["emptykey"] == ""

    def test_multiple_colons(self) -> None:
        result = parse_frontmatter("---\nkey: value:with:colons\n---")
        assert result["key"] == "value:with:colons"


# ============== FindRepoRoot Tests ==============

class TestFindRepoRoot:
    """Tests for find_repo_root."""

    def test_finds_root(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("x", encoding="utf-8")
        (repo / "schemas").mkdir()
        skill = repo / "skills" / "test"
        skill.mkdir(parents=True)
        assert find_repo_root(skill) == repo

    def test_no_root_raises(self, tmp_path: Path) -> None:
        skill = tmp_path / "skills" / "test"
        skill.mkdir(parents=True)
        with pytest.raises(ValueError, match="Cannot determine"):
            find_repo_root(skill)


# ============== ValidateSkill Tests ==============

class TestValidateSkill:
    """Tests for skill validation."""

    def test_missing_skill_md(self, tmp_path: Path) -> None:
        errors = validate_skill(tmp_path)
        assert any("SKILL.md not found" in e for e in errors)

    def test_valid_structure(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\nname: test-skill\ndescription: Test\n---\n", encoding="utf-8")
        errors = validate_skill(tmp_path)
        assert not any("SKILL.md not found" in e for e in errors)

    def test_invalid_name_uppercase(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\nname: Test-Skill\ndescription: Test\n---\n", encoding="utf-8")
        assert any("Invalid skill name" in e for e in validate_skill(tmp_path))

    def test_invalid_name_too_long(self, tmp_path: Path) -> None:
        long_name = "a" * (MAX_SKILL_NAME_LENGTH + 1)
        (tmp_path / "SKILL.md").write_text(f"---\nname: {long_name}\ndescription: Test\n---\n", encoding="utf-8")
        assert any("too long" in e for e in validate_skill(tmp_path))

    def test_missing_name(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\ndescription: Test\n---\n", encoding="utf-8")
        assert any("Missing frontmatter.name" in e for e in validate_skill(tmp_path))

    def test_missing_description(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\nname: test-skill\n---\n", encoding="utf-8")
        assert any("Missing frontmatter.description" in e for e in validate_skill(tmp_path))

    def test_description_angle_brackets(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\nname: test-skill\ndescription: <placeholder>\n---\n", encoding="utf-8")
        assert any("angle brackets" in e for e in validate_skill(tmp_path))

    def test_description_too_long(self, tmp_path: Path) -> None:
        long_desc = "x" * 1025
        (tmp_path / "SKILL.md").write_text(f"---\nname: test-skill\ndescription: {long_desc}\n---\n", encoding="utf-8")
        assert any("too long" in e and "Description" in e for e in validate_skill(tmp_path))

    def test_todo_marker(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\nname: test-skill\ndescription: Test\n---\nTODO: fix\n", encoding="utf-8")
        assert any("placeholder" in e.lower() or "TODO" in e for e in validate_skill(tmp_path))

    def test_unexpected_keys(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\nname: test-skill\ndescription: Test\nextra: value\n---\n", encoding="utf-8")
        assert any("Unexpected frontmatter keys" in e for e in validate_skill(tmp_path))

    def test_binary_file(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\nname: test-skill\ndescription: Test\n---\n", encoding="utf-8")
        (tmp_path / "image.png").write_bytes(b'\x89PNG')
        assert any("UTF-8" in e for e in validate_skill(tmp_path))

    def test_missing_required_file(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\nname: test-skill\ndescription: Test\n---\n", encoding="utf-8")
        assert any("Missing required file" in e for e in validate_skill(tmp_path))


# ============== ValidateJson Tests ==============

class TestValidateJsonFiles:
    """Tests for JSON validation."""

    def test_valid_json(self, tmp_path: Path) -> None:
        (tmp_path / "schemas").mkdir()
        (tmp_path / "schemas" / "test.schema.json").write_text('{}', encoding="utf-8")
        errors = validate_json_files(tmp_path)
        assert not any("Invalid JSON" in e for e in errors)

    def test_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "schemas").mkdir()
        bad_file = tmp_path / "schemas" / "bad.schema.json"
        bad_file.write_text('{invalid}', encoding="utf-8")
        assert any("Invalid JSON" in e and str(bad_file) in e for e in validate_json_files(tmp_path))

    def test_non_utf8(self, tmp_path: Path) -> None:
        (tmp_path / "schemas").mkdir()
        (tmp_path / "schemas" / "bad.schema.json").write_bytes(b'\xff\xfe {}')
        assert any("UTF-8" in e or "Invalid JSON" in e for e in validate_json_files(tmp_path))


# ============== Main Tests ==============

class TestMain:
    """Tests for main() entry point."""

    def test_version(self) -> None:
        with mock.patch.object(sys, "argv", ["script", "--version"]):
            with mock.patch("builtins.print"):
                assert main() == 0

    def test_debug(self, tmp_path: Path) -> None:
        # Setup valid skill
        (tmp_path / "README.md").write_text("x", encoding="utf-8")
        (tmp_path / "schemas").mkdir()
        skill = tmp_path / "skills" / "test-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: test-skill\ndescription: test\n---\n", encoding="utf-8")
        (skill / "agents").mkdir()
        (skill / "agents" / "openai.yaml").write_text("", encoding="utf-8")
        (skill / "references").mkdir()
        for ref in ["artifact-contract.md", "case-design-policy.md", "failure-modes.md",
                    "forward-test.md", "output-templates.md", "risk-and-gate-policy.md"]:
            (skill / "references" / ref).write_text("", encoding="utf-8")

        with mock.patch.object(sys, "argv", ["script", "--debug", str(skill)]):
            assert main() == 0

    def test_missing_skill_dir(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("x", encoding="utf-8")
        (tmp_path / "schemas").mkdir()
        nonexistent = tmp_path / "skills" / "nonexistent"

        with mock.patch.object(sys, "argv", ["script", str(nonexistent)]):
            assert main() == 1

    def test_no_repo_root(self, tmp_path: Path) -> None:
        skill = tmp_path / "skills" / "test"
        skill.mkdir(parents=True)

        with mock.patch.object(sys, "argv", ["script", str(skill)]):
            assert main() == 1

    def test_validation_errors(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("x", encoding="utf-8")
        (tmp_path / "schemas").mkdir()
        skill = tmp_path / "skills" / "test"
        skill.mkdir(parents=True)

        with mock.patch.object(sys, "argv", ["script", str(skill)]):
            assert main() == 1


# ============== Subprocess Tests (version flag) ==============

class TestVersionSubprocess:
    """Test --version via subprocess."""

    def test_version_output(self) -> None:
        script = Path(__file__).parent.parent / "scripts" / "quick-validate-skill.py"
        result = subprocess.run(["py", str(script), "--version"], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
        assert "0.1.1" in result.stdout