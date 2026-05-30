"""Unit tests for check-utf8.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest

# Load module dynamically
spec_check_utf8 = importlib.util.spec_from_file_location(
    "check_utf8", Path(__file__).parent.parent / "scripts" / "check-utf8.py"
)
check_utf8 = importlib.util.module_from_spec(spec_check_utf8)
sys.modules["check_utf8"] = check_utf8
spec_check_utf8.loader.exec_module(check_utf8)

main_check_utf8 = check_utf8.main


class TestCheckUtf8Help:
    """Tests for check-utf8.py help and version."""

    def test_help_flag_exits_zero(self) -> None:
        """--help should print help and exit 0."""
        with mock.patch.object(sys, "argv", ["script", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main_check_utf8()
            assert exc_info.value.code == 0

    def test_version_flag_exits_zero(self) -> None:
        """--version should print version and exit 0."""
        with mock.patch.object(sys, "argv", ["script", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main_check_utf8()
            assert exc_info.value.code == 0

    def test_no_args_prints_help(self) -> None:
        """No arguments should print help and exit 1."""
        with mock.patch.object(sys, "argv", ["script"]):
            assert main_check_utf8() == 1

    def test_valid_utf8_file_returns_zero(self, tmp_path: Path) -> None:
        """Valid UTF-8 file should return 0."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, UTF-8!", encoding="utf-8")

        with mock.patch.object(sys, "argv", ["script", str(test_file)]):
            assert main_check_utf8() == 0

    def test_non_utf8_file_returns_one(self, tmp_path: Path) -> None:
        """Non-UTF-8 file should return 1."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"\xff\xfe Invalid UTF-8")

        with mock.patch.object(sys, "argv", ["script", str(test_file)]):
            assert main_check_utf8() == 1

    def test_nonexistent_file_is_skipped(self, tmp_path: Path) -> None:
        """Nonexistent file should be warned and skipped."""
        nonexistent = tmp_path / "does_not_exist.txt"
        valid_file = tmp_path / "valid.txt"
        valid_file.write_text("Valid UTF-8", encoding="utf-8")

        with mock.patch.object(sys, "argv", ["script", str(nonexistent), str(valid_file)]):
            # Should succeed since valid file passes UTF-8 check
            assert main_check_utf8() == 0
