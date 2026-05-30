"""Unit tests for spec-ingest.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# Load module dynamically
spec = importlib.util.spec_from_file_location(
    "spec_ingest", Path(__file__).parent.parent / "scripts" / "spec-ingest.py"
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

    def test_mobile_contexts(self) -> None:
        assert normalize_section_name("Mobile Contexts") == "mobile_contexts"

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
            encoding="utf-8",
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
            "---\nfeature_id: TEST-02\ntitle: Test\n---\n## Summary\nSome summary\n",
            encoding="utf-8",
        )
        result = ingest_markdown_spec(md_file)

        assert "[NO ACCEPTANCE CRITERIA FOUND]" in result["acceptance_criteria"]
        assert any("No acceptance criteria" in a["text"] for a in result.get("assumptions", []))

    def test_generates_feature_id_from_filename(self, tmp_path: Path) -> None:
        md_file = tmp_path / "order-cancel.md"
        md_file.write_text(
            "---\ntitle: Test\n---\n## Acceptance Criteria\n- AC-1: Item\n", encoding="utf-8"
        )
        result = ingest_markdown_spec(md_file)
        assert "ORDER" in result["feature_id"] or "CANCEL" in result["feature_id"]

    def test_actors_from_frontmatter(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "---\nfeature_id: TEST\nactors: user, admin, system\n---\n"
            "## Acceptance Criteria\n- AC-1: Item\n",
            encoding="utf-8",
        )
        result = ingest_markdown_spec(md_file)
        assert "user" in result["actors"]
        assert "admin" in result["actors"]

    def test_mobile_contexts_from_section(self, tmp_path: Path) -> None:
        md_file = tmp_path / "mobile.md"
        md_file.write_text(
            "---\nfeature_id: MOB-01\ntitle: Mobile Feature\n---\n"
            "## Acceptance Criteria\n- AC-1: Item\n"
            "## Devices\n- iOS\n- Android\n"
            "## Mobile Contexts\n- foreground\n- background_resume\n",
            encoding="utf-8",
        )
        result = ingest_markdown_spec(md_file)
        assert result["devices"] == ["iOS", "Android"]
        assert result["mobile_contexts"] == ["foreground", "background_resume"]


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
            "---\nfeature_id: TEST-01\ntitle: Test\n---\n## Acceptance Criteria\n- AC-1: Item\n",
            encoding="utf-8",
        )
        output_file = tmp_path / "output.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "script",
                "--source",
                "markdown",
                "--input",
                str(md_file),
                "--output",
                str(output_file),
            ],
        ):
            assert main() == 0
            assert output_file.exists()
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert data["feature_id"] == "TEST-01"

    def test_missing_input_for_markdown(self) -> None:
        with mock.patch.object(
            sys, "argv", ["script", "--source", "markdown", "--output", "out.json"]
        ):
            assert main() == 1

    def test_confluence_stub(self, tmp_path: Path) -> None:
        output_file = tmp_path / "output.json"
        with mock.patch.object(
            sys,
            "argv",
            [
                "script",
                "--source",
                "confluence",
                "--url",
                "https://example.com/wiki/page",
                "--output",
                str(output_file),
            ],
        ):
            assert main() == 0
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert "CONFLUENCE" in data["feature_id"]

    def test_jira_stub(self, tmp_path: Path) -> None:
        output_file = tmp_path / "output.json"
        with mock.patch.object(
            sys,
            "argv",
            [
                "script",
                "--source",
                "jira",
                "--issue",
                "PROJ-123",
                "--output",
                str(output_file),
            ],
        ):
            assert main() == 0
            data = json.loads(output_file.read_text(encoding="utf-8"))
            assert data["feature_id"] == "PROJ-123"


class TestSpecIngestMainDirect:
    """Tests for main function direct calls for coverage.

    # TRACE: scripts/spec-ingest.py:682-765 (role: main_direct)
    """

    def test_main_missing_output(self) -> None:
        """Missing output returns error (argparse SystemExit)."""
        with mock.patch.object(
            sys,
            "argv",
            ["script", "--source", "markdown", "--input", "test.md"],
        ):
            with pytest.raises(SystemExit):
                main()

    def test_main_missing_source(self, tmp_path: Path) -> None:
        """Missing source returns error (argparse SystemExit)."""
        output_file = tmp_path / "output.json"
        with mock.patch.object(
            sys,
            "argv",
            ["script", "--output", str(output_file)],
        ):
            with pytest.raises(SystemExit):
                main()

    def test_main_confluence_missing_url(self, tmp_path: Path) -> None:
        """Confluence without url returns error."""
        output_file = tmp_path / "output.json"
        with mock.patch.object(
            sys,
            "argv",
            ["script", "--source", "confluence", "--output", str(output_file)],
        ):
            assert main() == 1

    def test_main_jira_missing_issue(self, tmp_path: Path) -> None:
        """Jira without issue returns error."""
        output_file = tmp_path / "output.json"
        with mock.patch.object(
            sys,
            "argv",
            ["script", "--source", "jira", "--output", str(output_file)],
        ):
            assert main() == 1

    def test_main_unknown_source(self, tmp_path: Path) -> None:
        """Unknown source type is rejected by argparse."""
        output_file = tmp_path / "output.json"
        with mock.patch.object(
            sys,
            "argv",
            ["script", "--source", "unknown", "--output", str(output_file)],
        ):
            # argparse will raise SystemExit for invalid choice
            with pytest.raises(SystemExit):
                main()


class TestConfluenceIngestMocked:
    """Tests for ingest_confluence_spec with mocked requests.

    # TRACE: scripts/spec-ingest.py:239-390 (role: confluence_ingest)
    """

    def test_ingest_confluence_functions_exist(self) -> None:
        """Confluence ingest functions exist."""
        module = spec_ingest

        assert hasattr(module, "ingest_confluence_spec")
        assert hasattr(module, "extract_confluence_page_id")
        assert hasattr(module, "parse_confluence_html")

    def test_extract_confluence_page_id_numeric(self) -> None:
        """Extract page ID from numeric input."""
        module = spec_ingest
        result = module.extract_confluence_page_id("12345", "")
        assert result == "12345"

    def test_extract_confluence_page_id_from_url(self) -> None:
        """Extract page ID from URL path."""
        module = spec_ingest
        result = module.extract_confluence_page_id(
            "https://test.atlassian.net/wiki/pages/12345", ""
        )
        assert result == "12345"

    def test_extract_confluence_page_id_from_query(self) -> None:
        """Extract page ID from query string."""
        module = spec_ingest
        result = module.extract_confluence_page_id(
            "https://test.atlassian.net/wiki?pageId=67890", ""
        )
        assert result == "67890"

    def test_parse_confluence_html(self) -> None:
        """Parse Confluence HTML to extract sections."""
        module = spec_ingest

        html = """
<h2>Acceptance Criteria</h2>
<ul><li>AC-1: First criterion</li><li>AC-2: Second criterion</ul>
<h2>Business Rules</h2>
<ul><li>BR-1: First rule</li></ul>
"""
        ac, br, actors, devices, mobile, changed = module.parse_confluence_html(html)
        assert len(ac) >= 1 or len(br) >= 1


class TestJiraIngestMocked:
    """Tests for ingest_jira_issue with mocked requests.

    # TRACE: scripts/spec-ingest.py:499-627 (role: jira_ingest)
    """

    def test_ingest_jira_functions_exist(self) -> None:
        """Jira ingest functions exist."""
        module = spec_ingest

        assert hasattr(module, "ingest_jira_issue")
        assert hasattr(module, "parse_jira_description")

    def test_parse_jira_description(self) -> None:
        """Parse Jira description to extract sections."""
        module = spec_ingest

        description = """
h2. Acceptance Criteria
* AC-1: First criterion
* AC-2: Second criterion

h2. Business Rules
* BR-1: Must validate input
"""
        ac, br, actors = module.parse_jira_description(description)
        assert len(ac) >= 1 or len(br) >= 1

    def test_parse_jira_description_empty(self) -> None:
        """Parse empty Jira description."""
        module = spec_ingest

        ac, br, actors = module.parse_jira_description("")
        assert len(ac) == 0
        assert len(br) == 0
        assert len(actors) == 0


class TestGenerateFeatureId:
    """Tests for generate_feature_id function.

    # TRACE: scripts/spec-ingest.py:483-493 (role: feature_id_generation)
    """

    def test_generate_feature_id_from_title(self) -> None:
        """Generate feature ID from title."""
        module = spec_ingest
        result = module.generate_feature_id("Order Cancel Feature", "12345")
        # Function extracts words and combines them
        assert len(result) > 0
        assert "-" in result

    def test_generate_feature_id_empty_title(self) -> None:
        """Generate feature ID from empty title."""
        module = spec_ingest
        result = module.generate_feature_id("", "12345")
        assert "CONF" in result


class TestConfluenceIngestWithRequests:
    """Tests for ingest_confluence_spec with requests available.

    # TRACE: scripts/spec-ingest.py:239-390 (role: confluence_ingest)
    """

    def test_ingest_confluence_api_success(self) -> None:
        """Confluence API success case."""
        from unittest import mock

        module = spec_ingest

        # Mock requests module within spec_ingest
        mock_requests = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "title": "Test Page Title",
            "body": {"storage": {"value": ""}},
            "version": {"number": 1},
        }
        mock_response.raise_for_status = mock.MagicMock()
        mock_requests.get.return_value = mock_response

        # Patch the requests import within the module
        with mock.patch.dict("os.environ", {
            "CONFLUENCE_URL": "https://test.atlassian.net/wiki",
            "CONFLUENCE_API_TOKEN": "token",
            "CONFLUENCE_USERNAME": "user",
        }):
            # Import requests in the module context
            import sys
            sys.modules["requests"] = mock_requests

            result = module.ingest_confluence_spec("https://test.atlassian.net/wiki/pages/12345")

            # Clean up
            del sys.modules["requests"]

            assert result["title"] == "Test Page Title"
            assert "source_refs" in result

    def test_ingest_confluence_api_error(self) -> None:
        """Confluence API error case."""
        from unittest import mock

        module = spec_ingest

        mock_requests = mock.MagicMock()
        mock_requests.exceptions.RequestException = Exception
        mock_requests.get.side_effect = Exception("API Error")

        with mock.patch.dict("os.environ", {
            "CONFLUENCE_URL": "https://test.atlassian.net/wiki",
            "CONFLUENCE_API_TOKEN": "token",
            "CONFLUENCE_USERNAME": "user",
        }):
            import sys
            sys.modules["requests"] = mock_requests

            result = module.ingest_confluence_spec("https://test.atlassian.net/wiki/pages/12345")

            del sys.modules["requests"]

            assert "ERROR" in result["feature_id"] or "assumptions" in result


class TestJiraIngestWithRequests:
    """Tests for ingest_jira_issue with requests available.

    # TRACE: scripts/spec-ingest.py:499-627 (role: jira_ingest)
    """

    def test_ingest_jira_api_success(self) -> None:
        """Jira API success case."""
        from unittest import mock

        module = spec_ingest

        mock_requests = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "fields": {
                "summary": "Test Issue Summary",
                "description": "",
                "labels": ["api", "backend"],
            }
        }
        mock_response.raise_for_status = mock.MagicMock()
        mock_requests.get.return_value = mock_response

        with mock.patch.dict("os.environ", {
            "JIRA_URL": "https://test.atlassian.net",
            "JIRA_API_TOKEN": "token",
            "JIRA_USERNAME": "user",
        }):
            import sys
            sys.modules["requests"] = mock_requests

            result = module.ingest_jira_issue("PROJ-123")

            del sys.modules["requests"]

            assert result["feature_id"] == "PROJ-123"
            assert result["title"] == "Test Issue Summary"

    def test_ingest_jira_api_error(self) -> None:
        """Jira API error case."""
        from unittest import mock

        module = spec_ingest

        mock_requests = mock.MagicMock()
        mock_requests.exceptions.RequestException = Exception
        mock_requests.get.side_effect = Exception("API Error")

        with mock.patch.dict("os.environ", {
            "JIRA_URL": "https://test.atlassian.net",
            "JIRA_API_TOKEN": "token",
            "JIRA_USERNAME": "user",
        }):
            import sys
            sys.modules["requests"] = mock_requests

            result = module.ingest_jira_issue("PROJ-456")

            del sys.modules["requests"]

            assert "ERROR" in result["feature_id"] or result["feature_id"] == "PROJ-456"


class TestParseConfluenceHtmlDetailed:
    """Tests for parse_confluence_html with various inputs.

    # TRACE: scripts/spec-ingest.py:416-480 (role: html_parsing)
    """

    def test_parse_confluence_html_full(self) -> None:
        """Parse full Confluence HTML."""
        module = spec_ingest

        html = """
<h2>Acceptance Criteria</h2>
<ul><li>AC-1: First criterion</li><li>AC-2: Second criterion</li></ul>
<h2>Business Rules</h2>
<ul><li>BR-1: Must validate</li><li>BR-2: Must log</li></ul>
<h2>Actors</h2>
<ul><li>User</li><li>Admin</li></ul>
<h2>Devices</h2>
<ul><li>Desktop</li><li>Mobile</li></ul>
<h2>Mobile Contexts</h2>
<ul><li>foreground</li><li>background</li></ul>
<h2>Changed Areas</h2>
<ul><li>API</li><li>Database</li></ul>
"""
        ac, br, actors, devices, mobile, changed = module.parse_confluence_html(html)
        assert len(ac) >= 1
        assert len(br) >= 1

    def test_parse_confluence_html_partial(self) -> None:
        """Parse partial Confluence HTML."""
        module = spec_ingest

        html = "<h2>Acceptance Criteria</h2><ul><li>Item</li></ul>"
        ac, br, actors, devices, mobile, changed = module.parse_confluence_html(html)
        assert len(ac) >= 1


class TestParseJiraDescriptionDetailed:
    """Tests for parse_jira_description with various inputs.

    # TRACE: scripts/spec-ingest.py:630-676 (role: description_parsing)
    """

    def test_parse_jira_description_markdown_headers(self) -> None:
        """Parse Jira description with Markdown headers."""
        module = spec_ingest

        description = """
# Acceptance Criteria
* AC-1: First
* AC-2: Second

# Business Rules
- BR-1: Must check
"""
        ac, br, actors = module.parse_jira_description(description)
        assert len(ac) >= 1 or len(br) >= 1

    def test_parse_jira_description_auto_detect(self) -> None:
        """Parse Jira description with auto-detect patterns."""
        module = spec_ingest

        description = """
* AC-001: This is acceptance criteria
* BR-001: This must be validated
* The system shall support logging
"""
        ac, br, actors = module.parse_jira_description(description)
        # Auto-detect patterns: AC-xxx, BR-xxx, must/shall
        assert len(ac) >= 1 or len(br) >= 1


class TestMainDirectCalls:
    """Tests for main function direct calls.

    # TRACE: scripts/spec-ingest.py:682-761 (role: main_entry)
    """

    def test_main_confluence_direct(self, tmp_path: Path) -> None:
        """Main with confluence source direct call."""
        from unittest import mock

        output_file = tmp_path / "output.json"

        with mock.patch.object(sys, "argv", [
            "script",
            "--source", "confluence",
            "--url", "https://example.com/wiki/page/12345",
            "--output", str(output_file),
        ]):
            result = main()
            assert result == 0
            assert output_file.exists()

    def test_main_jira_direct(self, tmp_path: Path) -> None:
        """Main with jira source direct call."""
        from unittest import mock

        output_file = tmp_path / "output.json"

        with mock.patch.object(sys, "argv", [
            "script",
            "--source", "jira",
            "--issue", "PROJ-789",
            "--output", str(output_file),
        ]):
            result = main()
            assert result == 0
            assert output_file.exists()
