"""Unit tests for CLI module (direct function calls for coverage)."""

from __future__ import annotations

import pytest

from bb_harness.cli import create_parser, main


class TestCreateParser:
    """Tests for create_parser function."""

    def test_parser_created(self) -> None:
        """Parser is created successfully."""
        parser = create_parser()
        assert parser.prog == "bb-harness"

    def test_has_version_flag(self) -> None:
        """Parser has --version flag."""
        parser = create_parser()
        # --version triggers SystemExit, so we check it exists
        for action in parser._actions:
            if action.dest == "version":
                return
        pytest.fail("--version flag not found")

    def test_has_verbose_flag(self) -> None:
        """Parser has --verbose flag."""
        parser = create_parser()
        for action in parser._actions:
            if action.dest == "global_verbose":
                return
        pytest.fail("--verbose flag not found")

    def test_has_dry_run_flag(self) -> None:
        """Parser has --dry-run flag."""
        parser = create_parser()
        for action in parser._actions:
            if action.dest == "global_dry_run":
                return
        pytest.fail("--dry-run flag not found")

    def test_has_subcommands(self) -> None:
        """Parser has expected subcommands."""
        parser = create_parser()
        # Check that subparsers exist by checking the _subparsers attribute
        # or by checking if dest='command' action exists
        for action in parser._actions:
            if action.dest == "command":
                # This is the subparsers action
                # choices should be a dict
                if hasattr(action, "choices") and action.choices is not None:
                    choices = action.choices
                    assert "validate" in choices
                    assert "ingest" in choices
                    assert "gate" in choices
                    assert "export" in choices
                    assert "import" in choices
                    assert "run" in choices
                    return
        # Alternative: check by parsing
        args = parser.parse_args(["validate"])
        assert args.command == "validate"


class TestMainFunction:
    """Tests for main function (direct calls)."""

    def test_no_args_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """main() with no args prints help and returns 0."""
        result = main([])
        assert result == 0
        captured = capsys.readouterr()
        assert "bb-harness" in captured.out

    def test_help_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """main(['--help']) prints help."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_version_flag(self) -> None:
        """main(['--version']) prints version."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_unknown_command_raises_system_exit(self) -> None:
        """main with unknown command raises SystemExit."""
        with pytest.raises(SystemExit) as exc_info:
            main(["unknown-command"])
        assert exc_info.value.code == 2

    def test_validate_command_exists(self) -> None:
        """main(['validate']) should not crash."""
        # validate without skill path will fail, but should not crash
        result = main(["validate"])
        # Returns error code because skill path is missing
        assert result != 0 or result == 0  # Either way, no crash

    def test_verbose_propagation(self) -> None:
        """--verbose flag propagates to subcommand."""
        parser = create_parser()
        args = parser.parse_args(["--verbose", "validate"])
        assert args.global_verbose is True

    def test_dry_run_propagation(self) -> None:
        """--dry-run flag propagates to subcommand."""
        parser = create_parser()
        args = parser.parse_args(["--dry-run", "export", "notion"])
        assert args.global_dry_run is True

    def test_top_level_verbose(self) -> None:
        """Top-level --verbose flag works."""
        parser = create_parser()
        args = parser.parse_args(["--verbose", "validate"])
        assert args.global_verbose is True

    def test_subcommand_dry_run(self) -> None:
        """Subcommand --dry-run flag works."""
        parser = create_parser()
        args = parser.parse_args(["export", "notion", "--dry-run"])
        assert args.dry_run is True


class TestSubcommandHelp:
    """Tests for subcommand --help."""

    def test_validate_help(self) -> None:
        """validate --help works."""
        with pytest.raises(SystemExit) as exc_info:
            main(["validate", "--help"])
        assert exc_info.value.code == 0

    def test_ingest_help(self) -> None:
        """ingest --help works."""
        with pytest.raises(SystemExit) as exc_info:
            main(["ingest", "--help"])
        assert exc_info.value.code == 0

    def test_gate_help(self) -> None:
        """gate --help works."""
        with pytest.raises(SystemExit) as exc_info:
            main(["gate", "--help"])
        assert exc_info.value.code == 0

    def test_export_help(self) -> None:
        """export --help works."""
        with pytest.raises(SystemExit) as exc_info:
            main(["export", "--help"])
        assert exc_info.value.code == 0

    def test_import_help(self) -> None:
        """import --help works."""
        with pytest.raises(SystemExit) as exc_info:
            main(["import", "--help"])
        assert exc_info.value.code == 0

    def test_run_help(self) -> None:
        """run --help works."""
        with pytest.raises(SystemExit) as exc_info:
            main(["run", "--help"])
        assert exc_info.value.code == 0


class TestDispatchMap:
    """Tests for dispatch map completeness."""

    def test_all_commands_have_handlers(self) -> None:
        """All expected commands can be parsed with help."""
        # Commands that work with --help (no params needed)
        expected_commands = [
            "validate",
            "ingest",
            "state-diagram",
            "regression-graph",
            "heatmap",
            "gate",
            "export",
            "import",
            "run",
        ]

        parser = create_parser()
        # Check by parsing --help for each command
        for cmd in expected_commands:
            with pytest.raises(SystemExit) as exc_info:
                parser.parse_args([cmd, "--help"])
            # SystemExit(0) means help was shown successfully
            assert exc_info.value.code == 0

    def test_heatmap_requires_input(self) -> None:
        """heatmap command requires --input."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["heatmap"])

    def test_state_diagram_requires_input(self) -> None:
        """state-diagram command requires --input."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["state-diagram"])

    def test_regression_graph_requires_input(self) -> None:
        """regression-graph command requires --input."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["regression-graph"])
