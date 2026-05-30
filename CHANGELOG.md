# Changelog

## Unreleased

- README を AI-first 入口へ再構成し、人間向け概要を `docs/human-readme.md` に分離。
- artifact 検証で `jsonschema` を標準依存にし、`examples/artifacts/` の全 JSON example が `validate-artifact --all --strict` で通るように整理。
- 検証記録を現状の `145 passed` に更新。
- mobile 対象向けに `mobile_contexts` と `platform_matrix` を追加し、iOS / Android の中断復帰、権限、通知入口、ネットワーク差分を扱う platform pack と golden を追加。
- workflow-cookbook 準拠の正本ドキュメントとして `HUB.codex.md`、`BLUEPRINT.md`、`RUNBOOK.md`、`GUARDRAILS.md`、`EVALUATION.md` を追加。
- `docs/tasks/` と `docs/acceptance/` を追加し、repo self-review と release readiness 記録を残せるようにした。
- 既存の spec-ingest / state-diagram / export 生成例と `uv.lock` を repo の追跡対象として整理し、README 群へ反映した。

### Added (PLAN 完了分)
- **F6: TestRail/Xray Import** (`scripts/import-testrail.py`, `scripts/import-xray.py`)
  - `--dry-run` で API token 未設定でも preview モードで成功。
  - `bb-harness import testrail/xray` CLI wrapper 経由で動作。
  - status/priority 変換テスト (`tests/test_import_status.py`, 50 tests)。
  - import 出力が `execution_evidence.schema.json` で検証可能。
- **F7: Forward Test CLI** (`src/bb_harness/commands/run.py`)
  - `bb-harness run forward-test --skill ... --input ...` で Skill 評価プロンプト出力。
- **Workflow Cookbook Tier 3 達成** (`docs/workflow-cookbook/`)
  - `index.json`: 28 nodes, 45 edges (知識マップ)
  - `hot.json`: 6 hot nodes, 7 quick paths
  - `caps/*.json`: 28 capsule files (全ドキュメント要約)
  - `README.md`: Workflow Cookbook 使用手順とスキーマ定義
  - `adoption-tiers.md`: Tier 0-3 の段階的導入フレームワーク
  - `README.md` に LLM-BOOTSTRAP ブロック追加 (AI エージェント向け効率的ナビゲーション)
  - Core Files テーブルに `docs/workflow-cookbook/` を追加
  - `tools/ci/check_workflow_cookbook_tier.py`: Tier チェックツール
  - `templates/tier1/`, `templates/tier2/`, `templates/tier3/`: テンプレート集
  - `docs/birdseye/` → `docs/workflow-cookbook/` にリネーム（workflow-cookbook 標準準拠）
  - `check_adoption_tier.py` → `check_workflow_cookbook_tier.py` にリネーム
- `--verbose` を全 subcommand (validate/ingest/gate/export/import/run/heatmap/state-diagram/regression-graph) に伝播。
- `execution_evidence.schema.json` に `timestamp` フィールド追加。
- `RUNBOOK.md` に import/export/run CLI の実行手順を追記。
- `tests/test_cli_dryrun.py` に import/export/run の CLI wrapper テストを追加。

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
- Unit tests: 129 tests (from 67)[^1]
- Coverage: ~98%[^1]

## [0.1.1] - 2026-05-03 (Quality Improvement)

### Added
- SPEC.md: 改修仕様書
- Unit tests (tests/) - カバレッジ98%[^1]
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

[^1]: 当時の記録。現在のテスト数・カバレッジは異なる可能性がある。最新値は `uv run pytest` 実行で確認。
