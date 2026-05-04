"""Unit tests for regression-graph.py."""

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
    "regression_graph",
    Path(__file__).parent.parent / "scripts" / "regression-graph.py"
)
regression_graph = importlib.util.module_from_spec(spec)
sys.modules["regression_graph"] = regression_graph
spec.loader.exec_module(regression_graph)

load_json_file = regression_graph.load_json_file
parse_feature_specs = regression_graph.parse_feature_specs
build_area_feature_map = regression_graph.build_area_feature_map
build_regression_edges = regression_graph.build_regression_edges
deduplicate_edges = regression_graph.deduplicate_edges
generate_dot = regression_graph.generate_dot
generate_d3_json = regression_graph.generate_d3_json
generate_html_wrapper = regression_graph.generate_html_wrapper
expand_input_paths = regression_graph.expand_input_paths
main = regression_graph.main


class TestLoadJsonFile:
    """Tests for JSON loading."""

    def test_valid_json(self, tmp_path: Path) -> None:
        file = tmp_path / "test.json"
        file.write_text('{"key": "value"}', encoding="utf-8")
        result = load_json_file(file)
        assert result["key"] == "value"

    def test_invalid_json(self, tmp_path: Path) -> None:
        file = tmp_path / "test.json"
        file.write_text("{invalid}", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_json_file(file)

    def test_missing_file(self, tmp_path: Path) -> None:
        file = tmp_path / "nonexistent.json"
        with pytest.raises(ValueError, match="Cannot read"):
            load_json_file(file)


class TestParseFeatureSpecs:
    """Tests for feature spec parsing."""

    def test_single_spec(self, tmp_path: Path) -> None:
        file = tmp_path / "test.feature_spec.json"
        file.write_text(
            json.dumps({"feature_id": "TEST-01", "title": "Test"}),
            encoding="utf-8"
        )
        result = parse_feature_specs([file])
        assert "TEST-01" in result
        assert result["TEST-01"]["title"] == "Test"

    def test_multiple_specs(self, tmp_path: Path) -> None:
        files = []
        for i in range(3):
            f = tmp_path / f"spec{i}.feature_spec.json"
            f.write_text(
                json.dumps({"feature_id": f"TEST-{i}", "title": f"Test {i}"}),
                encoding="utf-8"
            )
            files.append(f)
        result = parse_feature_specs(files)
        assert len(result) == 3


class TestBuildAreaFeatureMap:
    """Tests for area-feature mapping."""

    def test_basic_mapping(self) -> None:
        features = {
            "F1": {"changed_areas": ["service_a", "service_b"]},
            "F2": {"changed_areas": ["service_a", "service_c"]},
        }
        result = build_area_feature_map(features)
        assert "service_a" in result
        assert "F1" in result["service_a"]
        assert "F2" in result["service_a"]

    def test_empty_areas(self) -> None:
        features = {"F1": {"changed_areas": []}}
        result = build_area_feature_map(features)
        assert result == {}


class TestBuildRegressionEdges:
    """Tests for edge building."""

    def test_shared_area_edges(self) -> None:
        features = {
            "F1": {"changed_areas": ["service_x"]},
            "F2": {"changed_areas": ["service_x"]},
        }
        edges = build_regression_edges(features, {})
        assert len(edges) == 1
        assert edges[0]["type"] == "shared_area"
        assert edges[0]["area"] == "service_x"

    def test_regression_edges_from_test_model(self) -> None:
        features = {
            "F1": {"changed_areas": ["order_service"]},
            "F2": {"changed_areas": []},
        }
        test_models = {
            "F2": {"regression_edges": ["direct:order_service"]},
        }
        edges = build_regression_edges(features, test_models)
        assert any(e["source"] == "F2" and e["target"] == "F1" for e in edges)

    def test_no_edges(self) -> None:
        features = {
            "F1": {"changed_areas": ["a"]},
            "F2": {"changed_areas": ["b"]},
        }
        edges = build_regression_edges(features, {})
        assert edges == []


class TestDeduplicateEdges:
    """Tests for edge deduplication."""

    def test_removes_duplicates(self) -> None:
        edges = [
            {"source": "A", "target": "B"},
            {"source": "A", "target": "B"},
            {"source": "B", "target": "A"},  # Reverse duplicate
        ]
        result = deduplicate_edges(edges)
        assert len(result) == 1

    def test_keeps_unique(self) -> None:
        edges = [
            {"source": "A", "target": "B"},
            {"source": "A", "target": "C"},
        ]
        result = deduplicate_edges(edges)
        assert len(result) == 2


class TestGenerateDot:
    """Tests for DOT output."""

    def test_basic_dot(self) -> None:
        features = {"F1": {"title": "Feature 1"}}
        edges = [{"source": "F1", "target": "F2", "type": "shared_area"}]
        result = generate_dot(features, edges)
        assert "digraph" in result
        assert "F1" in result
        assert "->" in result

    def test_node_labels(self) -> None:
        features = {"F1": {"title": "Test Feature"}}
        result = generate_dot(features, [])
        assert "Test Feature" in result


class TestGenerateD3Json:
    """Tests for D3 JSON output."""

    def test_nodes_and_links(self) -> None:
        features = {"F1": {"title": "Feature"}}
        edges = [{"source": "F1", "target": "F2", "type": "dependency"}]
        result = generate_d3_json(features, edges)
        assert "nodes" in result
        assert "links" in result
        assert len(result["nodes"]) == 1


class TestGenerateHtmlWrapper:
    """Tests for HTML output."""

    def test_html_structure(self) -> None:
        d3_data = {"nodes": [], "links": []}
        result = generate_html_wrapper(d3_data)
        assert "<!DOCTYPE html>" in result
        assert "d3js.org" in result
        assert "<svg" in result


class TestExpandInputPaths:
    """Tests for input path expansion."""

    def test_directory_expansion(self, tmp_path: Path) -> None:
        (tmp_path / "test.feature_spec.json").write_text('{}', encoding="utf-8")
        (tmp_path / "test.test_model.json").write_text('{}', encoding="utf-8")
        (tmp_path / "other.json").write_text('{}', encoding="utf-8")

        specs, models = expand_input_paths(tmp_path)
        assert len(specs) == 1
        assert len(models) == 1

    def test_single_file(self, tmp_path: Path) -> None:
        file = tmp_path / "test.feature_spec.json"
        file.write_text('{}', encoding="utf-8")
        specs, models = expand_input_paths(file)
        assert len(specs) == 1


class TestMain:
    """Tests for main() entry point."""

    def test_version(self) -> None:
        with mock.patch.object(sys, "argv", ["script", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_dot_output(self, tmp_path: Path) -> None:
        # Create test files
        spec_file = tmp_path / "test.feature_spec.json"
        spec_file.write_text(
            json.dumps({"feature_id": "TEST-01", "title": "Test", "changed_areas": []}),
            encoding="utf-8"
        )
        output_file = tmp_path / "output.dot"

        with mock.patch.object(sys, "argv", [
            "script",
            "--input", str(tmp_path),
            "--format", "dot",
            "--output", str(output_file),
        ]):
            assert main() == 0
            assert output_file.exists()
            content = output_file.read_text(encoding="utf-8")
            assert "digraph" in content

    def test_html_output(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "test.feature_spec.json"
        spec_file.write_text(
            json.dumps({"feature_id": "TEST-01", "title": "Test"}),
            encoding="utf-8"
        )
        output_file = tmp_path / "output.html"

        with mock.patch.object(sys, "argv", [
            "script",
            "--input", str(tmp_path),
            "--format", "html",
            "--output", str(output_file),
        ]):
            assert main() == 0
            assert output_file.exists()
            content = output_file.read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content

    def test_no_files_found(self, tmp_path: Path) -> None:
        # Directory with no matching files
        (tmp_path / "other.txt").write_text("", encoding="utf-8")
        output_file = tmp_path / "output.dot"

        with mock.patch.object(sys, "argv", [
            "script",
            "--input", str(tmp_path),
            "--format", "dot",
            "--output", str(output_file),
        ]):
            assert main() == 1