"""Tests for scripts/validate-release-bundle.py.

# TRACE: scripts/validate-release-bundle.py (role: operations)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def load_validate_release_bundle_module() -> object:
    """Load validate-release-bundle.py module dynamically."""
    spec = importlib.util.spec_from_file_location(
        "validate_release_bundle", REPO_ROOT / "scripts" / "validate-release-bundle.py"
    )
    if spec is None or spec.loader is None:
        pytest.skip("Cannot load validate-release-bundle.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_release_bundle"] = module
    spec.loader.exec_module(module)
    return module


class TestReleaseBundleValidator:
    """Tests for ReleaseBundleValidator class."""

    def test_validator_initialization(self) -> None:
        """Validator initializes correctly."""
        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        assert validator.repo_root == REPO_ROOT
        assert len(validator.errors) == 0
        assert len(validator.warnings) == 0

    def test_validate_skill_bundle(self) -> None:
        """Skill bundle validation passes."""
        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        result = validator.validate_skill_bundle()

        assert result is True
        assert len(validator.errors) == 0

    def test_validate_schemas(self) -> None:
        """Schema validation passes."""
        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        result = validator.validate_schemas()

        assert result is True
        assert len(validator.errors) == 0

    def test_validate_artifact_examples(self) -> None:
        """Artifact examples validation passes."""
        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        result = validator.validate_artifact_examples()

        assert result is True

    def test_validate_goldens(self) -> None:
        """Goldens validation passes."""
        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        result = validator.validate_goldens()

        assert result is True

    def test_validate_utf8_encoding(self) -> None:
        """UTF-8 encoding validation passes."""
        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        result = validator.validate_utf8_encoding()

        assert result is True

    def test_validate_readme_references(self) -> None:
        """README references validation passes."""
        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        result = validator.validate_readme_references()

        assert result is True

    def test_run_validation(self) -> None:
        """Full validation run passes."""
        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        results = validator.run_validation()

        assert results["overall"] is True
        assert len(results["errors"]) == 0


class TestCreateDryRunBundle:
    """Tests for dry-run bundle creation."""

    def test_create_bundle(self, tmp_path: Path) -> None:
        """Create dry-run bundle."""
        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        bundle_path = validator.create_dry_run_bundle(tmp_path)

        assert bundle_path.exists()
        assert bundle_path.suffix == ".zip"
        assert bundle_path.stat().st_size > 0

    def test_bundle_contains_skill(self, tmp_path: Path) -> None:
        """Bundle contains SKILL.md."""
        import zipfile

        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        bundle_path = validator.create_dry_run_bundle(tmp_path)

        with zipfile.ZipFile(bundle_path, "r") as zf:
            names = zf.namelist()
            assert any("SKILL.md" in name for name in names)

    def test_bundle_contains_schemas(self, tmp_path: Path) -> None:
        """Bundle contains schemas."""
        import zipfile

        module = load_validate_release_bundle_module()

        validator = module.ReleaseBundleValidator(REPO_ROOT)
        bundle_path = validator.create_dry_run_bundle(tmp_path)

        with zipfile.ZipFile(bundle_path, "r") as zf:
            names = zf.namelist()
            assert any(".schema.json" in name for name in names)

    def test_bundle_contains_license_documents(self, tmp_path: Path) -> None:
        """Bundle contains all required license documents."""
        import zipfile

        module = load_validate_release_bundle_module()
        validator = module.ReleaseBundleValidator(REPO_ROOT)
        bundle_path = validator.create_dry_run_bundle(tmp_path)

        required = {
            "LICENSE",
            "LICENSE.ja.md",
            "NOTICE",
            "LICENSING.md",
            "COMMERCIAL-LICENSE.md",
            "THIRD_PARTY_NOTICES.md",
        }
        with zipfile.ZipFile(bundle_path, "r") as zf:
            assert required <= set(zf.namelist())


class TestValidateReleaseBundleMain:
    """Tests for main function."""

    def test_main_version(self) -> None:
        """Version flag works."""
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate-release-bundle.py"),
                "--version",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "validate-release-bundle" in result.stdout

    def test_main_dry_run(self, tmp_path: Path) -> None:
        """Dry-run validation works."""
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate-release-bundle.py"),
                "--dry-run",
                "--output",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout
        assert "Bundle created" in result.stdout
