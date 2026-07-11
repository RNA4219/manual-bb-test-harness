# SPEC: manual-bb-test-harness 改修仕様書

現行契約: **2.0.0** / 検証済みテスト: **726件** / Workflow Cookbook: **33 nodes・45 edges・33 capsules** / 次回レビュー: **2026-10-11**

## 概要

本仕様書は `manual-bb-test-harness` リポジトリの品質改善（21件）と機能拡張（5件）を定義・記録する。

## 改修項目 (21件)

| Severity | Count | Status |
|---|---|---|
| Critical | 1 | OK |
| High | 5 | OK |
| Medium | 9 | OK |
| Low | 6 | OK |

詳細は CHANGELOG.md を参照。

## 機能拡張 (7件 - HIGH Impact)

| Feature | Status | Description |
|---|---|---|
| F1: Spec Ingest | OK | Markdown/Confluence/Jira → feature_spec.json |
| F2: Regression Graph | OK | 依存関係可視化 (DOT/HTML) |
| F3: State Diagram | OK | Mermaid stateDiagram生成 |
| F4: TestRail/Xray | OK | Export to test management tools |
| F5: Ready Phase Contract | OK | 企画・モック・要件メモ → Definition of Ready / Phase 1 契約 |
| F6: TestRail/Xray Import | OK | TestRail/Xray → execution_evidence.json, dry-run preview, status変換テスト付き |
| F7: Forward Test CLI | OK | `bb-harness run forward-test` wrapper, Skill 評価プロンプト出力 |

## F5: Ready Phase Contract

開発着手前の企画、モック、要件メモを `phase_contract` に正規化し、締め切り決定前の健全性を `ok / degraded / blocked` で判定する。

### 必須項目

- 誰の課題か: `problem_owner`
- 成功条件: `success_conditions`
- Phase 1 の範囲: `phase1_scope`
- Phase 1 でやらないこと: `phase1_non_goals`
- 未決事項: `open_questions`
- 仕様不足: `spec_gaps`
- 技術リスク: `technical_risks`
- 指標: `metrics`
- 初期テスト観点: `test_lenses`

### Ready 判定

- `ok`: Phase 1 の対象ユーザー、成功条件、in/out、主要 oracle、未決事項の owner が揃っている。
- `degraded`: 軽微または中程度の未決事項はあるが、仮説と owner と期限があり、Phase 1 の範囲を壊さない。
- `blocked`: critical 未決事項、検証不能な成功条件、主要状態/権限/データ境界の欠落、または外部依存の未合意がある。

### 成果物

- Skill 導線: `skills/manual-bb-test-harness/SKILL.md`
- 詳細仕様: `skills/manual-bb-test-harness/references/ready-phase-contract.md`
- artifact 契約: `skills/manual-bb-test-harness/references/artifact-contract.md`
- 出力テンプレート: `skills/manual-bb-test-harness/references/output-templates.md`
- JSON Schema: `schemas/phase_contract.schema.json`
- Example: `examples/artifacts/order-cancel.phase_contract.json`

## 検証

| Phase | Verification | Status |
|---|---|---|
| 1 | `pip install -e .` | OK |
| 2 | pytest coverage | OK (86.40% branch-inclusive coverage @ 2026-07-12) |
| 3 | tests pass | OK (726 tests passed @ 2026-07-12) |
| 4 | CI Python 3.10〜3.13 + unit/integration/PowerShell/package smoke | OK |
| 5 | Schema validation | OK |
| 6 | Agent config | OK |
| 7 | F1-F4 functionality | OK |
| 8 | F5 phase_contract schema/example validation | OK |
| 9 | F6 TestRail/Xray import | OK (50 tests) |
| 10 | F7 Forward-test CLI | OK |
| 11 | Workflow Cookbook Tier 3 | OK (33 nodes, 45 edges, 33 capsules) |

**全検証完了 ✅**

## Version

2.0.0 - Keep a Changelog形式, Semantic Versioning準拠
