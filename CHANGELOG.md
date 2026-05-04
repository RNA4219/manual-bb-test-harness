# Changelog

Keep a Changelog形式, Semantic Versioning準拠。

## [0.2.0] - 2026-05-03

### Added (HIGH Impact Features)
- **F1: Spec Ingest Engine** (`scripts/spec-ingest.py`)
  - Markdown仕様からfeature_spec.json自動生成
  - YAML frontmatter + 構造化セクション解析
  - Confluence/Jira ingestion stub (API連携準備)
- **F2: Regression Graph Visualization** (`scripts/regression-graph.py`)
  - feature_spec間の依存関係可視化
  - GraphViz DOT出力 + D3.js HTML出力
  - changed_areas共有による影響範囲分析
- **F3: State Transition Diagram Generator** (`scripts/state-diagram.py`)
  - test_model.jsonからMermaid stateDiagram自動生成
  - valid/invalid transitions可視化
- **F4: TestRail/Xray Export**
  - `scripts/export-testrail.py`: CSV/JSON export (TestRail import対応)
  - `scripts/export-xray.py`: JSON export (Jira Xray import対応)
  - manual_case_set → TestRail/Xray形式変換

### Added (Schemas)
- `schemas/spec-source.schema.json`: 仕様入力schema
- `schemas/testrail-export.schema.json`: TestRail出力schema
- `schemas/xray-export.schema.json`: Xray出力schema

### Added (Examples)
- `docs/features/order-cancel-partial.md`: Markdown仕様例
- `examples/artifacts/order-cancel-partial.feature_spec.json`: Ingest出力例
- `examples/artifacts/*.states.mmd`: Mermaid diagram出力例
- `examples/regression-graph.dot/html`: 依存グラフ出力例
- `exports/testrail-order-cancel.csv`: TestRail export例
- `exports/xray-order-cancel.json`: Xray export例

### Tests
- Unit tests: 129 tests (from 67)
- Coverage: ~98% (maintained)

## [0.1.1] - 2026-05-03 (Quality Improvement)

### Added
- SPEC.md: 改修仕様書
- Unit tests (tests/) - カバレッジ98%
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