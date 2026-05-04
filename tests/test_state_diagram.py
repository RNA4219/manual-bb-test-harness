"""Unit tests for state-diagram.py."""

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
    "state_diagram",
    Path(__file__).parent.parent / "scripts" / "state-diagram.py"
)
state_diagram = importlib.util.module_from_spec(spec)
sys.modules["state_diagram"] = state_diagram
spec.loader.exec_module(state_diagram)

load_test_model = state_diagram.load_test_model
extract_states = state_diagram.extract_states
extract_transitions = state_diagram.extract_transitions
parse_transition = state_diagram.parse_transition
generate_mermaid = state_diagram.generate_mermaid
main = state_diagram.main


class TestLoadTestModel:
    """Tests for load_test_model."""

    def test_valid_json(self, tmp_path: Path) -> None:
        data = {"states": ["a", "b"], "valid_transitions": ["a -> b"]}
        file = tmp_path / "test.test_model.json"
        file.write_text(json.dumps(data), encoding="utf-8")
        result = load_test_model(file)
        assert result == data

    def test_invalid_json(self, tmp_path: Path) -> None:
        file = tmp_path / "test.test_model.json"
        file.write_text("{invalid}", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_test_model(file)

    def test_missing_file(self, tmp_path: Path) -> None:
        file = tmp_path / "nonexistent.json"
        with pytest.raises(ValueError, match="Cannot read"):
            load_test_model(file)


class TestExtractStates:
    """Tests for extract_states."""

    def test_explicit_states(self) -> None:
        model = {"states": ["pending", "shipped", "cancelled"]}
        result = extract_states(model)
        assert result == ["pending", "shipped", "cancelled"]

    def test_infer_from_transitions(self) -> None:
        model = {"valid_transitions": ["a -> b", "b -> c"]}
        result = extract_states(model)
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_empty_model(self) -> None:
        model = {}
        result = extract_states(model)
        assert result == []


class TestExtractTransitions:
    """Tests for extract_transitions."""

    def test_both_present(self) -> None:
        model = {
            "valid_transitions": ["a -> b"],
            "invalid_transitions": ["b -> c"],
        }
        valid, invalid = extract_transitions(model)
        assert valid == ["a -> b"]
        assert invalid == ["b -> c"]

    def test_missing_invalid(self) -> None:
        model = {"valid_transitions": ["a -> b"]}
        valid, invalid = extract_transitions(model)
        assert valid == ["a -> b"]
        assert invalid == []


class TestParseTransition:
    """Tests for parse_transition."""

    def test_simple(self) -> None:
        from_state, to_state = parse_transition("a -> b")
        assert from_state == "a"
        assert to_state == "b"

    def test_with_spaces(self) -> None:
        from_state, to_state = parse_transition("  pending  ->  cancelled  ")
        assert from_state == "pending"
        assert to_state == "cancelled"

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid transition"):
            parse_transition("a b")

    def test_double_arrow(self) -> None:
        with pytest.raises(ValueError, match="Invalid transition"):
            parse_transition("a -> b -> c")


class TestGenerateMermaid:
    """Tests for generate_mermaid."""

    def test_basic(self) -> None:
        states = ["pending", "cancelled"]
        valid = ["pending -> cancelled"]
        invalid = []
        result = generate_mermaid(states, valid, invalid)
        assert "stateDiagram-v2" in result
        assert "[*] --> pending" in result
        assert "pending --> cancelled" in result

    def test_with_invalid_transitions(self) -> None:
        states = ["pending", "shipped", "cancelled"]
        valid = ["pending -> cancelled"]
        invalid = ["shipped -> cancelled"]
        result = generate_mermaid(states, valid, invalid)
        assert "shipped -.-> cancelled: invalid" in result

    def test_with_flows(self) -> None:
        states = ["pending", "cancelled"]
        valid = ["pending -> cancelled"]
        invalid = []
        flows = ["buyer cancellation", "cs delegated"]
        result = generate_mermaid(states, valid, invalid, flows)
        assert "Flow 1: buyer cancellation" in result
        assert "Flow 2: cs delegated" in result

    def test_no_transitions(self) -> None:
        states = ["a", "b"]
        valid = []
        invalid = []
        result = generate_mermaid(states, valid, invalid)
        assert "stateDiagram-v2" in result
        assert "[*]" not in result


class TestMain:
    """Tests for main() entry point."""

    def test_version(self) -> None:
        with mock.patch.object(sys, "argv", ["script", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_generate_output(self, tmp_path: Path) -> None:
        # Create input
        input_file = tmp_path / "test.test_model.json"
        input_file.write_text(
            json.dumps({
                "states": ["pending", "cancelled"],
                "valid_transitions": ["pending -> cancelled"],
            }),
            encoding="utf-8"
        )
        output_file = tmp_path / "output.mmd"

        with mock.patch.object(sys, "argv", [
            "script",
            "--input", str(input_file),
            "--output", str(output_file),
        ]):
            assert main() == 0
            assert output_file.exists()
            content = output_file.read_text(encoding="utf-8")
            assert "stateDiagram-v2" in content

    def test_invalid_input(self, tmp_path: Path) -> None:
        input_file = tmp_path / "bad.json"
        input_file.write_text("{invalid}", encoding="utf-8")
        output_file = tmp_path / "out.mmd"

        with mock.patch.object(sys, "argv", [
            "script",
            "--input", str(input_file),
            "--output", str(output_file),
        ]):
            assert main() == 1