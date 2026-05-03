# Improvement Notes

このメモは、`manual-bb-test-harness` の改善履歴を記録する。

## 2026-05-03 改善完了

### 完了した改善項目

| Category | Count | Details |
|---|---|---|
| Critical | 1 | Unit tests追加 (42 tests, 94% coverage) |
| High | 5 | Exception handling, null check, CI multi-platform, pyproject.toml |
| Medium | 9 | Schema descriptions, READMEs, type hints, version/debug flags |
| Low | 6 | CHANGELOG, SPEC, generic.yaml, JSON golden examples |

### CI状況

- 3 OS × 3 Python versions 全成功
- Node.js 20 deprecation対応: actions更新済み (v5/v6)

### 残課題（必要時のみ）

- GitHub Pages hosting for schemas ($id URL resolution)
- Coverage 100%達成（現在94%）

## 初版運用方針（廃止）

以下は初版時の記録。現在は改善完了。

### 初版方針（過去）

- Skill本体、参照方針、golden、rubric、Notion templateは初版完成
- 品質保証中心: evaluation-rubric.md, goldens/, Notion forward-test記録
- schemas/は機械連携補助（Notion運用を主）

### Optional Improvements（実施済み）

- Domain pack追加: auth, payment, notification, mobile/offline
- Golden追加:権限,決済,外部連携失敗,モバイル中断復帰
- failure-modes.md更新: forward-test失敗例追加
- Markdown fallback report: Notion転記容易化