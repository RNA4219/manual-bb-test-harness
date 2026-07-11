"""Tests for check_workflow_cookbook_freshness.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_module_from_path(module_name: str, file_path: Path) -> object:
    """Load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Load the module from tools/ci
REPO_ROOT = Path(__file__).parent.parent  # manual-bb-test-harness
FRESHNESS_MODULE = load_module_from_path(
    "check_workflow_cookbook_freshness",
    REPO_ROOT / "tools" / "ci" / "check_workflow_cookbook_freshness.py",
)

normalize_node_id_to_caps_name = FRESHNESS_MODULE.normalize_node_id_to_caps_name
get_short_caps_name = FRESHNESS_MODULE.get_short_caps_name
load_json = FRESHNESS_MODULE.load_json
find_caps_file = FRESHNESS_MODULE.find_caps_file
check_freshness = FRESHNESS_MODULE.check_freshness


class TestNormalizeNodeIdToCapsName:
    """Tests for normalize_node_id_to_caps_name function."""

    def test_simple_filename(self) -> None:
        """Simple filename conversion."""
        result = normalize_node_id_to_caps_name("README.md")
        assert result == "README.md.json"

    def test_nested_path(self) -> None:
        """Nested path conversion."""
        result = normalize_node_id_to_caps_name("docs/specs/spec-01.md")
        assert result == "docs.specs.spec-01.md.json"

    def test_skills_path(self) -> None:
        """Skills path conversion."""
        result = normalize_node_id_to_caps_name("skills/manual-bb-test-harness/SKILL.md")
        assert result == "skills.manual-bb-test-harness.SKILL.md.json"

    def test_goldens_path(self) -> None:
        """Goldens path conversion."""
        result = normalize_node_id_to_caps_name("goldens/order-cancel.input.md")
        assert result == "goldens.order-cancel.input.md.json"


class TestGetShortCapsName:
    """Tests for get_short_caps_name function."""

    def test_simple_filename(self) -> None:
        """Simple filename short name."""
        result = get_short_caps_name("README.md")
        assert result == "README.md.json"

    def test_nested_path(self) -> None:
        """Nested path short name (last component only)."""
        result = get_short_caps_name("skills/manual-bb-test-harness/SKILL.md")
        assert result == "SKILL.md.json"

    def test_docs_path(self) -> None:
        """Docs path short name."""
        result = get_short_caps_name("docs/evaluation-rubric.md")
        assert result == "evaluation-rubric.md.json"


class TestLoadJson:
    """Tests for load_json function."""

    def test_valid_json(self, tmp_path: Path) -> None:
        """Valid JSON file is loaded correctly."""
        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")

        result = load_json(json_file)
        assert result == {"key": "value"}

    def test_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns None."""
        result = load_json(tmp_path / "missing.json")
        assert result is None

    def test_invalid_json(self, tmp_path: Path) -> None:
        """Invalid JSON returns None."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("not valid json {", encoding="utf-8")

        result = load_json(json_file)
        assert result is None


class TestFindCapsFile:
    """Tests for find_caps_file function."""

    def test_find_full_name(self, tmp_path: Path) -> None:
        """Find caps file using full name."""
        caps_dir = tmp_path / "caps"
        caps_dir.mkdir()
        caps_file = caps_dir / "docs.specs.spec-01.md.json"
        caps_file.write_text(json.dumps({"id": "docs/specs/spec-01.md"}), encoding="utf-8")

        result = find_caps_file(caps_dir, "docs/specs/spec-01.md")
        assert result == caps_file

    def test_find_short_name(self, tmp_path: Path) -> None:
        """Find caps file using short name."""
        caps_dir = tmp_path / "caps"
        caps_dir.mkdir()
        caps_file = caps_dir / "SKILL.md.json"
        caps_file.write_text(json.dumps({"id": "skills/manual-bb-test-harness/SKILL.md"}), encoding="utf-8")

        result = find_caps_file(caps_dir, "skills/manual-bb-test-harness/SKILL.md")
        assert result == caps_file

    def test_not_found(self, tmp_path: Path) -> None:
        """Caps file not found returns None."""
        caps_dir = tmp_path / "caps"
        caps_dir.mkdir()

        result = find_caps_file(caps_dir, "missing/file.md")
        assert result is None

    def test_prefers_full_name(self, tmp_path: Path) -> None:
        """Full name is preferred when both exist."""
        caps_dir = tmp_path / "caps"
        caps_dir.mkdir()
        full_caps = caps_dir / "skills.manual-bb-test-harness.SKILL.md.json"
        short_caps = caps_dir / "SKILL.md.json"
        full_caps.write_text(json.dumps({"id": "full"}), encoding="utf-8")
        short_caps.write_text(json.dumps({"id": "short"}), encoding="utf-8")

        result = find_caps_file(caps_dir, "skills/manual-bb-test-harness/SKILL.md")
        assert result == full_caps


class TestCheckFreshness:
    """Tests for check_freshness function."""

    def test_missing_workflow_cookbook_dir(self, tmp_path: Path) -> None:
        """Missing workflow-cookbook directory returns error."""
        result = check_freshness(tmp_path)
        assert result["passed"] is False
        assert "docs/workflow-cookbook directory not found" in result["errors"]

    def test_missing_index_json(self, tmp_path: Path) -> None:
        """Missing index.json returns error."""
        workflow_dir = tmp_path / "docs" / "workflow-cookbook"
        workflow_dir.mkdir(parents=True)

        result = check_freshness(tmp_path)
        assert result["passed"] is False
        assert "index.json not found or invalid JSON" in result["errors"]

    def test_valid_repo(self) -> None:
        """Valid repo passes freshness check."""
        result = check_freshness(REPO_ROOT)
        assert result["passed"] is True
        assert len(result["missing_files"]) == 0
        assert len(result["missing_caps"]) == 0

    def test_metadata_mismatch_nodes(self, tmp_path: Path) -> None:
        """Metadata mismatch for nodes count."""
        workflow_dir = tmp_path / "docs" / "workflow-cookbook"
        workflow_dir.mkdir(parents=True)
        caps_dir = workflow_dir / "caps"
        caps_dir.mkdir()

        index_json = workflow_dir / "index.json"
        index_data = {
            "version": "1.0.0",
            "generated_at": "00001",
            "metadata": {
                "total_nodes": 10,
                "total_edges": 5,
                "total_capsules": 3,
            },
            "nodes": [
                {"id": "README.md", "path": "./README.md", "role": "overview", "title": "README"},
            ],
            "edges": [],
        }
        index_json.write_text(json.dumps(index_data), encoding="utf-8")

        # Create README.md
        readme = tmp_path / "README.md"
        readme.write_text("# README", encoding="utf-8")

        # Create caps
        caps_file = caps_dir / "README.md.json"
        caps_file.write_text(json.dumps({"id": "README.md", "last_verified": "2026-05-30"}), encoding="utf-8")

        result = check_freshness(tmp_path)
        assert result["passed"] is False
        assert "total_nodes: metadata=10, actual=1" in result["metadata_mismatch"]

    def test_missing_file_for_node(self, tmp_path: Path) -> None:
        """Missing file for node is detected."""
        workflow_dir = tmp_path / "docs" / "workflow-cookbook"
        workflow_dir.mkdir(parents=True)
        caps_dir = workflow_dir / "caps"
        caps_dir.mkdir()

        index_json = workflow_dir / "index.json"
        index_data = {
            "version": "1.0.0",
            "generated_at": "00001",
            "metadata": {
                "total_nodes": 1,
                "total_edges": 0,
                "total_capsules": 1,
            },
            "nodes": [
                {"id": "MISSING.md", "path": "./MISSING.md", "role": "overview", "title": "Missing"},
            ],
            "edges": [],
        }
        index_json.write_text(json.dumps(index_data), encoding="utf-8")

        result = check_freshness(tmp_path)
        assert result["passed"] is False
        assert "MISSING.md" in result["missing_files"]

    def test_missing_caps_for_node(self, tmp_path: Path) -> None:
        """Missing caps file for node is detected."""
        workflow_dir = tmp_path / "docs" / "workflow-cookbook"
        workflow_dir.mkdir(parents=True)
        caps_dir = workflow_dir / "caps"
        caps_dir.mkdir()

        index_json = workflow_dir / "index.json"
        index_data = {
            "version": "1.0.0",
            "generated_at": "00001",
            "metadata": {
                "total_nodes": 1,
                "total_edges": 0,
                "total_capsules": 0,
            },
            "nodes": [
                {"id": "README.md", "path": "./README.md", "role": "overview", "title": "README"},
            ],
            "edges": [],
        }
        index_json.write_text(json.dumps(index_data), encoding="utf-8")

        # Create README.md (file exists)
        readme = tmp_path / "README.md"
        readme.write_text("# README", encoding="utf-8")

        result = check_freshness(tmp_path)
        assert result["passed"] is False
        assert "README.md" in result["missing_caps"]


    def test_readme_count_mismatch_is_rejected(self, tmp_path: Path) -> None:
        """README and index counts must stay synchronized."""
        workflow_dir = tmp_path / "docs" / "workflow-cookbook"
        caps_dir = workflow_dir / "caps"
        caps_dir.mkdir(parents=True)
        (tmp_path / "README.md").write_text(
            "index.json (2 nodes, 0 edges)", encoding="utf-8"
        )
        index = {
            "generated_at": "2026-07-11T00:00:00+09:00",
            "metadata": {
                "last_updated": "2026-07-11",
                "total_nodes": 1,
                "total_edges": 0,
                "total_capsules": 1,
            },
            "nodes": [{"id": "README.md", "path": "./README.md"}],
            "edges": [],
        }
        (workflow_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
        hot = {
            "generated_at": "2026-07-11T00:00:00+09:00",
            "project_status": {"last_updated": "2026-07-11", "total_capsules": 1},
            "hot_nodes": [{"id": "README.md", "path": "./README.md"}],
        }
        (workflow_dir / "hot.json").write_text(json.dumps(hot), encoding="utf-8")
        (caps_dir / "README.md.json").write_text(
            json.dumps({"last_verified": "2999-01-01"}), encoding="utf-8"
        )

        result = check_freshness(tmp_path)

        assert result["passed"] is False
        assert any("README counts" in issue for issue in result["metadata_mismatch"])

    def test_missing_hot_node_path_is_rejected(self, tmp_path: Path) -> None:
        """A hot node must be indexed and resolve to an existing file."""
        workflow_dir = tmp_path / "docs" / "workflow-cookbook"
        caps_dir = workflow_dir / "caps"
        caps_dir.mkdir(parents=True)
        (tmp_path / "README.md").write_text(
            "index.json (1 nodes, 0 edges)", encoding="utf-8"
        )
        index = {
            "generated_at": "2026-07-11T00:00:00+09:00",
            "metadata": {
                "last_updated": "2026-07-11",
                "total_nodes": 1,
                "total_edges": 0,
                "total_capsules": 1,
            },
            "nodes": [{"id": "README.md", "path": "./README.md"}],
            "edges": [],
        }
        (workflow_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
        hot = {
            "generated_at": "2026-07-11T00:00:00+09:00",
            "project_status": {"last_updated": "2026-07-11", "total_capsules": 1},
            "hot_nodes": [{"id": "missing.md", "path": "./missing.md"}],
        }
        (workflow_dir / "hot.json").write_text(json.dumps(hot), encoding="utf-8")
        (caps_dir / "README.md.json").write_text(
            json.dumps({"last_verified": "2999-01-01"}), encoding="utf-8"
        )

        result = check_freshness(tmp_path)

        assert result["passed"] is False
        assert "hot node not in index: missing.md" in result["hot_node_issues"]
        assert "hot node path missing: ./missing.md" in result["hot_node_issues"]

class TestCliIntegration:
    """Integration tests for CLI."""

    def test_cli_pass_on_valid_repo(self) -> None:
        """CLI passes on valid repo."""
        import subprocess

        result = subprocess.run(
            [sys.executable, "tools/ci/check_workflow_cookbook_freshness.py", "--repo", str(REPO_ROOT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "[PASS]" in result.stdout

    def test_cli_json_output(self) -> None:
        """CLI JSON output works."""
        import subprocess

        result = subprocess.run(
            [sys.executable, "tools/ci/check_workflow_cookbook_freshness.py", "--repo", str(REPO_ROOT), "--json"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["passed"] is True

    def test_cli_strict_mode(self) -> None:
        """CLI strict mode."""
        import subprocess

        result = subprocess.run(
            [sys.executable, "tools/ci/check_workflow_cookbook_freshness.py", "--repo", str(REPO_ROOT), "--strict"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        # Should pass since no stale caps (files not modified after last_verified)
        assert result.returncode == 0

    def test_hot_test_count_mismatch_is_rejected(self, tmp_path: Path) -> None:
        """README test count and hot.json test_count must stay synchronized."""
        workflow_dir = tmp_path / "docs" / "workflow-cookbook"
        caps_dir = workflow_dir / "caps"
        caps_dir.mkdir(parents=True)
        (tmp_path / "README.md").write_text(
            "index.json (1 nodes, 0 edges)\n現行リリース系列: **2.0.0** / 検証済みテスト: **1件**",
            encoding="utf-8",
        )
        index = {
            "generated_at": "2026-07-11T00:00:00+09:00",
            "metadata": {
                "last_updated": "2026-07-11",
                "total_nodes": 1,
                "total_edges": 0,
                "total_capsules": 1,
            },
            "nodes": [{"id": "README.md", "path": "./README.md"}],
            "edges": [],
        }
        (workflow_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
        hot = {
            "generated_at": "2026-07-11T00:00:00+09:00",
            "project_status": {
                "last_updated": "2026-07-11",
                "total_capsules": 1,
                "test_count": 2,
            },
            "hot_nodes": [{"id": "README.md", "path": "./README.md"}],
        }
        (workflow_dir / "hot.json").write_text(json.dumps(hot), encoding="utf-8")
        (caps_dir / "README.md.json").write_text(
            json.dumps({"last_verified": "2999-01-01"}), encoding="utf-8"
        )

        result = check_freshness(tmp_path)

        assert result["passed"] is False
        assert any("test_count mismatch" in issue for issue in result["metadata_mismatch"])
