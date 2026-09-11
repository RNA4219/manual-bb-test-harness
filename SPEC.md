# SPEC: manual-bb-test-harness 改修仕様書

現行契約: **4.1.1** / 検証済みテスト: **1168件** / Workflow Cookbook: **33 nodes・45 edges・33 capsules** / 次回レビュー: **2026-10-11**

## 概要

4.1.1では日本語ファイル名・UTF-8 BOM・証跡0件の入力不具合と、CIの分岐率判定を修正する。
[自己BBの修正受入](docs/acceptance/self-bb-fix-20260911/report.md)、
[純分岐率の検収](docs/acceptance/AC-20260911-branch-coverage.md)、
[配布仕様](docs/release-policy.md#411-自己bbの入力不具合と分岐率判定の修正)に基づき、
互換修正のパッチ版として公開する。

4.1.0ではREADMEリンク、[生成分割と指示](docs/specs/spec-06-bounded-generation-readiness.md)、
[PyPI公開後検証](docs/release-policy.md)、[要件信頼度の実績分析準備](docs/requirements-calibration.md)
を追加する。既存artifact契約・採点policy・Gate条件を維持する。

本仕様書は `manual-bb-test-harness` リポジトリの品質改善と機能拡張の仕様・検証履歴を記録する。

## 改修項目 (21件)

| Severity | Count | Status |
|---|---|---|
| Critical | 1 | OK |
| High | 5 | OK |
| Medium | 9 | OK |
| Low | 6 | OK |

詳細は CHANGELOG.md を参照。

## 機能一覧

| Feature | Status | Description |
|---|---|---|
| F1: Spec Ingest | OK | Markdown/Confluence/Jira → feature_spec.json |
| F2: Regression Graph | OK | 依存関係可視化 (DOT/HTML) |
| F3: State Diagram | OK | Mermaid stateDiagram生成 |
| F4: TestRail/Xray | OK | Export to test management tools |
| F5: Ready Phase Contract | OK | 企画・モック・要件メモ → Definition of Ready / Phase 1 契約 |
| F6: TestRail/Xray Import | OK | TestRail/Xray → execution_evidence.json, dry-run preview, status変換テスト付き |
| F7: Forward Test CLI | OK | `bb-harness run forward-test` wrapper, Skill 評価プロンプト出力 |
| F8: Local Mode | OK | `bb-harness run local-design`、OpenAI互換endpoint、Qwen 27B profile、schema repair、host管理Gate |
| F9: 技法被覆 | OK（有限モデル） | `coverage / migrate`、technique_plan、設計・実施・合格分離、Gate shadow。契約・上限は技法被覆ガイドを参照 |
| F10: 生成効率・証跡版 | 実装済み・実LLM比較は不成立（spec-05検収記録参照） | [spec-05](docs/specs/spec-05-efficient-generation-evidence-revisions.md)。重複送信削減、差分レビュー、予算・usage、case/model版照合、実LLM比較 |
| F11: 分割生成・完了判定 | 実装済み・小規模実LLMで全段生成完了、品質受入は未達（degraded） | [spec-06](docs/specs/spec-06-bounded-generation-readiness.md)。batched、終了理由、出力保護、設計状態、比較の実ファイル再検証 |
| F12: 要件定義信頼度 | 実装済み・運用policyによる評価 | [spec-07](docs/specs/spec-07-requirements-confidence.md)。要確認件数・重大度・密度・レビュー率、根拠付き解決、JSON／Markdown出力 |
| F13: HATE・QEG CI | 実装済み・GitHub CI成功 | [spec-08](docs/specs/spec-08-hate-qeg-ci.md)。実pytest証跡の正規化、hash・実行対象・合否検証、失敗時もartifact保存 |

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
| 2 | pytest coverage | OK (86.00% branch-inclusive coverage @ 2026-07-21) |
| 3 | tests pass | OK (765 tests passed @ 2026-07-21) |
| 4 | CI Python 3.10〜3.13 + unit/integration/PowerShell/package smoke | OK |
| 5 | Schema validation | OK |
| 6 | Agent config | OK |
| 7 | F1-F4 functionality | OK |
| 8 | F5 phase_contract schema/example validation | OK |
| 9 | F6 TestRail/Xray import | OK (50 tests) |
| 10 | F7 Forward-test CLI | OK |
| 11 | Workflow Cookbook Tier 3 | OK (33 nodes, 45 edges, 33 capsules) |
| 12 | F8 Local Mode CLI / schema / package smoke | OK |

上表は既存機能の検証履歴。追加変更の検証状況は対応するspecと検収記録を参照する。

## Version

4.1.1 - Keep a Changelog形式、[release policy](docs/release-policy.md)に準拠。

4.0.0でartifact契約の拡張に伴うmajor更新を行った。4.0.1ではPyPIが拒否した未登録classifierを除去し、PyPAの分類辞書によるbuild・公開前検証を追加する。package、CLI、PowerShell validator、README、Workflow Cookbookの現行版を4.0.1へ同期する。追加artifact契約1.1.0、既存入力との互換性、実LLM比較・batched全段完走の未達記録を保持する。PRとmainのCI成功を確認し、v4.0.1タグから新規配布物を作成する。既存v4.0.0タグ・配布物は変更しない。

## 分割生成・完了判定（2026-09-10）

追加仕様[spec-06](docs/specs/spec-06-bounded-generation-readiness.md)に基づき、batched生成、終了理由の判定、既存出力保護、design_status、実ファイルに基づく比較検証を追加。実LLMの結果は[検収記録](docs/acceptance/AC-20260910-batched.md)へ記録する。
