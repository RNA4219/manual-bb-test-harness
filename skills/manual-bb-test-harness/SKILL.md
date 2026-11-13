---
name: manual-bb-test-harness
description: 手動ブラックボックス前提で、仕様・受入条件・変更点・不具合履歴・自動テスト証跡から、根拠付きテスト観点、リスク優先度、手動テストケース、工数見積り、品質ゲート判定、Go/No-Go brief を作る。要確認件数・重大度・レビュー根拠から要件定義の信頼度も評価する。Use when the task is to assess requirements confidence, design or review manual black-box test plans, derive equivalence/boundary/decision/state coverage, triage missing oracles, assess release readiness, or build a small JSON-contract harness for QA workflows.
---

# Manual BB Test Harness

## 目的

手動ブラックボックスを主軸に、観点からリリース判断までを監査可能な chain として作る。巨大な一枚岩プロンプトではなく、短い判断責務と型付き artifact をつなぐ。

## 仕事の入口

依頼に当たる仕事の節と、その節が指す参照を読む。「共通の方針」はどの仕事にも掛かる。

| 仕事 | 使う場面 | 読む節 |
|---|---|---|
| テスト設計を作る | 仕様、受入条件、業務ルール、変更点、対象環境、既存証跡から、観点から Go/No-Go brief までを出す | テスト設計を作る、Gate を判定する |
| Gate を判定する | 自動テスト証跡、手動 P0/P1 実行結果、欠陥状態、残余リスクからリリース可否を出す | Gate を判定する |
| Ready を判定する | 企画、モック、要件メモなど、開発着手前の入力を扱う | Ready と要件定義の信頼度 |
| 要件定義の信頼度を評価する | 要件定義の信頼度・要確認件数を評価する | Ready と要件定義の信頼度 |
| RanD の成果物を取り込む | RanDのR&D成果物・要求候補・文書監査・前回差分を使う | RanD連携 |
| 技法被覆を検証する | 正式な技法被覆、型付きモデル、移行、Local Modeの追加成果物を扱う | 技法被覆と Local Mode |
| Local Mode で生成する | Local Modeの生成・予算・証跡を扱う | 技法被覆と Local Mode |
| 既存の設計をレビューする | ほかの人や以前の版の設計・ケースを見る | テスト設計を作る。形は `references/output-templates.md` の「既存の設計をレビューするとき」 |
| Skill 自体を評価する | golden input で Skill を評価する | Skill 自体を評価する |

## 共通の方針

- 共有メモリではなく型付き artifact でつなぐ。
- 全 artifact に `source_refs`、`assumptions`、`confidence` または根拠文を持たせる。
- `black` を release acceptance の主役にし、`gray` はログや DB など限定内部情報による補助、`white` は自動テスト evidence の受け皿にする。
- 出力をレビューするときは、典型的な失敗モードを `references/failure-modes.md` で確認する。

通常は Markdown で返し、機械連携が必要な場合は JSON artifact も併記する。必ず traceability を見える形にする。

テンプレートは `references/output-templates.md` を読む。
同じファイルに、出したあとに直すとき・表計算や外部ツールへ展開するとき・日本語の見出しで渡すときの決まりがある。
詳細な artifact と schema の形は `references/artifact-contract.md` を読む。

## テスト設計を作る

必ず次の順で出力する。

1. 根拠付き観点
2. リスク
3. 優先度
4. 手動テストケース
5. テスト計画と開始・停止・再開条件
6. 工数
7. Gate 判定
8. Go/No-Go brief

7 と 8 は「Gate を判定する」の決まりで書く。依頼者が軽い版を求めたときは、順を保ったまま量を絞る。絞り方は `references/output-templates.md` の「軽い版」を読む。

### ワークフロー

開発着手前の入力を扱う場合は、先に「Ready と要件定義の信頼度」を読む。

1. `normalize_intake`: 仕様、受入条件、業務ルール、変更点、対象環境、既存証跡を `feature_spec` に正規化する。不足情報は `ok / degraded / blocked` で分類し、推測は assumption として残す。
2. `model_test_surface`: `flow / state / rule / data / role / regression impact` に分解し、coverage item の母集合を作る。
3. `derive_observations`: 同値分割、境界値、デシジョンテーブル、状態遷移、チェックリストベース、探索、エラー推測から観点を作る。
4. `assess_risk`: impact x likelihood を基底に、検出困難性、変更波及、外部依存、権限感度、自動テスト信用を補正して `P0..P3` を付ける。
5. `plan_techniques / synthesize_manual_cases`: 型付きモデルから `technique_plan` と被覆義務を確定し、高リスク観点を優先してケースを作る。各 scripted case に oracle、source_ref、具体的な入力と被覆対応を持たせる。統合後も必要な入力点・条件・連続経路を保持する。
6. `plan_test`: 目的、テストレベル、開始条件、停止・再開条件、データ・環境準備、見積根拠を `test_plan` にする。
7. `estimate_effort`: prep、execution、evidence、retry buffer を分けて見積もり、実行順を出す。
8. `evaluate_gates`: モデルと具体的入力から `coverage_report` を再計算し、設計済み・実施済み・合格を分離する。新しい被覆指標はshadowとして報告し、既存Gateは自動証跡、P0/P1結果、欠陥、残余リスク、waiverで判定する。
9. `assemble_release_brief`: ステークホルダー向けに 1 ページ相当の判断材料へ整える。

### ケース設計ルール

- Foundation の芯は同値分割、境界値分析、デシジョンテーブル、状態遷移に置く。
- 観点抽出は「仕様を読む」ではなく、coverage item を発見する作業として扱う。
- チェックリストベースは版と項目別結果を持つ独立技法として扱う。探索チャーターはtimebox、session notes、findings、retrospectiveを残し、エラー推測も仮説を明示する。
- 状態遷移、権限、回帰影響は first-class に扱う。注文、申請、承認、返金、解約、招待、認証は stateful とみなして確認する。
- テストデータは coverage を運ぶ主役として、`canonical_valid`、`invalid_single_fault`、`boundary3`、`rule_combo`、`state_seed`、`history_seed` に分ける。
- 仕様根拠のない expected result は scripted case にしない。`[要確認]` を付け、探索チャーターまたは blocker に降格する。
- `[要確認]` は質問に回す前に仕分ける。資料で決まるもの・書き方で解けるものは外し、残りを未決事項の表に載せる。
- 手動ケースは、期待結果ごとに LLM が実施できるかを仕分ける。自動テストとは別に扱う。決まりは `references/execution-routing.md` を読む。
- 既存の自動テストがある変更では、先に自動テストを読み、同じ振る舞いを観測している観点を手動ケースから外す。外した観点と根拠を出力の冒頭に書き、P0 の主経路は手動に残す。
- P0/P1 相当 feature だけ multi-run を検討する。3 run を目安に安定IDでmergeし、`support_count`は抽出安定性のシグナルとして残す。mandatoryとpriorityはAC、業務ルール、リスク根拠で決め、少数runだけを理由に降格しない。入力値、条件、経路、期待結果、被覆ID、traceも比較し、同じタイトルだけでは削除しない。

観点抽出の具体チェックは `references/case-design-policy.md` を読む。

対象に iOS / Android / mobile が含まれる場合は `references/platform-pack-mobile.md` も読む。

認証・認可、他者のデータの分離、個人情報、共用の資源に触れる変更と、脆弱性の検査の所見を受け取ったときは `references/security-pack.md` も読む。

EC、注文、決済、在庫、キャンセル、返金が主題なら `references/domain-pack-ec.md` も読む。B2B SaaS、workspace、role、permission、invitation、audit log が主題なら `references/domain-pack-saas-rbac.md` も読む。金融、決済、取引、認証、コンプライアンス、監査が主題なら `references/domain-pack-finance.md` も読む。

### リスク

- リスクは `impact x likelihood` を基底に、manual black-box 実務で効く補正を加える。
- FMEA の RPN は補助指標に留め、主ランキングには使わない。
- リスク表の優先度は式の帯のまま書く。上げるのはケースの優先度で、決まった理由があるときだけ上げ、理由を書く。
- 点数と優先度は暗算で書かない。リスク表を書いたら `bb-harness check risk --input <設計書.md>` で検算し、不一致と検算不可を 0 にしてから出す。

式と P0〜P3 の閾値、昇格の理由は `references/risk-and-gate-policy.md` を読む。

## Gate を判定する

- 品質ゲートは coverage 単体で決めない。新規変更の自動テスト証跡、手動 P0/P1 実行結果、欠陥状態、残余リスクで判定する。
- No-Go 条件は強く扱う。blocker、P0 fail、critical assumption unresolved、残余リスク超過のいずれかがあれば No-Go。
- 手動の実行結果がまだ無い時点の Gate は `no_go` とする。理由に実施前であることを書き、Go に足りない条件を `unmet_conditions` に並べる。

profile と判定の条件は `references/risk-and-gate-policy.md` を読む。

## Ready と要件定義の信頼度

企画、モック、要件メモなど、開発着手前の入力を扱う場合は、先に `references/ready-phase-contract.md` を読み、`phase_contract` で Definition of Ready を判定する。

要件定義の信頼度・要確認件数を評価するときは `references/requirements-confidence.md` を読み、`evaluate requirements`で採点する。レビュー・解決の根拠を記録し、ReadyやリリースGoと区別する。

## RanD連携

RanDのR&D成果物・要求候補・文書監査・前回差分を使う場合は、`references/rand-integration.md`を読む。`bb-harness import rand`で設計入力と依頼文を作り、任意の欠陥台帳を次の探索へ引き継ぐ。

## 技法被覆と Local Mode

正式な技法被覆、型付きモデル、移行、Local Modeの追加成果物を扱うときは `references/technique-coverage.md` を読む。

Local Modeの生成・予算・証跡を扱う場合は `references/efficient-generation.md` を読む。compactでは未被覆補完と差分レビューを使い、実測usageと推定を区別する。新しい実行証跡はケースとモデルの版を照合する。

## Skill 自体を評価する

Skill 自体を評価するときは `references/forward-test.md` の golden input を使う。
