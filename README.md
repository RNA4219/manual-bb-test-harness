# manual-bb-test-harness

仕様や受入条件から、根拠付きの手動テスト設計とリリース判断を作る Codex Skill と CLI です。ISTQB の同値分割・境界値分析・デシジョンテーブル・状態遷移を軸に、探索的テストやリスク評価を組み合わせます。

- 仕様・変更点・不具合履歴から、確認すべき観点と優先度を整理する。
- 手動テストケース・探索チャーター・工数見積りを、根拠と追跡関係を付けて作る。
- 自動・手動の実行証跡、欠陥、残余リスクから `go / conditional_go / no_go` と判断理由を出す。

## はじめる

CLI は Python 3.10 以上と uv を使います。リポジトリのルートで実行してください。

```powershell
uv sync
uv run bb-harness --help
```

### テスト設計を依頼する

Codex に [Skill](skills/manual-bb-test-harness/SKILL.md) と入力仕様を指定します。サンプルで試す場合:

```text
./skills/manual-bb-test-harness の $manual-bb-test-harness を使い、
./goldens/order-cancel.input.md の手動ブラックボックステストを設計してください。
根拠付き観点、リスク、優先度、ケース、工数、Gate 判定、Go/No-Go brief を作成してください。
```

必要な入力、出力の読み方、モバイル向けサンプルは[利用ガイド](docs/human-readme.md)にまとめています。

### 実行証跡から Gate を判定する

用意済みのサンプル成果物を使って、CLI の判定を確認できます。

```powershell
uv run bb-harness gate --input examples/artifacts --build-id web-1.42.0+1289 --output tmp/gate.json
```

この例は、承認済みの例外条件を含む `conditional_go` になります。自分の成果物を使うときの必須入力・判定条件・終了コードは [Gate の実行手順](RUNBOOK.md#gate-の実行)を参照してください。

## 詳しい説明

| 目的 | 読む文書 |
|---|---|
| 入力を用意し、設計結果を確認する | [利用ガイド](docs/human-readme.md) |
| CLI 操作・検証・トラブル対応 | [RUNBOOK](RUNBOOK.md) |
| RanD の要求・監査結果を取り込む | [RanD 連携](skills/manual-bb-test-harness/references/rand-integration.md) |
| TestRail / Xray / Notion と連携する | [外部連携の実行手順](RUNBOOK.md#6-cli-で-importexportrun-を実行する) |
| JSON 成果物と移行条件を確認する | [artifact 契約](skills/manual-bb-test-harness/references/artifact-contract.md)・[schemas](schemas/) |
| 設計方針・保守時の読み順を確認する | [BLUEPRINT](BLUEPRINT.md)・[HUB](HUB.codex.md) |
| 変更履歴・検証記録を確認する | [CHANGELOG](CHANGELOG.md)・[ISTQB レビュー](docs/istqb-review-round2-20260912.md) |

<details>
<summary>AI エージェント向けの読み順</summary>

<!-- LLM-BOOTSTRAP v1 -->
1. [HUB.codex.md](HUB.codex.md) で目的に合う正本文書を選ぶ。
2. [index.json](docs/workflow-cookbook/index.json) で関係するノードを確認する (34 nodes, 48 edges)。
3. [hot.json](docs/workflow-cookbook/hot.json) の `quick_paths` と [caps/](docs/workflow-cookbook/caps/) から、必要な文書を読む。

変更対象とその前後 2 hop を起点に、必要な capsule を選んでください。Skill 実行は `skill_execution`、CLI 操作は `cli_operations`、品質確認は `quality_assurance` が入口です。作業時の指示は [AGENTS.md](AGENTS.md) を参照してください。

検証済みテスト: **1002件**。実施条件と制約は [検証記録](docs/istqb-review-round2-20260912.md)を参照してください。
<!-- /LLM-BOOTSTRAP -->

</details>
