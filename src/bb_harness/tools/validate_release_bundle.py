"""Validate release artifact bundle for release readiness.

Generates a dry-run bundle and validates:
- Skill bundle structure
- JSON schemas
- Artifact examples
- Golden outputs
- UTF-8 encoding
- README references

Usage:
    python scripts/validate-release-bundle.py --dry-run
    python scripts/validate-release-bundle.py --version

Example:
    python scripts/validate-release-bundle.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from bb_harness import __version__

REPO_ROOT = Path.cwd()


class ReleaseBundleValidator:
    """Validate release artifact bundle."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_skill_bundle(self) -> bool:
        """Validate Skill bundle structure."""
        skill_dir = self.repo_root / "skills" / "manual-bb-test-harness"

        # Check SKILL.md exists
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            self.errors.append(f"Missing SKILL.md: {skill_md}")
            return False

        # Check frontmatter
        content = skill_md.read_text(encoding="utf-8")
        if not content.startswith("---"):
            self.errors.append("SKILL.md missing frontmatter")
            return False

        # Parse frontmatter
        lines = content.split("\n")
        in_frontmatter = False
        frontmatter: dict[str, str] = {}
        for line in lines:
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
                continue
            if in_frontmatter and ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip()

        # Check required frontmatter fields
        if "name" not in frontmatter:
            self.errors.append("SKILL.md missing 'name' in frontmatter")
            return False
        if "description" not in frontmatter:
            self.errors.append("SKILL.md missing 'description' in frontmatter")
            return False

        # Check references directory
        refs_dir = skill_dir / "references"
        if not refs_dir.exists():
            self.warnings.append("Missing references directory")

        return True

    def validate_schemas(self) -> bool:
        """Validate JSON schemas."""
        schema_dir = self.repo_root / "schemas"

        if not schema_dir.exists():
            self.errors.append(f"Missing schemas directory: {schema_dir}")
            return False

        # Check required schemas
        required_schemas = [
            "phase_contract.schema.json",
            "feature_spec.schema.json",
            "test_model.schema.json",
            "risk_register.schema.json",
            "manual_case_set.schema.json",
            "gate_decision.schema.json",
            "execution_evidence.schema.json",
            "automation_evidence.schema.json",
            "waiver_set.schema.json",
        ]

        for schema_name in required_schemas:
            schema_file = schema_dir / schema_name
            if not schema_file.exists():
                self.errors.append(f"Missing schema: {schema_name}")
                continue

            # Validate JSON syntax
            try:
                json.loads(schema_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                self.errors.append(f"Invalid JSON in {schema_name}: {e}")

        return len(self.errors) == 0

    def validate_artifact_examples(self) -> bool:
        """Validate artifact examples."""
        examples_dir = self.repo_root / "examples" / "artifacts"

        if not examples_dir.exists():
            self.errors.append(f"Missing examples/artifacts directory: {examples_dir}")
            return False

        # Check at least one example per artifact type
        artifact_types = {
            "feature_spec": "*.feature_spec.json",
            "test_model": "*.test_model.json",
            "risk_register": "*.risk_register.json",
            "manual_case_set": "*.manual_case_set.json",
            "gate_decision": "*.gate_decision.json",
            "execution_evidence": "execution_evidence/*.json",
            "automation_evidence": "*.automation_evidence.json",
            "waiver_set": "*.waiver_set.json",
        }

        for artifact_type, pattern in artifact_types.items():
            if pattern.startswith("execution_evidence"):
                files = list((examples_dir / "execution_evidence").glob("*.json"))
            else:
                files = list(examples_dir.glob(pattern))

            if len(files) == 0:
                self.warnings.append(f"No example for {artifact_type}")

        return True

    def validate_goldens(self) -> bool:
        """Validate golden outputs."""
        goldens_dir = self.repo_root / "goldens"

        if not goldens_dir.exists():
            self.errors.append(f"Missing goldens directory: {goldens_dir}")
            return False

        # Check required golden pairs
        required_goldens = [
            ("order-cancel.input.md", "order-cancel.expected.md"),
            ("mobile-session-resume.input.md", "mobile-session-resume.expected.md"),
        ]

        for input_file, expected_file in required_goldens:
            if not (goldens_dir / input_file).exists():
                self.warnings.append(f"Missing golden input: {input_file}")
            if not (goldens_dir / expected_file).exists():
                self.warnings.append(f"Missing golden expected: {expected_file}")

        return True

    def validate_utf8_encoding(self) -> bool:
        """Validate UTF-8 encoding for all text files."""
        text_patterns = [
            "skills/**/*.md",
            "docs/**/*.md",
            "goldens/**/*.md",
            "schemas/**/*.json",
            "examples/**/*.json",
        ]

        for pattern in text_patterns:
            for file in self.repo_root.glob(pattern):
                try:
                    file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    self.errors.append(f"UTF-8 encoding error: {file}")

        return len(self.errors) == 0

    def validate_readme_references(self) -> bool:
        """Validate README references."""
        readme = self.repo_root / "README.md"

        if not readme.exists():
            self.errors.append("Missing README.md")
            return False

        content = readme.read_text(encoding="utf-8")

        # Check required references
        required_refs = [
            "HUB.codex.md",
            "BLUEPRINT.md",
            "RUNBOOK.md",
            "skills/manual-bb-test-harness",
        ]

        for ref in required_refs:
            if ref not in content:
                self.warnings.append(f"README.md missing reference to {ref}")

        return True

    def validate_release_metadata(self) -> bool:
        """Validate commercial contact resolution and release version consistency."""
        commercial_path = self.repo_root / "COMMERCIAL-LICENSE.md"
        if not commercial_path.exists():
            self.errors.append("Missing COMMERCIAL-LICENSE.md")
            return False
        commercial = commercial_path.read_text(encoding="utf-8")
        if "[COMMERCIAL_CONTACT]" in commercial:
            self.errors.append("COMMERCIAL-LICENSE.md still contains [COMMERCIAL_CONTACT]")
        if "https://licensing.rna4219.com/" not in commercial:
            self.errors.append(
                "COMMERCIAL-LICENSE.md is missing the official application portal"
            )

        sources = {
            "pyproject.toml": (
                self.repo_root / "pyproject.toml",
                r'^version\s*=\s*"([^"]+)"$',
            ),
            "README.md": (
                self.repo_root / "README.md",
                r"現行リリース系列:\s*\*\*([^*]+)\*\*",
            ),
            "src/bb_harness/__init__.py": (
                self.repo_root / "src" / "bb_harness" / "__init__.py",
                r'^__version__\s*=\s*"([^"]+)"$',
            ),
        }
        versions: dict[str, str] = {}
        for label, (path, pattern) in sources.items():
            if not path.exists():
                self.errors.append(f"Missing version source: {label}")
                continue
            match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
            if match is None:
                self.errors.append(f"{label} is missing its release version")
                continue
            versions[label] = match.group(1)
        expected = versions.get("pyproject.toml")
        if expected is not None:
            for label, value in versions.items():
                if value != expected:
                    self.errors.append(
                        f"{label} version mismatch: expected {expected}, got {value}"
                    )
        return len(self.errors) == 0

    def validate_package_distribution(self) -> bool:
        """Build and smoke-test installed wheel and sdist."""
        result = subprocess.run(
            [sys.executable, str(self.repo_root / "tools" / "ci" / "package_smoke.py")],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.errors.append(
                "Package smoke failed:\n"
                + result.stdout
                + ("\n" + result.stderr if result.stderr else "")
            )
            return False
        return True

    def create_dry_run_bundle(self, output_dir: Path) -> Path:
        """Create dry-run bundle."""
        bundle_path = output_dir / "release-bundle-dry-run.zip"

        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Skill bundle
            skill_dir = self.repo_root / "skills" / "manual-bb-test-harness"
            for file in skill_dir.glob("**/*"):
                if file.is_file():
                    zf.write(file, f"skills/manual-bb-test-harness/{file.relative_to(skill_dir)}")

            # Schemas
            schema_dir = self.repo_root / "schemas"
            for file in schema_dir.glob("*.schema.json"):
                zf.write(file, f"schemas/{file.name}")

            # Examples
            examples_dir = self.repo_root / "examples" / "artifacts"
            for file in examples_dir.glob("**/*.json"):
                if file.parent.name == "execution_evidence":
                    zf.write(file, f"examples/artifacts/execution_evidence/{file.name}")
                else:
                    zf.write(file, f"examples/artifacts/{file.name}")

            # Goldens
            goldens_dir = self.repo_root / "goldens"
            for file in goldens_dir.glob("*.md"):
                zf.write(file, f"goldens/{file.name}")

            # Key docs
            docs_files = [
                "LICENSE",
                "LICENSE.ja.md",
                "NOTICE",
                "LICENSING.md",
                "COMMERCIAL-LICENSE.md",
                "THIRD_PARTY_NOTICES.md",
                "README.md",
                "CHANGELOG.md",
                "BLUEPRINT.md",
                "RUNBOOK.md",
                "GUARDRAILS.md",
                "EVALUATION.md",
                "HUB.codex.md",
            ]
            for doc_file in docs_files:
                file = self.repo_root / doc_file
                if file.exists():
                    zf.write(file, doc_file)

        return bundle_path

    def run_validation(self, include_package_smoke: bool = False) -> dict[str, Any]:
        """Run all validations."""
        results: dict[str, Any] = {
            "skill_bundle": self.validate_skill_bundle(),
            "schemas": self.validate_schemas(),
            "artifact_examples": self.validate_artifact_examples(),
            "goldens": self.validate_goldens(),
            "utf8_encoding": self.validate_utf8_encoding(),
            "readme_references": self.validate_readme_references(),
            "release_metadata": self.validate_release_metadata(),
            "errors": self.errors,
            "warnings": self.warnings,
        }
        if include_package_smoke:
            results["package_distribution"] = self.validate_package_distribution()

        results["overall"] = len(self.errors) == 0

        return results


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate release artifact bundle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create and validate dry-run bundle",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tmp-release-bundle"),
        help="Output directory for dry-run bundle",
    )
    parser.add_argument(
        "--package-smoke",
        action="store_true",
        help="Build and smoke-test installed wheel and sdist",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"validate-release-bundle {__version__}",
    )

    args = parser.parse_args()

    validator = ReleaseBundleValidator(REPO_ROOT)

    if args.dry_run:
        print("=" * 60)
        print("RELEASE BUNDLE VALIDATION (Dry-run)")
        print("=" * 60)

        # Run validations
        results = validator.run_validation(include_package_smoke=args.package_smoke)

        # Create dry-run bundle
        args.output.mkdir(parents=True, exist_ok=True)
        bundle_path = validator.create_dry_run_bundle(args.output)

        print(f"\nBundle created: {bundle_path}")
        print(f"Bundle size: {bundle_path.stat().st_size} bytes")

        # Print results
        print("\nValidation Results:")
        print("-" * 40)

        for key, value in results.items():
            if key in ["errors", "warnings"]:
                continue
            status = "[OK]" if value else "[FAIL]"
            print(f"  {key}: {status}")

        if results["errors"]:
            print("\nErrors:")
            for error in results["errors"]:
                print(f"  - {error}")

        if results["warnings"]:
            print("\nWarnings:")
            for warning in results["warnings"]:
                print(f"  - {warning}")

        print("\n" + "=" * 60)
        print(f"Overall: [{'PASS' if results['overall'] else 'FAIL'}]")
        print("=" * 60)

        return 0 if results["overall"] else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
