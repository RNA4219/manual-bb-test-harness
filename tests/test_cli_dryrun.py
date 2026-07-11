"""Tests for CLI dry-run propagation and import commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


class TestExportNotionDryRunViaCLI:
    """Tests for bb-harness --dry-run export notion."""

    def test_top_level_dry_run_export_notion(self) -> None:
        """bb-harness --dry-run export notion should succeed without NOTION_API_TOKEN."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--dry-run",
                "export",
                "notion",
                "--score",
                "90",
                "--status",
                "pass",
                "--db",
                "dummy_db_id",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "DRY RUN" in result.stdout

    def test_subcommand_dry_run_export_notion(self) -> None:
        """bb-harness export notion --dry-run should also work."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "export",
                "notion",
                "--score",
                "85",
                "--status",
                "conditional_pass",
                "--db",
                "test_db",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "DRY RUN" in result.stdout


class TestImportTestRailDryRun:
    """Tests for import-testrail.py --dry-run."""

    def test_direct_script_dry_run(self) -> None:
        """scripts/import-testrail.py --dry-run should succeed without credentials."""
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "import-testrail.py"),
                "--project",
                "12",
                "--run",
                "1234",
                "--output",
                str(PROJECT_ROOT / "tmp-import"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "DRY RUN" in result.stdout
        assert "Project: 12" in result.stdout

    def test_cli_wrapper_dry_run(self) -> None:
        """bb-harness import testrail --dry-run should work."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "import",
                "testrail",
                "--project",
                "12",
                "--run",
                "1234",
                "--output",
                str(PROJECT_ROOT / "tmp-import"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "DRY RUN" in result.stdout

    def test_cli_top_level_dry_run(self) -> None:
        """bb-harness --dry-run import testrail should also work."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--dry-run",
                "import",
                "testrail",
                "--project",
                "99",
                "--run",
                "5678",
                "--output",
                str(PROJECT_ROOT / "tmp-import"),
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "DRY RUN" in result.stdout


class TestImportXrayDryRun:
    """Tests for import-xray.py --dry-run."""

    def test_direct_script_dry_run(self) -> None:
        """scripts/import-xray.py --dry-run should succeed without credentials."""
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "import-xray.py"),
                "--exec",
                "TEST-1",
                "--output",
                str(PROJECT_ROOT / "tmp-import"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "DRY RUN" in result.stdout
        assert "Execution: TEST-1" in result.stdout

    def test_cli_wrapper_dry_run(self) -> None:
        """bb-harness import xray --dry-run should work."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "import",
                "xray",
                "--exec",
                "PROJ-TE-123",
                "--output",
                str(PROJECT_ROOT / "tmp-import"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "DRY RUN" in result.stdout

    def test_cli_top_level_dry_run(self) -> None:
        """bb-harness --dry-run import xray should also work."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--dry-run",
                "import",
                "xray",
                "--exec",
                "TEST-99",
                "--output",
                str(PROJECT_ROOT / "tmp-import"),
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "DRY RUN" in result.stdout


class TestImportHelp:
    """Tests for bb-harness import --help."""

    def test_import_help(self) -> None:
        """bb-harness import --help should show usage."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "import",
                "--help",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "testrail" in result.stdout.lower()
        assert "xray" in result.stdout.lower()


class TestVerboseOutput:
    """Tests for --verbose flag."""

    def test_validate_verbose(self) -> None:
        """bb-harness --verbose validate should show command details."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--verbose",
                "validate",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        # verbose output goes to stderr
        assert "[verbose]" in result.stderr
        assert "Running:" in result.stderr

    def test_ingest_verbose(self) -> None:
        """bb-harness --verbose ingest should show command and source."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--verbose",
                "ingest",
                "--source",
                "markdown",
                "--input",
                "goldens/order-cancel.input.md",
                "--output",
                str(PROJECT_ROOT / "tmp-verbose-test.json"),
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert "[verbose]" in result.stderr
        assert "Running:" in result.stderr
        assert "Source: markdown" in result.stderr

    def test_gate_verbose(self) -> None:
        """bb-harness --verbose gate should show command and profile."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--verbose",
                "gate",
                "--input",
                "examples/artifacts",
                "--output",
                str(PROJECT_ROOT / "tmp-verbose-gate.json"),
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert "[verbose]" in result.stderr
        assert "Profile:" in result.stderr
        assert "Profile:" in result.stderr


class TestRunForwardTest:
    """Tests for bb-harness run forward-test (PLAN-CLI-03)."""

    def test_forward_test_help(self) -> None:
        """bb-harness run forward-test --help should show usage."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "run",
                "forward-test",
                "--help",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "forward-test" in result.stdout.lower()
        assert "--input" in result.stdout
        assert "--skill" in result.stdout

    def test_run_help(self) -> None:
        """bb-harness run --help should list forward-test."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "run",
                "--help",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "forward-test" in result.stdout.lower()

    def test_forward_test_execution(self) -> None:
        """bb-harness run forward-test with valid input should print prompt."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "run",
                "forward-test",
                "--input",
                "goldens/order-cancel.input.md",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "Forward Test" in result.stdout
        assert "order-cancel" in result.stdout

    def test_forward_test_missing_input(self) -> None:
        """bb-harness run forward-test with missing input should fail."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "run",
                "forward-test",
                "--input",
                "nonexistent-file.md",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_forward_test_verbose(self) -> None:
        """bb-harness --verbose run forward-test should show details."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--verbose",
                "run",
                "forward-test",
                "--input",
                "goldens/order-cancel.input.md",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "[verbose]" in result.stderr
        assert "Skill:" in result.stderr
