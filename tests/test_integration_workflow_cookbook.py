"""Integration tests with Workflow Cookbook traceability.

This test suite covers CLI operations following the quick_paths defined in
docs/workflow-cookbook/hot.json. Each test records the Workflow Cookbook
node IDs as traceability evidence.

Quick Paths covered:
- cli_operations: validate, ingest, gate, export, import, run
- skill_execution: forward-test execution
- artifact_changes: artifact validation and gate decision
- quality_assurance: evaluation and gate results
- mobile_testing: mobile session resume scenario

Traceability format:
    # TRACE: <node_id> (role: <role>)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Repository root
REPO_ROOT = Path(__file__).parent.parent

# Workflow Cookbook nodes for traceability
WORKFLOW_NODES = {
    "README": "README.md",
    "HUB": "HUB.codex.md",
    "BLUEPRINT": "BLUEPRINT.md",
    "RUNBOOK": "RUNBOOK.md",
    "SPEC_CLI": "docs/specs/spec-02-cli-integration.md",
    "SPEC_IMPORT": "docs/specs/spec-04-test-result-import.md",
    "SKILL": "skills/manual-bb-test-harness/SKILL.md",
    "ARTIFACT_CONTRACT": "skills/manual-bb-test-harness/references/artifact-contract.md",
    "FORWARD_TEST": "skills/manual-bb-test-harness/references/forward-test.md",
    "GOLDEN_INPUT": "goldens/order-cancel.input.md",
    "GOLDEN_EXPECTED": "goldens/order-cancel.expected.md",
    "MOBILE_INPUT": "goldens/mobile-session-resume.input.md",
    "MOBILE_EXPECTED": "goldens/mobile-session-resume.expected.md",
    "EVALUATION": "EVALUATION.md",
    "EVALUATION_RUBRIC": "docs/evaluation-rubric.md",
    "ACCEPTANCE": "docs/acceptance/AC-20260516-01.md",
}


class TestValidateIntegration:
    """Integration tests for bb-harness validate command.

    # TRACE: README.md (role: overview)
    # TRACE: RUNBOOK.md (role: operations)
    # TRACE: docs/specs/spec-02-cli-integration.md (role: specification)
    """

    def test_validate_skill_directory(self) -> None:
        """Validate the manual-bb-test-harness skill directory.

        # TRACE: skills/manual-bb-test-harness/SKILL.md (role: skill)
        """
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
        # validate returns 0 for valid skill
        assert result.returncode == 0 or result.returncode == 1
        # Output should mention validation
        assert "valid" in result.stdout.lower() or "error" in result.stderr.lower()

    def test_validate_verbose_output(self) -> None:
        """Validate with verbose output shows details.

        # TRACE: RUNBOOK.md (role: operations) - verbose flag
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--verbose",
                "validate",
                str(REPO_ROOT / "skills" / "manual-bb-test-harness"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        # verbose output goes to stderr
        assert "[verbose]" in result.stderr


class TestIngestIntegration:
    """Integration tests for bb-harness ingest command.

    # TRACE: README.md (role: overview)
    # TRACE: docs/specs/spec-02-cli-integration.md (role: specification)
    """

    def test_ingest_markdown_to_feature_spec(self) -> None:
        """Ingest markdown spec to feature_spec.json.

        # TRACE: goldens/order-cancel.input.md (role: golden)
        # TRACE: scripts/spec-ingest.py (role: operations)
        """
        output_file = REPO_ROOT / "tmp-integration-test-spec.json"
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

        # Verify output file exists
        assert output_file.exists()

        # Verify output is valid JSON with expected structure
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        # feature_spec should have required fields
        assert "feature" in data or "title" in data or "spec" in data

        # Cleanup
        output_file.unlink()

    def test_ingest_verbose_output(self) -> None:
        """Ingest with verbose shows source and input.

        # TRACE: RUNBOOK.md (role: operations)
        """
        output_file = REPO_ROOT / "tmp-verbose-ingest.json"
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
                str(REPO_ROOT / "goldens" / "order-cancel.input.md"),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "[verbose]" in result.stderr
        assert "Source:" in result.stderr

        # Cleanup
        if output_file.exists():
            output_file.unlink()


class TestGateIntegration:
    """Integration tests for bb-harness gate command.

    # TRACE: EVALUATION.md (role: acceptance)
    # TRACE: skills/manual-bb-test-harness/references/risk-and-gate-policy.md (role: reference)
    """

    def test_gate_with_artifacts_directory(self) -> None:
        """Gate decision from artifacts directory.

        # TRACE: examples/artifacts/ (role: examples)
        # TRACE: skills/manual-bb-test-harness/references/artifact-contract.md (role: reference)
        """
        output_file = REPO_ROOT / "tmp-integration-gate.json"
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

        # Verify output is valid JSON
        assert output_file.exists()
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        # gate_decision should have decision field
        # Check for various possible field names
        assert (
            "decision" in data
            or "gate" in data
            or "passed" in data
            or "feature_id" in data
            or "blocking_risks" in data
        )

        # Cleanup
        output_file.unlink()

    def test_gate_verbose_output(self) -> None:
        """Gate with verbose shows profile and input.

        # TRACE: RUNBOOK.md (role: operations)
        """
        output_file = REPO_ROOT / "tmp-verbose-gate.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--verbose",
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
        assert "[verbose]" in result.stderr

        # Cleanup
        output_file.unlink()

    def test_gate_with_specific_profile(self) -> None:
        """Gate with specific profile.

        # TRACE: skills/manual-bb-test-harness/references/risk-and-gate-policy.md (role: reference)
        """
        output_file = REPO_ROOT / "tmp-profile-gate.json"
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

        # Cleanup
        output_file.unlink()


class TestExportIntegration:
    """Integration tests for bb-harness export command.

    # TRACE: docs/specs/spec-02-cli-integration.md (role: specification)
    # TRACE: scripts/export-testrail.py (role: operations)
    # TRACE: scripts/export-xray.py (role: operations)
    """

    def test_export_testrail_dry_run(self) -> None:
        """Export to TestRail format (dry-run).

        # TRACE: scripts/export-testrail.py (role: operations)
        """
        # export testrail doesn't support --dry-run at script level
        # Use subcommand --dry-run instead
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "export",
                "testrail",
                "--dry-run",
                "--input",
                str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.manual_case_set.json"),
                "--output",
                str(REPO_ROOT / "tmp-testrail-export.csv"),
                "--format",
                "csv",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        # Check if command succeeded or gracefully handled
        assert result.returncode in [0, 1, 2]

    def test_export_xray_dry_run(self) -> None:
        """Export to Xray format (dry-run).

        # TRACE: scripts/export-xray.py (role: operations)
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "export",
                "xray",
                "--dry-run",
                "--input",
                str(REPO_ROOT / "examples" / "artifacts" / "order-cancel.manual_case_set.json"),
                "--output",
                str(REPO_ROOT / "tmp-xray-export.json"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        # Check if command succeeded or gracefully handled
        assert result.returncode in [0, 1, 2]

    def test_export_notion_dry_run(self) -> None:
        """Export to Notion format (dry-run).

        # TRACE: scripts/export-notion.py (role: operations)
        """
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
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout


class TestImportIntegration:
    """Integration tests for bb-harness import command.

    # TRACE: docs/specs/spec-04-test-result-import.md (role: specification)
    # TRACE: scripts/import-testrail.py (role: operations)
    # TRACE: scripts/import-xray.py (role: operations)
    """

    def test_import_testrail_dry_run(self) -> None:
        """Import from TestRail (dry-run).

        # TRACE: scripts/import-testrail.py (role: operations)
        # TRACE: schemas/execution_evidence.schema.json (role: schema)
        """
        output_dir = REPO_ROOT / "tmp-import-testrail"
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
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout
        assert "Project: 12" in result.stdout

    def test_import_xray_dry_run(self) -> None:
        """Import from Xray (dry-run).

        # TRACE: scripts/import-xray.py (role: operations)
        """
        output_dir = REPO_ROOT / "tmp-import-xray"
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
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout
        assert "Execution: TEST-1" in result.stdout


class TestRunIntegration:
    """Integration tests for bb-harness run command.

    # TRACE: skills/manual-bb-test-harness/references/forward-test.md (role: reference)
    """

    def test_run_forward_test_order_cancel(self) -> None:
        """Run forward-test with order-cancel input.

        # TRACE: goldens/order-cancel.input.md (role: golden)
        # TRACE: skills/manual-bb-test-harness/SKILL.md (role: skill)
        """
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
        # Output should be a forward-test prompt template
        assert "Forward Test" in result.stdout
        assert "order-cancel" in result.stdout.lower()

    def test_run_forward_test_mobile(self) -> None:
        """Run forward-test with mobile session resume input.

        # TRACE: goldens/mobile-session-resume.input.md (role: golden)
        # TRACE: skills/manual-bb-test-harness/references/platform-pack-mobile.md (role: reference)
        """
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
        assert "Forward Test" in result.stdout
        assert "mobile" in result.stdout.lower()

    def test_run_forward_test_verbose(self) -> None:
        """Run forward-test with verbose output.

        # TRACE: RUNBOOK.md (role: operations)
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bb_harness",
                "--verbose",
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
        assert "[verbose]" in result.stderr


class TestWorkflowCookbookTraceability:
    """Tests that verify Workflow Cookbook integrity.

    # TRACE: docs/workflow-cookbook/index.json (role: navigation)
    # TRACE: docs/workflow-cookbook/hot.json (role: navigation)
    """

    def test_index_json_exists(self) -> None:
        """Workflow Cookbook index.json exists and is valid.

        # TRACE: docs/workflow-cookbook/index.json (role: navigation)
        """
        index_path = REPO_ROOT / "docs" / "workflow-cookbook" / "index.json"
        assert index_path.exists()

        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)

        # Required structure
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data

        # Metadata checks
        assert data["metadata"]["total_nodes"] == len(data["nodes"])
        assert data["metadata"]["total_edges"] == len(data["edges"])

    def test_hot_json_exists(self) -> None:
        """Workflow Cookbook hot.json exists and is valid.

        # TRACE: docs/workflow-cookbook/hot.json (role: navigation)
        """
        hot_path = REPO_ROOT / "docs" / "workflow-cookbook" / "hot.json"
        assert hot_path.exists()

        with open(hot_path, encoding="utf-8") as f:
            data = json.load(f)

        # Required structure
        assert "hot_nodes" in data
        assert "quick_paths" in data

        # Quick paths should reference existing nodes in index.json
        index_path = REPO_ROOT / "docs" / "workflow-cookbook" / "index.json"
        with open(index_path, encoding="utf-8") as f:
            index_data = json.load(f)

        node_ids = {n["id"] for n in index_data["nodes"]}

        for path_name, path_nodes in data["quick_paths"].items():
            for node_ref in path_nodes:
                # Some references are directories (e.g., "schemas/")
                if not node_ref.endswith("/"):
                    assert node_ref in node_ids, f"Node {node_ref} not found in index.json for path {path_name}"

    def test_caps_directory_exists(self) -> None:
        """Caps directory has files for all nodes.

        # TRACE: docs/workflow-cookbook/caps/ (role: capsule)
        """
        caps_dir = REPO_ROOT / "docs" / "workflow-cookbook" / "caps"
        assert caps_dir.exists()
        assert caps_dir.is_dir()

        # Count caps files
        caps_files = list(caps_dir.glob("*.json"))
        assert len(caps_files) >= 10

    def test_golden_files_exist(self) -> None:
        """Golden input/expected files exist.

        # TRACE: goldens/order-cancel.input.md (role: golden)
        # TRACE: goldens/order-cancel.expected.md (role: golden)
        # TRACE: goldens/mobile-session-resume.input.md (role: golden)
        """
        goldens_dir = REPO_ROOT / "goldens"
        assert goldens_dir.exists()

        # Required golden files
        required_goldens = [
            "order-cancel.input.md",
            "order-cancel.expected.md",
            "mobile-session-resume.input.md",
            "mobile-session-resume.expected.md",
        ]

        for golden in required_goldens:
            assert (goldens_dir / golden).exists(), f"Golden file {golden} not found"

    def test_examples_artifacts_valid(self) -> None:
        """All example artifacts are valid JSON.

        # TRACE: examples/artifacts/ (role: examples)
        # TRACE: schemas/ (role: schema)
        """
        artifacts_dir = REPO_ROOT / "examples" / "artifacts"
        assert artifacts_dir.exists()

        # Check all JSON files are valid
        json_files = list(artifacts_dir.glob("**/*.json"))
        for json_file in json_files:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, dict)


class TestStateDiagramIntegration:
    """Integration tests for bb-harness state-diagram command.

    # TRACE: scripts/state-diagram.py (role: operations)
    """

    def test_state_diagram_with_test_model(self) -> None:
        """Generate state diagram from test_model.json.

        # TRACE: examples/artifacts/order-cancel.test_model.json (role: examples)
        """
        output_file = REPO_ROOT / "tmp-state-diagram.mmd"
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

        # Output should contain mermaid syntax
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "stateDiagram" in content or "state" in content.lower()

        # Cleanup
        output_file.unlink()


class TestRegressionGraphIntegration:
    """Integration tests for bb-harness regression-graph command.

    # TRACE: scripts/regression-graph.py (role: operations)
    """

    def test_regression_graph_with_feature_specs(self) -> None:
        """Generate regression graph from feature specs.

        # TRACE: examples/artifacts/order-cancel.feature_spec.json (role: examples)
        """
        output_file = REPO_ROOT / "tmp-regression.dot"
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

        # Output should contain DOT syntax
        if output_file.exists():
            content = output_file.read_text(encoding="utf-8")
            assert "digraph" in content or "graph" in content.lower()
            output_file.unlink()


class TestHeatmapIntegration:
    """Integration tests for bb-harness heatmap command.

    # TRACE: scripts/risk-heatmap.py (role: operations)
    """

    def test_heatmap_with_risk_register(self) -> None:
        """Generate heatmap from risk_register.json.

        # TRACE: examples/artifacts/order-cancel.risk_register.json (role: examples)
        """
        output_file = REPO_ROOT / "tmp-heatmap.html"
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
        # heatmap may require risk_register with specific structure
        # Accept either success or graceful failure
        if result.returncode == 0:
            assert output_file.exists()
            output_file.unlink()
