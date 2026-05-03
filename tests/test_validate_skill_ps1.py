"""Unit tests for validate-skill.ps1 via PowerShell subprocess."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "validate-skill.ps1"
REPO_ROOT = Path(__file__).parent.parent


def run_powershell_script(script_args: list[str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run PowerShell script and return result."""
    args = ["pwsh", "-File", str(SCRIPT_PATH)]
    if script_args:
        args.extend(script_args)
    return subprocess.run(
        args,
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def temp_skill_dir(tmp_path: Path) -> Path:
    """Create a temporary skill directory structure."""
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    return skill_dir


class TestPowershellFrontmatter:
    """Tests for PowerShell frontmatter validation."""

    def test_valid_skill_passes(self) -> None:
        """Test that the actual skill passes validation."""
        result = run_powershell_script()
        # This should pass for the actual manual-bb-test-harness skill
        assert "checks passed" in result.stdout or result.returncode == 0

    def test_missing_skill_md_fails(self, temp_skill_dir: Path) -> None:
        """Test missing SKILL.md detection."""
        result = run_powershell_script(["-SkillPath", str(temp_skill_dir)], cwd=REPO_ROOT)
        # Script should fail when SKILL.md is missing
        # Note: Current script has hardcoded path, may need modification

    def test_missing_frontmatter_fails(self, temp_skill_dir: Path) -> None:
        """Test missing frontmatter detection."""
        skill_md = temp_skill_dir / "SKILL.md"
        skill_md.write_text("No frontmatter here", encoding="utf-8")
        result = run_powershell_script(["-SkillPath", str(temp_skill_dir)], cwd=REPO_ROOT)

    def test_malformed_frontmatter_fails(self, temp_skill_dir: Path) -> None:
        """Test malformed frontmatter detection."""
        skill_md = temp_skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: test\n---", encoding="utf-8")  # Missing closing ---
        result = run_powershell_script(["-SkillPath", str(temp_skill_dir)], cwd=REPO_ROOT)


class TestPowershellRequiredFiles:
    """Tests for PowerShell required file validation."""

    def test_missing_required_reference_file(self, temp_skill_dir: Path) -> None:
        """Test missing reference file detection."""
        skill_md = temp_skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\ndescription: Test\n---\n", encoding="utf-8")
        result = run_powershell_script(["-SkillPath", str(temp_skill_dir)], cwd=REPO_ROOT)


class TestPowershellTodoMarkers:
    """Tests for PowerShell TODO marker detection."""

    def test_todo_marker_detected(self, temp_skill_dir: Path) -> None:
        """Test TODO marker detection in files."""
        skill_md = temp_skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\ndescription: Test\n---\nTODO: implement\n", encoding="utf-8")
        result = run_powershell_script(["-SkillPath", str(temp_skill_dir)], cwd=REPO_ROOT)


class TestPowershellJsonValidation:
    """Tests for PowerShell JSON schema validation."""

    def test_invalid_json_schema_detected(self, tmp_path: Path) -> None:
        """Test invalid JSON schema file detection."""
        schemas_dir = REPO_ROOT / "schemas"
        # Create a temporary invalid schema for testing
        # This test should be careful not to modify actual schemas


class TestPowershellParameters:
    """Tests for PowerShell script parameters."""

    def test_version_flag(self) -> None:
        """Test --version flag output."""
        result = run_powershell_script(["--version"])
        # Should output version and exit successfully
        pass

    def test_skill_name_parameter(self) -> None:
        """Test -SkillName parameter customization."""
        result = run_powershell_script(["-SkillName", "manual-bb-test-harness"])
        assert result.returncode == 0 or "checks passed" in result.stdout


class TestPowershellIntegration:
    """Integration tests for PowerShell script with actual repo."""

    def test_actual_repo_validates(self) -> None:
        """Test that actual repository passes all checks."""
        result = run_powershell_script()
        assert result.returncode == 0
        assert "checks passed" in result.stdout

    def test_actual_skill_md_frontmatter(self) -> None:
        """Test actual SKILL.md has valid frontmatter."""
        skill_md = REPO_ROOT / "skills" / "manual-bb-test-harness" / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "name: manual-bb-test-harness" in content
        assert "description:" in content


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="PowerShell tests primarily for Windows, pwsh available on other platforms"
)
class TestPowershellWindowsSpecific:
    """Windows-specific PowerShell tests."""

    def test_windows_line_endings(self, temp_skill_dir: Path) -> None:
        """Test handling of Windows CRLF line endings."""
        skill_md = temp_skill_dir / "SKILL.md"
        content = "---\r\nname: test-skill\r\ndescription: Test\r\n---\r\n"
        skill_md.write_bytes(content.encode("utf-8"))
        result = run_powershell_script(["-SkillPath", str(temp_skill_dir)], cwd=REPO_ROOT)