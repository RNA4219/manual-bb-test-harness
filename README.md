# manual-bb-test-harness

[![CI](https://github.com/RNA4219/manual-bb-test-harness/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/RNA4219/manual-bb-test-harness/actions/workflows/validate.yml)
[![license: RNA-TPSAL-1.0](https://img.shields.io/badge/license-RNA--TPSAL--1.0-blue.svg)](https://github.com/RNA4219/manual-bb-test-harness/blob/main/LICENSE)
[![source-available](https://img.shields.io/badge/source--available-yes-orange.svg)](https://github.com/RNA4219/manual-bb-test-harness/blob/main/LICENSE)

仕様や受入条件から、根拠付きの手動テスト設計とリリース判断を作る Codex Skill と CLI です。ISTQB の同値分割・境界値分析・デシジョンテーブル・状態遷移を軸に、探索的テストやリスク評価を組み合わせます。

- 仕様・変更点・不具合履歴から、確認すべき観点と優先度を整理する。
- 手動テストケース・探索チャーター・工数見積りを、根拠と追跡関係を付けて作る。
- 自動・手動の実行証跡、欠陥、残余リスクから `go / conditional_go / no_go` と判断理由を出す。

## はじめる

CLI は Python 3.10 以上で動作します。公開パッケージは `python -m pip install bb-harness` で導入できます。Skill・サンプルも使う場合はリポジトリを取得し、ルートで次を実行してください。

```powershell
uv sync
uv run bb-harness --help
```

### テスト設計を依頼する

Codex に [Skill](https://github.com/RNA4219/manual-bb-test-harness/blob/main/skills/manual-bb-test-harness/SKILL.md) と入力仕様を指定します。サンプルで試す場合:

```text
./skills/manual-bb-test-harness の $manual-bb-test-harness を使い、
./goldens/order-cancel.input.md の手動ブラックボックステストを設計してください。
根拠付き観点、リスク、優先度、ケース、工数、Gate 判定、Go/No-Go brief を作成してください。
```

必要な入力、出力の読み方、モバイル向けサンプルは[利用ガイド](https://github.com/RNA4219/manual-bb-test-harness/blob/main/docs/human-readme.md)にまとめています。

### ローカル LLM で設計する

OpenAI 互換のローカル LLM を起動してから、Local Mode を明示して実行します。

```powershell
uv run bb-harness run local-design --input goldens/order-cancel.input.md --output tmp/order-cancel-local --profile qwen36
```

接続先・モデル・生成予算の設定は [Local Mode ガイド](https://github.com/RNA4219/manual-bb-test-harness/blob/main/docs/local-model-guide.md)を参照してください。実行証跡がない段階のリリース判定は `no_go` になります。

### 実行証跡から Gate を判定する

用意済みのサンプル成果物を使って、CLI の判定を確認できます。

```powershell
uv run bb-harness gate --input examples/artifacts --build-id web-1.42.0+1289 --output tmp/gate.json
```

この例は、承認済みの例外条件を含む `conditional_go` になります。自分の成果物を使うときの必須入力・判定条件・終了コードは [Gate の実行手順](https://github.com/RNA4219/manual-bb-test-harness/blob/main/RUNBOOK.md#gate-の実行)を参照してください。

## 詳しい説明

| 目的 | 読む文書 |
|---|---|
| 入力を用意し、設計結果を確認する | [利用ガイド](https://github.com/RNA4219/manual-bb-test-harness/blob/main/docs/human-readme.md) |
| CLI 操作・検証・トラブル対応 | [RUNBOOK](https://github.com/RNA4219/manual-bb-test-harness/blob/main/RUNBOOK.md) |
| RanD の要求・監査結果を取り込む | [RanD 連携](https://github.com/RNA4219/manual-bb-test-harness/blob/main/skills/manual-bb-test-harness/references/rand-integration.md) |
| TestRail / Xray / Notion と連携する | [外部連携の実行手順](https://github.com/RNA4219/manual-bb-test-harness/blob/main/RUNBOOK.md#6-cli-で-importexportrun-を実行する) |
| JSON 成果物と移行条件を確認する | [artifact 契約](https://github.com/RNA4219/manual-bb-test-harness/blob/main/skills/manual-bb-test-harness/references/artifact-contract.md)・[schemas](https://github.com/RNA4219/manual-bb-test-harness/blob/main/schemas/) |
| 技法別の被覆を検証・移行する | [技法と被覆](https://github.com/RNA4219/manual-bb-test-harness/blob/main/skills/manual-bb-test-harness/references/technique-coverage.md) |
| 要件の信頼度を評価する | [評価手順](https://github.com/RNA4219/manual-bb-test-harness/blob/main/skills/manual-bb-test-harness/references/requirements-confidence.md)・[実績との比較](https://github.com/RNA4219/manual-bb-test-harness/blob/main/docs/requirements-calibration.md) |
| ローカル生成の予算・分割を設定する | [生成設定](https://github.com/RNA4219/manual-bb-test-harness/blob/main/skills/manual-bb-test-harness/references/efficient-generation.md) |
| 設計方針・保守時の読み順を確認する | [BLUEPRINT](https://github.com/RNA4219/manual-bb-test-harness/blob/main/BLUEPRINT.md)・[HUB](https://github.com/RNA4219/manual-bb-test-harness/blob/main/HUB.codex.md) |
| 変更履歴・検証記録を確認する | [CHANGELOG](https://github.com/RNA4219/manual-bb-test-harness/blob/main/CHANGELOG.md)・[ISTQB レビュー](https://github.com/RNA4219/manual-bb-test-harness/blob/main/docs/istqb-review-round2-20260912.md) |

## ライセンス

このバージョンは [RNA Third-Party Service Attribution License 1.0](https://github.com/RNA4219/manual-bb-test-harness/blob/main/LICENSE) に基づく source-available ソフトウェアです。個人利用・研究・教育・自社内利用は無償です。第三者向けの有償サービスでは案件単位の帰属表示が必要で、帰属表示を省略するホワイトラベル利用には別途書面による商用ライセンスが必要です。

詳しい条件は [LICENSING.md](https://github.com/RNA4219/manual-bb-test-harness/blob/main/LICENSING.md) と [商用ライセンス](https://github.com/RNA4219/manual-bb-test-harness/blob/main/COMMERCIAL-LICENSE.md)を参照してください。過去の MIT 版は引き続き元の条件で利用できます。

<details>
<summary>AI エージェント向けの読み順</summary>

<!-- LLM-BOOTSTRAP v1 -->
1. [HUB.codex.md](https://github.com/RNA4219/manual-bb-test-harness/blob/main/HUB.codex.md) で目的に合う正本文書を選ぶ。
2. [index.json](https://github.com/RNA4219/manual-bb-test-harness/blob/main/docs/workflow-cookbook/index.json) で関係するノードを確認する (34 nodes, 48 edges)。
3. [hot.json](https://github.com/RNA4219/manual-bb-test-harness/blob/main/docs/workflow-cookbook/hot.json) の `quick_paths` と [caps/](https://github.com/RNA4219/manual-bb-test-harness/blob/main/docs/workflow-cookbook/caps/) から、必要な文書を読む。

変更対象とその前後 2 hop を起点に、必要な capsule を選んでください。Skill 実行は `skill_execution`、CLI 操作は `cli_operations`、品質確認は `quality_assurance` が入口です。作業時の指示は [AGENTS.md](https://github.com/RNA4219/manual-bb-test-harness/blob/main/AGENTS.md) を参照してください。

現行リリース系列: **4.1.1** / 検証済みテスト: **1481件**。実施条件と制約は [検証記録](https://github.com/RNA4219/manual-bb-test-harness/blob/main/docs/istqb-review-round2-20260912.md)を参照してください。
<!-- /LLM-BOOTSTRAP -->

</details>
