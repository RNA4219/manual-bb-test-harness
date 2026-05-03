# Changelog

Keep a Changelog形式, Semantic Versioning準拠。

## [Unreleased]

### Added
- SPEC.md: 改修仕様書
- Unit tests (tests/) - カバレッジ95%
- pyproject.toml: 依存関係設定
- Multi-platform CI (windows/ubuntu/macos, Python 3.10/3.11/3.12)
- Subdirectory README (schemas/, examples/, goldens/)
- Provider-agnostic agent config (agents/generic.yaml)
- `--version`, `--debug` flags
- `-SkillName` parameter (PowerShell)
- JSON golden examples
- Additional artifacts (manual_case_set, gate_decision)
- Schema descriptions

### Fixed
- Bare `Exception` catch → specific exceptions
- `$Matches` null check (PowerShell)
- Hardcoded skill name → configurable
- Error messages with path context
- Dynamic repo root detection
- TODO pattern explanation comments

## [0.1.0] - Initial Release

- Manual black-box test design skill
- JSON schemas, golden examples
- Validation scripts (Python/PowerShell)
- CI workflow, evaluation rubric
- Domain packs (EC, SaaS-RBAC)