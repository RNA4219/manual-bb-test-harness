"""Unit tests for spec-ingest.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Load module dynamically
spec = importlib.util.spec_from_file_location(
    "spec_ingest",
    Path(__file__).parent.parent / "scripts" / "spec-ingest.py"
)
spec_ingest = importlib.util.module_from_spec(spec)
sys.modules["spec_ingest"] = spec_ingest
spec.loader.exec_module(spec_ingest)

parse_yaml_frontmatter = spec_ingest.parse_yaml_frontmatter
extract_markdown_sections = spec_ingest.extract_markdown_sections
normalize_section_name = spec_ingest.normalize_section_name
ingest_markdown_spec = spec_ingest.ingest_markdown_spec
main = spec_ingest.main


class TestParseYamlFrontmatter:
    """Tests for frontmatter parsing."""

    def test_valid_frontmatter(self) -> None:
        content = "---\nfeature_id: TEST-01\ntitle: Test\n---\nBody"
        result = parse_yaml_frontmatter(content)
        assert result["feature_id"] == "TEST-01"
        assert result["title"] == "Test"

    def test_missing_frontmatter(self) -> None:
        content = "No frontmatter here"
        result = parse_yaml_frontmatter(content)
        assert result == {}  # Returns empty dict when no frontmatter

    def test_malformed_line(self) -> None:
        content = "---\nfeature_id: TEST\ninvalidline\n---\nBody"
        result = parse_yaml_frontmatter(content)
        # Malformed lines are skipped, returns valid entries only
        assert result.get("feature_id") == "TEST"

    def test_multiple_values(self) -> None:
        content = "---\nkey: value:with:colons\n---\nBody"
        result = parse_yaml_frontmatter(content)
        assert result["key"] == "value:with:colons"

    def test_empty_value(self) -> None:
        content = "---\nkey:\n---\nBody"
        result = parse_yaml_frontmatter(content)
        assert result["key"] == ""


class TestExtractMarkdownSections:
    """Tests for section extraction."""

    def test_basic_sections(self) -> None:
        content = "---\n---\n## AC\n- Item 1\n- Item 2\n## BR\n- Rule 1"
        sections = extract_markdown_sections(content)
        assert "AC" in sections
        assert "Item 1" in sections["AC"]

    def test_numbered_list(self) -> None:
        content = "---\n---\n## AC\n1. Item one\n2. Item two"
        sections = extract_markdown_sections(content)
        assert "Item one" in sections["AC"]
        assert "Item two" in sections["AC"]

    def test_paragraph_text(self) -> None:
        content = "---\n---\n## Summary\nThis is a paragraph.\n## AC\n- Item"
        sections = extract_markdown_sections(content)
        assert "This is a paragraph." in sections["Summary"]

    def test_no_sections(self) -> None:
        content = "---\n---\nJust plain text"
        sections = extract_markdown_sections(content)
        assert sections == {}


class TestNormalizeSectionName:
    """Tests for section name normalization."""

    def test_acceptance_criteria(self) -> None:
        assert normalize_section_name("Acceptance Criteria") == "acceptance_criteria"
        assert normalize_section_name("acceptance criteria") == "acceptance_criteria"

    def test_ac_abbrev(self) -> None:
        assert normalize_section_name("AC") == "acceptance_criteria"

    def test_actors_not_confused(self) -> None:
        # Critical test: "actors" should NOT match "ac"
        assert normalize_section_name("Actors") == "actors"
        assert normalize_section_name("actors") == "actors"

    def test_business_rules(self) -> None:
        assert normalize_section_name("Business Rules") == "business_rules"
        assert normalize_section_name("BR") == "business_rules"

    def test_unknown_section(self) -> None:
        assert normalize_section_name("Custom Section") == "custom_section"


class TestIngestMarkdownSpec:
    """Tests for full Markdown ingestion."""

    def test_full_markdown(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "---\nfeature_id: TEST-01\ntitle: Test Feature\n---\n"
            "## Acceptance Criteria\n- AC-1: First criterion\n- AC-2: Second criterion\n"
            "## Business Rules\n- BR-1: First rule\n",
            encoding="utf-8"
        )
        result = ingest_markdown_spec(md_file)

        assert result["feature_id"] == "TEST-01"
        assert result["title"] == "Test Feature"
        assert "AC-1: First criterion" in result["acceptance_criteria"]
        assert "BR-1: First rule" in result["business_rules"]
        assert result["source_refs"][0]["kind"] == "spec"

    def test_missing_ac_adds_assumption(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "---\nfeature_id: TEST-02\ntitle: Test\n---\n"
            "## Summary\nSome summary\n",
            encoding="utf-8"
        )
        result = ingest_markdown_spec(md_file)

        assert "[NO ACCEPTANCE CRITERIA FOUND]" in result["acceptance_criteria"]
        assert any("No acceptance criteria" in a["text"] for a in result.get("assumptions", []))

    def test_generates_feature_id_from_filename(self, tmp_path: Path) -> None:
        md_file = tmp_path / "order-cancel.md"
        md_file.write_text(
            "---\ntitle: Test\n---\n"
            "## Acceptance Criteria\n- AC-1: Item\n",
            encoding="utf-8"
        )
        result = ingest_markdown_spec(md_file)
        assert "ORDER" in result["feature_id"] or "CANCEL" in result["feature_id"]

    def test_actors_from_frontmatter(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "---\nfeature_id: TEST\nactors: user, admin, system\n---\n"
            "## Acceptance Criteria\n- AC-1: Item\n",
            encoding="utf-8"
        )
        result = ingest_markdown_spec(md_file)
        assert "user" in result["actors"]
        assert "admin" in result["actors"]


class TestMain:
    """Tests for main() entry point."""

    def test_version(self) -> None:
        with mock.patch.object(sys, "argv", ["script", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_markdown_ingestion(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "---\nfeature_id: TEST-01\ntitle: Test\n---\n"
            "## Acceptance Criteria\n- AC-1: Item\n",
            encoding="utf-8"
        )
        output_file = tmp_path / "output.json"

        with mock.patch.object(sys, "argv", [
            "script",
            "--source", "markdown",
            "--input", str(md_file),
            "--output", str(output_file),
        ]):
            assert main() == 0
            assert output_file.exists()
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert data["feature_id"] == "TEST-01"

    def test_missing_input_for_markdown(self) -> None:
        with mock.patch.object(sys, "argv", [
            "script", "--source", "markdown", "--output", "out.json"
        ]):
            assert main() == 1

    def test_confluence_stub(self, tmp_path: Path) -> None:
        output_file = tmp_path / "output.json"
        with mock.patch.object(sys, "argv", [
            "script",
            "--source", "confluence",
            "--url", "https://example.com/wiki/page",
            "--output", str(output_file),
        ]):
            assert main() == 0
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert "CONFLUENCE" in data["feature_id"]

    def test_jira_stub(self, tmp_path: Path) -> None:
        output_file = tmp_path / "output.json"
        with mock.patch.object(sys, "argv", [
            "script",
            "--source", "jira",
            "--issue", "PROJ-123",
            "--output", str(output_file),
        ]):
            assert main() == 0
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert data["feature_id"] == "PROJ-123"