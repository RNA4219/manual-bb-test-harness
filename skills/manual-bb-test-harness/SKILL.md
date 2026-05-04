---
name: manual-bb-test-harness
description: 手動ブラックボックス前提で、仕様・受入条件・変更点・不具合履歴・自動テスト証跡から、根拠付きテスト観点、リスク優先度、手動テストケース、工数見積り、品質ゲート判定、Go/No-Go brief を作る。Use when Codex needs to design or review manual black-box test plans, derive equivalence/boundary/decision/state coverage, triage missing oracles, assess release readiness, or build a small JSON-contract harness for QA workflows.
---

# Manual BB Test Harness

## 目的

手動ブラックボックスを主軸に、観点からリリース判断までを監査可能な chain として作る。巨大な一枚岩プロンプトではなく、短い判断責務と型付き artifact をつなぐ。

必ず次の順で出力する。

1. 根拠付き観点
2. リスク
3. 優先度
4. 手動テストケース
5. 工数
6. Gate 判定
7. Go/No-Go brief

## 基本ワークフロー

1. `normalize_intake`: 仕様、受入条件、業務ルール、変更点、対象環境、既存証跡を `feature_spec` に正規化する。不足情報は `ok / degraded / blocked` で分類し、推測は assumption として残す。
2. `model_test_surface`: `flow / state / rule / data / role / regression impact` に分解し、coverage item の母集合を作る。
3. `derive_observations`: 同値分割、境界値、デシジョンテーブル、状態遷移、経験ベース探索チャーターから観点を作る。
4. `assess_risk`: impact x likelihood を基底に、検出困難性、変更波及、外部依存、権限感度、自動テスト信用を補正して `P0..P3` を付ける。
5. `synthesize_manual_cases`: 高リスク観点を優先し、重複を減らした最小の手動ケース集合へ圧縮する。各 scripted case には oracle と source_ref を必須にする。
6. `estimate_effort`: prep、execution、evidence、retry buffer を分けて見積もり、実行順を出す。
7. `evaluate_gates`: 自動テスト証跡、手動 P0/P1 結果、欠陥状態、残余リスク、waiver を合わせて `go / conditional_go / no_go` を判定する。
8. `assemble_release_brief`: ステークホルダー向けに 1 ページ相当の判断材料へ整える。

## Artifact 方針

- 共有メモリではなく型付き artifact でつなぐ。
- 全 artifact に `source_refs`、`assumptions`、`confidence` または根拠文を持たせる。
- `black` を release acceptance の主役にし、`gray` はログや DB など限定内部情報による補助、`white` は自動テスト evidence の受け皿にする。
- P0/P1 相当 feature だけ multi-run を検討する。3 run を目安に `normalized_title + technique + trace_to` で merge し、support_count が低い観点は optional に落とす。
- 出力をレビューするときは、典型的な失敗モードを `references/failure-modes.md` で確認する。

詳細な artifact と schema の形は `references/artifact-contract.md` を読む。

## ケース設計ルール

- Foundation の芯は同値分割、境界値分析、デシジョンテーブル、状態遷移に置く。
- 観点抽出は「仕様を読む」ではなく、coverage item を発見する作業として扱う。
- 経験ベース技法は scripted case を補完する探索チャーターとして扱う。
- 状態遷移、権限、回帰影響は first-class に扱う。注文、申請、承認、返金、解約、招待、認証は stateful とみなして確認する。
- テストデータは coverage を運ぶ主役として、`canonical_valid`、`invalid_single_fault`、`boundary3`、`rule_combo`、`state_seed`、`history_seed` に分ける。
- 仕様根拠のない expected result は scripted case にしない。`[要確認]` を付け、探索チャーターまたは blocker に降格する。

観点抽出の具体チェックは `references/case-design-policy.md` を読む。

EC、注文、決済、在庫、キャンセル、返金が主題なら `references/domain-pack-ec.md` も読む。B2B SaaS、workspace、role、permission、invitation、audit log が主題なら `references/domain-pack-saas-rbac.md` も読む。金融、決済、取引、認証、コンプライアンス、監査が主題なら `references/domain-pack-finance.md` も読む。

## リスクと Gate

- リスクは `impact x likelihood` を基底に、manual black-box 実務で効く補正を加える。
- FMEA の RPN は補助指標に留め、主ランキングには使わない。
- 品質ゲートは coverage 単体で決めない。新規変更の自動テスト証跡、手動 P0/P1 実行結果、欠陥状態、残余リスクで判定する。
- No-Go 条件は強く扱う。blocker、P0 fail、critical assumption unresolved、残余リスク超過のいずれかがあれば No-Go。

式、閾値、profile は `references/risk-and-gate-policy.md` を読む。

## 出力形式

通常は Markdown で返し、機械連携が必要な場合は JSON artifact も併記する。必ず traceability を見える形にする。

テンプレートは `references/output-templates.md` を読む。

Skill 自体を評価するときは `references/forward-test.md` の golden input を使う。
