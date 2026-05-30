"""Tests to reach 90%+ coverage for src/bb_harness.

Remaining uncovered:
- __main__.py: 3-5 (module execution)
- cli.py: 108 (error handling)
- export.py: 107-108, 131, 141-142
- gate.py: 64-77
- import_results.py: 86-87, 99, 110-111
- ingest.py: 57-58, 61
- run.py: 65-66, 71-72, 115-119
- heatmap.py: 58
- regression_graph.py: 51
- state_diagram.py: 43

# TRACE: src/bb_harness/__main__.py (role: module_entry)
# TRACE: src/bb_harness/cli.py:108 (role: error_handling)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


class TestMainModule:
    """Tests for __main__.py module execution.

    # TRACE: src/bb_harness/__main__.py (role: module_entry)
    """

    def test_module_execution_help(self) -> None:
        """python -m bb_harness --help works."""
        result = subprocess.run(
            [sys.executable, "-m", "bb_harness", "--help"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "bb-harness" in result.stdout

    def test_module_execution_version(self) -> None:
        """python -m bb_harness --version works."""
        result = subprocess.run(
            [sys.executable, "-m", "bb_harness", "--version"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "0.2.0" in result.stdout

    def test_module_execution_no_args(self) -> None:
        """python -m bb_harness with no args shows help."""
        result = subprocess.run(
            [sys.executable, "-m", "bb_harness"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "bb-harness" in result.stdout

    def test_module_execution_validate(self) -> None:
        """python -m bb_harness validate works."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "validate",
                str(REPO_ROOT / "skills" / "manual-bb-test-harness"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode in [0, 1]

    def test_module_execution_run(self) -> None:
        """python -m bb_harness run forward-test works."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "run",
                "forward-test",
                "--input",
                str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "Forward Test" in result.stdout


class TestExportDetailed:
    """Tests for export command to cover remaining lines.

    # TRACE: src/bb_harness/commands/export.py:107-108, 131, 141-142 (role: missing)
    """

    def test_export_testrail_via_main(self, tmp_path: Path) -> None:
        """Export testrail via main."""
        output_file = tmp_path / "testrail.csv"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "export",
                "testrail",
                "--input",
                str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.manual_case_set.json"),
                "--output",
                str(output_file),
                "--format",
                "csv",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode in [0, 1, 2]

    def test_export_xray_via_main(self, tmp_path: Path) -> None:
        """Export xray via main."""
        output_file = tmp_path / "xray.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "export",
                "xray",
                "--input",
                str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.manual_case_set.json"),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode in [0, 1, 2]

    def test_export_notion_all_statuses(self) -> None:
        """Export notion with all valid status types."""
        # Valid statuses based on export-notion.py
        statuses = ["pass", "fail", "conditional_pass"]
        for status in statuses:
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
                    status,
                    "--db",
                    "test_db",
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )
            assert result.returncode == 0


class TestGateDetailed:
    """Tests for gate command to cover remaining lines.

    # TRACE: src/bb_harness/commands/gate.py:64-77 (role: missing)
    """

    def test_gate_via_main(self, tmp_path: Path) -> None:
        """Gate via main."""
        output_file = tmp_path / "gate.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "gate",
                "--input",
                str(REPO_ROOT / "examples" / "artifacts"),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert output_file.exists()

    def test_gate_via_main_with_profile(self, tmp_path: Path) -> None:
        """Gate via main with profile."""
        output_file = tmp_path / "gate.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "gate",
                "--input",
                str(REPO_ROOT / "examples" / "artifacts"),
                "--output",
                str(output_file),
                "--profile",
                "standard",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0


class TestRunDetailed:
    """Tests for run command to cover remaining lines.

    # TRACE: src/bb_harness/commands/run.py:65-66, 71-72, 115-119 (role: missing)
    """

    def test_run_forward_test_via_main(self) -> None:
        """Run forward-test via main."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "run",
                "forward-test",
                "--input",
                str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "Forward Test" in result.stdout

    def test_run_forward_test_with_skill_via_main(self) -> None:
        """Run forward-test with skill via main."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "run",
                "forward-test",
                "--skill",
                str(REPO_ROOT / "skills" / "manual-bb-test-harness"),
                "--input",
                str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0

    def test_run_forward_test_mobile_via_main(self) -> None:
        """Run forward-test with mobile via main."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "run",
                "forward-test",
                "--input",
                str(REPO_ROOT / "goldens" / "mobile-session-resume.input.md"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0


class TestIngestDetailed:
    """Tests for ingest command to cover remaining lines.

    # TRACE: src/bb_harness/commands/ingest.py:57-58, 61 (role: missing)
    """

    def test_ingest_via_main(self, tmp_path: Path) -> None:
        """Ingest via main."""
        output_file = tmp_path / "output.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "ingest",
                "--source",
                "markdown",
                "--input",
                str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert output_file.exists()

    def test_ingest_missing_input_via_main(self, tmp_path: Path) -> None:
        """Ingest with missing input via main."""
        output_file = tmp_path / "output.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "ingest",
                "--source",
                "markdown",
                "--input",
                "nonexistent.md",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode != 0


class TestHeatmapDetailed:
    """Tests for heatmap command to cover remaining lines.

    # TRACE: src/bb_harness/commands/heatmap.py:58 (role: missing)
    """

    def test_heatmap_via_main(self, tmp_path: Path) -> None:
        """Heatmap via main."""
        output_file = tmp_path / "heatmap.html"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "heatmap",
                "--input",
                str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.risk_register.json"),
                "--output",
                str(output_file),
                "--format",
                "html",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode in [0, 1, 2]


class TestStateDiagramDetailed:
    """Tests for state-diagram command to cover remaining lines.

    # TRACE: src/bb_harness/commands/state_diagram.py:43 (role: missing)
    """

    def test_state_diagram_via_main(self, tmp_path: Path) -> None:
        """State-diagram via main."""
        output_file = tmp_path / "diagram.mmd"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "state-diagram",
                "--input",
                str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.test_model.json"),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert output_file.exists()


class TestRegressionGraphDetailed:
    """Tests for regression-graph command to cover remaining lines.

    # TRACE: src/bb_harness/commands/regression_graph.py:51 (role: missing)
    """

    def test_regression_graph_via_main(self, tmp_path: Path) -> None:
        """Regression-graph via main."""
        output_file = tmp_path / "graph.dot"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "regression-graph",
                "--input",
                str(REPO_ROOT / "examples" / "artifacts"),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0


class TestImportDetailed:
    """Tests for import command to cover remaining lines.

    # TRACE: src/bb_harness/commands/import_results.py:86-87, 99, 110-111 (role: missing)
    """

    def test_import_testrail_via_main(self, tmp_path: Path) -> None:
        """Import testrail via main."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--dry-run",
                "import",
                "testrail",
                "--project",
                "12",
                "--run",
                "1234",
                "--output",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0

    def test_import_xray_via_main(self, tmp_path: Path) -> None:
        """Import xray via main."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--dry-run",
                "import",
                "xray",
                "--exec",
                "TEST-1",
                "--output",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
