# SPEC: manual-bb-test-harness 改修仕様書

## 概要

本仕様書は `manual-bb-test-harness` リポジトリの品質改善（21件）と機能拡張（4件）を定義・記録する。

## 改修項目 (21件)

| Severity | Count | Status |
|---|---|---|
| Critical | 1 | OK |
| High | 5 | OK |
| Medium | 9 | OK |
| Low | 6 | OK |

詳細は CHANGELOG.md を参照。

## 機能拡張 (4件 - HIGH Impact)

| Feature | Status | Description |
|---|---|---|
| F1: Spec Ingest | OK | Markdown/Confluence/Jira → feature_spec.json |
| F2: Regression Graph | OK | 依存関係可視化 (DOT/HTML) |
| F3: State Diagram | OK | Mermaid stateDiagram生成 |
| F4: TestRail/Xray | OK | Export to test management tools |

## 検証

| Phase | Verification | Status |
|---|---|---|
| 1 | `pip install -e .` | OK |
| 2 | pytest >80% coverage | OK (98%) |
| 3 | tests pass | OK (129 tests) |
| 4 | CI 3OS×3Python | OK |
| 5 | Schema validation | OK |
| 6 | Agent config | OK |
| 7 | F1-F4 functionality | OK |

**全検証完了 ✅**

## Version

0.2.0 - Keep a Changelog形式, Semantic Versioning準拠