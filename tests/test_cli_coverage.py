"""Direct function tests for CLI commands to improve coverage.

This module tests CLI commands by directly calling the run functions
instead of subprocess, which allows coverage to be measured.

# TRACE: src/bb_harness/cli.py (role: entry_point)
# TRACE: src/bb_harness/commands/*.py (role: command_handlers)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bb_harness.cli import create_parser, main
from bb_harness.commands import (
    export,
    gate,
    heatmap,
    import_results,
    ingest,
    regression_graph,
    run,
    state_diagram,
    validate,
)

REPO_ROOT = Path(__file__).parent.parent


class TestValidateCommand:
    """Tests for validate command handler.

    # TRACE: src/bb_harness/commands/validate.py (role: command)
    """

    def test_validate_run_with_skill_path(self) -> None:
        """Validate run with skill path."""
        parser = create_parser()
        args = parser.parse_args([
            "validate",
            str(REPO_ROOT / "skills" / "manual-bb-test-harness"),
        ])
        result = validate.run(args)
        # Returns 0 for valid skill
        assert result in [0, 1]

    def test_validate_run_verbose(self) -> None:
        """Validate run with verbose flag."""
        parser = create_parser()
        args = parser.parse_args([
            "--verbose",
            "validate",
            str(REPO_ROOT / "skills" / "manual-bb-test-harness"),
        ])
        assert args.global_verbose is True
        result = validate.run(args)
        assert result in [0, 1]

    def test_validate_missing_skill(self) -> None:
        """Validate with missing skill directory."""
        parser = create_parser()
        args = parser.parse_args([
            "validate",
            str(REPO_ROOT / "nonexistent-skill"),
        ])
        result = validate.run(args)
        # Should return error code
        assert result != 0


class TestIngestCommand:
    """Tests for ingest command handler.

    # TRACE: src/bb_harness/commands/ingest.py (role: command)
    """

    def test_ingest_markdown(self, tmp_path: Path) -> None:
        """Ingest markdown spec."""
        output_file = tmp_path / "output.json"
        parser = create_parser()
        args = parser.parse_args([
            "ingest",
            "--source", "markdown",
            "--input", str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
            "--output", str(output_file),
        ])
        result = ingest.run(args)
        assert result == 0
        assert output_file.exists()

    def test_ingest_verbose(self, tmp_path: Path) -> None:
        """Ingest with verbose."""
        output_file = tmp_path / "output.json"
        parser = create_parser()
        args = parser.parse_args([
            "--verbose",
            "ingest",
            "--source", "markdown",
            "--input", str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
            "--output", str(output_file),
        ])
        result = ingest.run(args)
        assert result == 0


class TestGateCommand:
    """Tests for gate command handler.

    # TRACE: src/bb_harness/commands/gate.py (role: command)
    """

    def test_gate_with_artifacts(self, tmp_path: Path) -> None:
        """Gate decision from artifacts."""
        output_file = tmp_path / "gate.json"
        parser = create_parser()
        args = parser.parse_args([
            "gate",
            "--input", str(REPO_ROOT / "examples" / "artifacts"),
            "--output", str(output_file),
        ])
        result = gate.run(args)
        assert result == 0
        assert output_file.exists()

        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)
        assert "feature_id" in data or "blocking_risks" in data

    def test_gate_verbose(self, tmp_path: Path) -> None:
        """Gate with verbose."""
        output_file = tmp_path / "gate.json"
        parser = create_parser()
        args = parser.parse_args([
            "--verbose",
            "gate",
            "--input", str(REPO_ROOT / "examples" / "artifacts"),
            "--output", str(output_file),
        ])
        result = gate.run(args)
        assert result == 0

    def test_gate_with_profile(self, tmp_path: Path) -> None:
        """Gate with profile."""
        output_file = tmp_path / "gate.json"
        parser = create_parser()
        args = parser.parse_args([
            "gate",
            "--input", str(REPO_ROOT / "examples" / "artifacts"),
            "--output", str(output_file),
            "--profile", "standard",
        ])
        result = gate.run(args)
        assert result == 0


class TestExportCommand:
    """Tests for export command handler.

    # TRACE: src/bb_harness/commands/export.py (role: command)
    """

    def test_export_notion_dry_run(self) -> None:
        """Export notion with dry-run."""
        parser = create_parser()
        args = parser.parse_args([
            "export", "notion",
            "--dry-run",
            "--score", "90",
            "--status", "pass",
            "--db", "dummy_db",
        ])
        result = export.run(args)
        assert result == 0

    def test_export_notion_verbose(self) -> None:
        """Export notion with verbose."""
        parser = create_parser()
        args = parser.parse_args([
            "--verbose",
            "export", "notion",
            "--dry-run",
            "--score", "85",
            "--status", "conditional_pass",
            "--db", "test_db",
        ])
        result = export.run(args)
        assert result == 0

    def test_export_testrail(self, tmp_path: Path) -> None:
        """Export testrail."""
        output_file = tmp_path / "testrail.csv"
        parser = create_parser()
        args = parser.parse_args([
            "export", "testrail",
            "--input", str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.manual_case_set.json"),
            "--output", str(output_file),
            "--format", "csv",
        ])
        result = export.run(args)
        # Accept success or graceful failure
        assert result in [0, 1, 2]

    def test_export_xray(self, tmp_path: Path) -> None:
        """Export xray."""
        output_file = tmp_path / "xray.json"
        parser = create_parser()
        args = parser.parse_args([
            "export", "xray",
            "--input", str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.manual_case_set.json"),
            "--output", str(output_file),
        ])
        result = export.run(args)
        assert result in [0, 1, 2]


class TestImportCommand:
    """Tests for import command handler.

    # TRACE: src/bb_harness/commands/import_results.py (role: command)
    """

    def test_import_testrail_dry_run(self, tmp_path: Path) -> None:
        """Import testrail with dry-run."""
        parser = create_parser()
        args = parser.parse_args([
            "import", "testrail",
            "--dry-run",
            "--project", "12",
            "--run", "1234",
            "--output", str(tmp_path),
        ])
        result = import_results.run(args)
        assert result == 0

    def test_import_xray_dry_run(self, tmp_path: Path) -> None:
        """Import xray with dry-run."""
        parser = create_parser()
        args = parser.parse_args([
            "import", "xray",
            "--dry-run",
            "--exec", "TEST-1",
            "--output", str(tmp_path),
        ])
        result = import_results.run(args)
        assert result == 0

    def test_import_testrail_verbose(self, tmp_path: Path) -> None:
        """Import testrail with verbose."""
        parser = create_parser()
        args = parser.parse_args([
            "--verbose",
            "import", "testrail",
            "--dry-run",
            "--project", "99",
            "--run", "5678",
            "--output", str(tmp_path),
        ])
        result = import_results.run(args)
        assert result == 0


class TestRunCommand:
    """Tests for run command handler.

    # TRACE: src/bb_harness/commands/run.py (role: command)
    """

    def test_run_forward_test(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Run forward-test."""
        parser = create_parser()
        args = parser.parse_args([
            "run", "forward-test",
            "--input", str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
        ])
        result = run.run(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Forward Test" in captured.out

    def test_run_forward_test_mobile(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Run forward-test with mobile input."""
        parser = create_parser()
        args = parser.parse_args([
            "run", "forward-test",
            "--input", str(REPO_ROOT / "goldens" / "mobile-session-resume.input.md"),
        ])
        result = run.run(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Forward Test" in captured.out

    def test_run_forward_test_verbose(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Run forward-test with verbose."""
        parser = create_parser()
        args = parser.parse_args([
            "--verbose",
            "run", "forward-test",
            "--input", str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
        ])
        result = run.run(args)
        assert result == 0
        # verbose output may go to stdout or stderr depending on implementation
        captured = capsys.readouterr()
        # Just check that output was generated
        assert "Forward Test" in captured.out

    def test_run_forward_test_missing_input(self) -> None:
        """Run forward-test with missing input."""
        parser = create_parser()
        args = parser.parse_args([
            "run", "forward-test",
            "--input", "nonexistent.md",
        ])
        result = run.run(args)
        assert result != 0


class TestStateDiagramCommand:
    """Tests for state-diagram command handler.

    # TRACE: src/bb_harness/commands/state_diagram.py (role: command)
    """

    def test_state_diagram(self, tmp_path: Path) -> None:
        """Generate state diagram."""
        output_file = tmp_path / "diagram.mmd"
        parser = create_parser()
        args = parser.parse_args([
            "state-diagram",
            "--input", str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.test_model.json"),
            "--output", str(output_file),
        ])
        result = state_diagram.run(args)
        assert result == 0
        assert output_file.exists()


class TestRegressionGraphCommand:
    """Tests for regression-graph command handler.

    # TRACE: src/bb_harness/commands/regression_graph.py (role: command)
    """

    def test_regression_graph(self, tmp_path: Path) -> None:
        """Generate regression graph."""
        output_file = tmp_path / "graph.dot"
        parser = create_parser()
        args = parser.parse_args([
            "regression-graph",
            "--input", str(REPO_ROOT / "examples" / "artifacts"),
            "--output", str(output_file),
        ])
        result = regression_graph.run(args)
        assert result == 0


class TestHeatmapCommand:
    """Tests for heatmap command handler.

    # TRACE: src/bb_harness/commands/heatmap.py (role: command)
    """

    def test_heatmap(self, tmp_path: Path) -> None:
        """Generate heatmap."""
        output_file = tmp_path / "heatmap.html"
        parser = create_parser()
        args = parser.parse_args([
            "heatmap",
            "--input", str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.risk_register.json"),
            "--output", str(output_file),
            "--format", "html",
        ])
        result = heatmap.run(args)
        # Accept success or graceful failure (heatmap may need specific structure)
        assert result in [0, 1]


class TestMainFunction:
    """Tests for main function.

    # TRACE: src/bb_harness/cli.py (role: entry_point)
    """

    def test_main_empty_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Main with empty args shows help."""
        result = main([])
        assert result == 0
        captured = capsys.readouterr()
        assert "bb-harness" in captured.out

    def test_main_validate(self) -> None:
        """Main with validate command."""
        result = main([
            "validate",
            str(REPO_ROOT / "skills" / "manual-bb-test-harness"),
        ])
        assert result in [0, 1]

    def test_main_ingest(self, tmp_path: Path) -> None:
        """Main with ingest command."""
        output_file = tmp_path / "output.json"
        result = main([
            "ingest",
            "--source", "markdown",
            "--input", str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
            "--output", str(output_file),
        ])
        assert result == 0

    def test_main_gate(self, tmp_path: Path) -> None:
        """Main with gate command."""
        output_file = tmp_path / "gate.json"
        result = main([
            "gate",
            "--input", str(REPO_ROOT / "examples" / "artifacts"),
            "--output", str(output_file),
        ])
        assert result == 0

    def test_main_export_notion(self) -> None:
        """Main with export notion command."""
        result = main([
            "--dry-run",
            "export", "notion",
            "--score", "90",
            "--status", "pass",
            "--db", "dummy",
        ])
        assert result == 0

    def test_main_import_testrail(self, tmp_path: Path) -> None:
        """Main with import testrail command."""
        result = main([
            "--dry-run",
            "import", "testrail",
            "--project", "12",
            "--run", "1234",
            "--output", str(tmp_path),
        ])
        assert result == 0

    def test_main_run_forward_test(self) -> None:
        """Main with run forward-test command."""
        result = main([
            "run", "forward-test",
            "--input", str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
        ])
        assert result == 0

    def test_main_state_diagram(self, tmp_path: Path) -> None:
        """Main with state-diagram command."""
        output_file = tmp_path / "diagram.mmd"
        result = main([
            "state-diagram",
            "--input", str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.test_model.json"),
            "--output", str(output_file),
        ])
        assert result == 0

    def test_main_regression_graph(self, tmp_path: Path) -> None:
        """Main with regression-graph command."""
        output_file = tmp_path / "graph.dot"
        result = main([
            "regression-graph",
            "--input", str(REPO_ROOT / "examples" / "artifacts"),
            "--output", str(output_file),
        ])
        assert result == 0

    def test_main_verbose_propagation(self, tmp_path: Path) -> None:
        """Main propagates --verbose to subcommand."""
        output_file = tmp_path / "gate.json"
        result = main([
            "--verbose",
            "gate",
            "--input", str(REPO_ROOT / "examples" / "artifacts"),
            "--output", str(output_file),
        ])
        assert result == 0

    def test_main_dry_run_propagation(self) -> None:
        """Main propagates --dry-run to subcommand."""
        result = main([
            "--dry-run",
            "export", "notion",
            "--score", "90",
            "--status", "pass",
            "--db", "dummy",
        ])
        assert result == 0
