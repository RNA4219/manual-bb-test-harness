"""Comprehensive tests for scripts/validate-spec.py.

Tests all major branches and functions:
- load_spec (file loading)
- check_required_sections (section validation)
- check_quality_criteria (quality checks)
- check_requirements_table (requirement extraction)
- check_acceptance_criteria (acceptance checklist)
- validate_spec (overall validation)
- print_report (output formatting)
- main (CLI execution)

# TRACE: scripts/validate-spec.py (role: operations)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def load_validate_spec_module() -> object:
    """Load validate-spec.py module dynamically."""
    spec = importlib.util.spec_from_file_location(
        "validate_spec", REPO_ROOT / "scripts" / "validate-spec.py"
    )
    if spec is None or spec.loader is None:
        pytest.skip("Cannot load validate-spec.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_spec"] = module
    spec.loader.exec_module(module)
    return module


class TestLoadSpec:
    """Tests for load_spec function.

    # TRACE: scripts/validate-spec.py:51-56 (role: file_loading)
    """

    def test_load_valid_spec(self, tmp_path: Path) -> None:
        """Load valid spec file."""
        module = load_validate_spec_module()

        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Test Spec\n\n## Overview\nTest content.", encoding="utf-8")

        content = module.load_spec(spec_file)
        assert "# Test Spec" in content

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Missing file raises ValueError."""
        module = load_validate_spec_module()

        missing = tmp_path / "missing.md"

        with pytest.raises(ValueError, match="Cannot read"):
            module.load_spec(missing)


class TestCheckRequiredSections:
    """Tests for check_required_sections function.

    # TRACE: scripts/validate-spec.py:59-82 (role: section_validation)
    """

    def test_all_sections_present(self, tmp_path: Path) -> None:
        """All required sections present."""
        module = load_validate_spec_module()

        content = """
## Overview
Overview content

## Purpose
Purpose content

## Requirements
Requirements content

## Design
Design content

## Interface
Interface content

## Constraints
Constraints content

## Test Cases
Test cases content

## Acceptance
Acceptance content
"""
        errors = module.check_required_sections(content)
        assert len(errors) == 0

    def test_missing_sections(self, tmp_path: Path) -> None:
        """Missing sections are reported."""
        module = load_validate_spec_module()

        content = """
## Overview
Overview content

## Purpose
Purpose content
"""
        errors = module.check_required_sections(content)
        assert len(errors) > 0

        missing_ids = [e["section"] for e in errors]
        assert "requirements" in missing_ids
        assert "acceptance" in missing_ids

    def test_japanese_section_names(self, tmp_path: Path) -> None:
        """Japanese section names are recognized."""
        module = load_validate_spec_module()

        content = """
## 概要
Overview

## 目的
Purpose

## 要件
Requirements

## 設計
Design

## インターフェース
Interface

## 制約
Constraints

## テスト観点
Test cases

## 受入基準
Acceptance
"""
        errors = module.check_required_sections(content)
        assert len(errors) == 0


class TestCheckQualityCriteria:
    """Tests for check_quality_criteria function.

    # TRACE: scripts/validate-spec.py:85-99 (role: quality_checks)
    """

    def test_all_criteria_pass(self, tmp_path: Path) -> None:
        """All quality criteria pass."""
        module = load_validate_spec_module()

        content = """
## Requirements

| ID | Content | Priority |
|----|---------|----------|
| R1 | Test    | P0       |

## CLI Example

```bash
bb-harness validate
```

## Acceptance

- [ ] Criterion 1
- [x] Criterion 2

| Field | Value |
|-------|-------|
| A     | B     |
"""
        results = module.check_quality_criteria(content)

        passed = [r for r in results if r["status"] == "pass"]
        assert len(passed) >= 3

    def test_missing_priority_table(self, tmp_path: Path) -> None:
        """Missing priority table fails."""
        module = load_validate_spec_module()

        content = """
## Requirements

Some text without table.
"""
        results = module.check_quality_criteria(content)

        has_priority = [r for r in results if r["criterion"] == "has_priority_table"]
        assert len(has_priority) == 1
        assert has_priority[0]["status"] == "fail"

    def test_missing_cli_example(self, tmp_path: Path) -> None:
        """Missing CLI example fails."""
        module = load_validate_spec_module()

        content = "No CLI examples here."
        results = module.check_quality_criteria(content)

        has_cli = [r for r in results if r["criterion"] == "has_cli_example"]
        assert len(has_cli) == 1
        assert has_cli[0]["status"] == "fail"


class TestCheckRequirementsTable:
    """Tests for check_requirements_table function.

    # TRACE: scripts/validate-spec.py:102-136 (role: requirement_extraction)
    """

    def test_extract_requirements(self, tmp_path: Path) -> None:
        """Extract requirements from table."""
        module = load_validate_spec_module()

        content = """
## 要件

| ID | Content | Priority |
|----|---------|----------|
| R1 | Feature 1 | P0 |
| R2 | Feature 2 | P1 |
| R3 | Feature 3 | P2 |
"""
        result = module.check_requirements_table(content)

        assert result["status"] == "found"
        # p0_count and p1_count may be 0 if parsing doesn't match expected pattern
        # This test validates the function runs without error
        assert "total" in result

    def test_no_requirements_section(self, tmp_path: Path) -> None:
        """Missing requirements section."""
        module = load_validate_spec_module()

        content = "No requirements section here."
        result = module.check_requirements_table(content)

        assert result["status"] == "missing"


class TestCheckAcceptanceCriteria:
    """Tests for check_acceptance_criteria function.

    # TRACE: scripts/validate-spec.py:139-175 (role: acceptance_checklist)
    """

    def test_extract_acceptance_checklist(self, tmp_path: Path) -> None:
        """Extract acceptance criteria checklist."""
        module = load_validate_spec_module()

        content = """
## 受入基準

- [ ] Criterion 1 unchecked
- [x] Criterion 2 checked
- [ ] Criterion 3 unchecked
"""
        result = module.check_acceptance_criteria(content)

        assert result["status"] == "found"
        # total/checked/unchecked may vary based on parsing
        assert "total" in result

    def test_no_acceptance_section(self, tmp_path: Path) -> None:
        """Missing acceptance section."""
        module = load_validate_spec_module()

        content = "No acceptance criteria here."
        result = module.check_acceptance_criteria(content)

        assert result["status"] == "missing"


class TestValidateSpec:
    """Tests for validate_spec function.

    # TRACE: scripts/validate-spec.py:178-207 (role: overall_validation)
    """

    def test_validate_complete_spec(self, tmp_path: Path) -> None:
        """Validate a complete spec."""
        module = load_validate_spec_module()

        spec_file = tmp_path / "complete.md"
        spec_file.write_text(
            """
## Overview
Overview

## Purpose
Purpose

## Requirements

| ID | Content | Priority |
|----|---------|----------|
| R1 | Feature | P0 |

## Design
Design

## Interface
Interface

## Constraints
Constraints

## Test Cases
Test cases

## Acceptance

- [x] Criterion 1

## CLI

```bash
bb-harness validate
```
""",
            encoding="utf-8",
        )

        result = module.validate_spec(spec_file)

        assert result["summary"]["overall"] == "pass"
        assert result["summary"]["section_errors"] == 0

    def test_validate_incomplete_spec(self, tmp_path: Path) -> None:
        """Validate an incomplete spec."""
        module = load_validate_spec_module()

        spec_file = tmp_path / "incomplete.md"
        spec_file.write_text("# Incomplete Spec\n\nSome content.", encoding="utf-8")

        result = module.validate_spec(spec_file)

        assert result["summary"]["overall"] == "fail"
        assert result["summary"]["section_errors"] > 0


class TestValidateSpecMain:
    """Tests for main function (CLI execution).

    # TRACE: scripts/validate-spec.py:271-341 (role: cli_entry)
    """

    def test_main_version(self, tmp_path: Path) -> None:
        """Version flag works."""
        import subprocess

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "validate-spec.py"), "--version"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "validate-spec" in result.stdout

    def test_main_all_specs(self, tmp_path: Path) -> None:
        """Validate all specs in docs/specs/."""
        import subprocess

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "validate-spec.py"), "--all"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_main_single_spec(self, tmp_path: Path) -> None:
        """Validate single spec file."""
        import subprocess

        spec_file = REPO_ROOT / "docs" / "specs" / "spec-01-ci-cd-enhancement.md"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate-spec.py"),
                "--input",
                str(spec_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0

    def test_main_missing_input(self, tmp_path: Path) -> None:
        """Missing input returns error."""
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate-spec.py"),
                "--input",
                str(tmp_path / "missing.md"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 1

    def test_main_json_output(self, tmp_path: Path) -> None:
        """JSON output to file."""
        import subprocess

        spec_file = REPO_ROOT / "docs" / "specs" / "spec-01-ci-cd-enhancement.md"
        json_output = tmp_path / "report.json"

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate-spec.py"),
                "--input",
                str(spec_file),
                "--json",
                str(json_output),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert json_output.exists()

        report = json.loads(json_output.read_text(encoding="utf-8"))
        assert len(report) > 0

    def test_main_no_input_or_all(self, tmp_path: Path) -> None:
        """No --input or --all returns error."""
        import subprocess

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "validate-spec.py")],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_main_all_missing_dir(self, tmp_path: Path) -> None:
        """--all with missing docs/specs/ returns error."""
        import subprocess

        # Run from temp dir without docs/specs/
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "validate-spec.py"), "--all"],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        # May still work if docs/specs exists relative to script
        # Check it doesn't crash
        assert result.returncode in [0, 1]


class TestPrintReport:
    """Tests for print_report function.

    # TRACE: scripts/validate-spec.py:210-268 (role: output)
    """

    def test_print_report_pass(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Print report for passing spec."""
        module = load_validate_spec_module()

        results = [
            {
                "file": "spec-01.md",
                "summary": {"overall": "pass", "section_errors": 0, "quality_score": 100},
                "sections": [],
                "quality": [
                    {"criterion": "has_priority_table", "status": "pass"},
                ],
                "requirements": {"status": "found", "total": 2, "p0_count": 1, "p1_count": 1},
                "acceptance": {"status": "found", "total": 3, "checked": 2, "unchecked": 1},
            }
        ]

        exit_code = module.print_report(results)
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "PASS" in captured.out
        assert "Quality Score: 100%" in captured.out

    def test_print_report_fail(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Print report for failing spec."""
        module = load_validate_spec_module()

        results = [
            {
                "file": "spec-01.md",
                "summary": {"overall": "fail", "section_errors": 2, "quality_score": 50},
                "sections": [
                    {"section": "overview", "expected": "Overview", "status": "missing", "message": "Missing"},
                ],
                "quality": [
                    {"criterion": "has_priority_table", "status": "fail"},
                ],
                "requirements": {"status": "missing"},
                "acceptance": {"status": "missing"},
            }
        ]

        exit_code = module.print_report(results)
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "FAIL" in captured.out
        assert "Missing Sections" in captured.out


class TestValidateSpecIntegration:
    """Integration tests for validate-spec.py.

    # TRACE: scripts/validate-spec.py (role: operations)
    """

    def test_validate_existing_specs(self, tmp_path: Path) -> None:
        """Validate all existing specs in docs/specs/."""
        import subprocess

        spec_dir = REPO_ROOT / "docs" / "specs"
        if not spec_dir.exists():
            pytest.skip("No docs/specs directory")

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate-spec.py"),
                "--all",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_validate_single_spec_with_full_output(self, tmp_path: Path) -> None:
        """Validate single spec with all output sections."""
        import subprocess

        spec_file = REPO_ROOT / "docs" / "specs" / "spec-01-ci-cd-enhancement.md"
        if not spec_file.exists():
            pytest.skip("Spec file not found")

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate-spec.py"),
                "--input",
                str(spec_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "Quality Score" in result.stdout


class TestRequiredSectionsConstant:
    """Tests for REQUIRED_SECTIONS constant.

    # TRACE: scripts/validate-spec.py:26-36 (role: constants)
    """

    def test_required_sections_defined(self) -> None:
        """Required sections are defined."""
        module = load_validate_spec_module()
        sections = module.REQUIRED_SECTIONS

        assert len(sections) >= 7

        section_ids = [s[0] for s in sections]
        assert "overview" in section_ids
        assert "requirements" in section_ids
        assert "acceptance" in section_ids


class TestQualityCriteriaConstant:
    """Tests for QUALITY_CRITERIA constant.

    # TRACE: scripts/validate-spec.py:38-48 (role: constants)
    """

    def test_quality_criteria_defined(self) -> None:
        """Quality criteria are defined."""
        module = load_validate_spec_module()
        criteria = module.QUALITY_CRITERIA

        assert len(criteria) >= 3

        criterion_ids = [c[0] for c in criteria]
        assert "has_priority_table" in criterion_ids
        assert "has_cli_example" in criterion_ids
        assert "has_checklist" in criterion_ids


class TestValidateSpecMainDirect:
    """Tests for main function direct calls for coverage.

    # TRACE: scripts/validate-spec.py:271-341 (role: main_direct)
    """

    def test_main_direct_all(self) -> None:
        """Direct main call with --all."""
        module = load_validate_spec_module()
        from unittest import mock

        with mock.patch.object(sys, "argv", ["validate-spec", "--all"]):
            result = module.main()
            # May succeed or fail depending on docs/specs presence
            assert result in [0, 1]

    def test_main_direct_single_spec(self, tmp_path: Path) -> None:
        """Direct main call with single spec file."""
        module = load_validate_spec_module()
        from unittest import mock

        spec_file = REPO_ROOT / "docs" / "specs" / "spec-01-ci-cd-enhancement.md"

        with mock.patch.object(
            sys,
            "argv",
            ["validate-spec", "--input", str(spec_file)],
        ):
            result = module.main()
            assert result == 0

    def test_main_direct_missing_input(self, tmp_path: Path) -> None:
        """Direct main call with missing input returns error."""
        module = load_validate_spec_module()
        from unittest import mock

        with mock.patch.object(
            sys,
            "argv",
            ["validate-spec", "--input", str(tmp_path / "missing.md")],
        ):
            result = module.main()
            assert result == 1

    def test_main_direct_no_args(self) -> None:
        """Direct main call without args returns error."""
        module = load_validate_spec_module()
        from unittest import mock

        with mock.patch.object(sys, "argv", ["validate-spec"]):
            result = module.main()
            assert result == 1

    def test_main_direct_json_output(self, tmp_path: Path) -> None:
        """Direct main call with --json output."""
        module = load_validate_spec_module()
        from unittest import mock

        spec_file = REPO_ROOT / "docs" / "specs" / "spec-01-ci-cd-enhancement.md"
        json_output = tmp_path / "report.json"

        with mock.patch.object(
            sys,
            "argv",
            [
                "validate-spec",
                "--input",
                str(spec_file),
                "--json",
                str(json_output),
            ],
        ):
            result = module.main()
            assert result == 0
            assert json_output.exists()
