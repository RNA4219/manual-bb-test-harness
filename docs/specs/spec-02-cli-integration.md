# Spec: CLI統合

## 概要

散在するscripts/*.pyを単一CLIエントリポイント`bb-harness`に統合。サブコマンド形式で全機能を提供。

## 目的

- 利用者の使い勝手向上（単一コマンドで全機能アクセス）
- pip install可能なパッケージ化
- --help/--versionの一元管理
- 依存関係の明示化管理

## 要件

### R1: CLI構造

| id | 要件 | 優先度 |
|---|---|---|
| R1.1 | `bb-harness <subcommand>` 形式 | P0 |
| R1.2 | --help/--version全体サポート | P0 |
| R1.3 | 各subcommand固有引数継承 | P0 |
| R1.4 | 共通引数（--verbose、--dry-run） | P1 |

### R2: Subcommands

| id | subcommand | 元script | 優先度 |
|---|---|---|---|
| R2.1 | `validate` | quick-validate-skill.py | P0 |
| R2.2 | `ingest` | spec-ingest.py | P0 |
| R2.3 | `state-diagram` | state-diagram.py | P0 |
| R2.4 | `regression-graph` | regression-graph.py | P0 |
| R2.5 | `heatmap` | risk-heatmap.py | P0 |
| R2.6 | `gate` | evaluate-gate.py | P0 |
| R2.7 | `export-testrail` | export-testrail.py | P1 |
| R2.8 | `export-xray` | export-xray.py | P1 |
| R2.9 | `export-notion` | export-notion.py | P1 |
| R2.10 | `run-forward-test` | forward-test実行 | P2 |

### R3: パッケージ化

| id | 要件 | 優先度 |
|---|---|---|
| R3.1 | setup.py/pyproject.toml作成 | P0 |
| R3.2 | pip install可能 | P0 |
| R3.3 | requirements.txt明示化 | P0 |
| R3.4 | optional dependencies（requests、notion-sdk） | P1 |

### R4: 設定ファイル

| id | 要件 | 優先度 |
|---|---|---|
| R4.1 | ~/.bb-harness/config.yaml（API token等） | P1 |
| R4.2 | 環境変数優先度 > config.yaml > default | P1 |

## 設計

### CLI構成

```
bb-harness
├── validate      # Skill構造検証
├── ingest        # 仕様取り込み
│   ├── --source markdown
│   ├── --source confluence
│   └── --source jira
├── state-diagram # 状態遷移図生成
├── regression-graph # 回帰グラフ生成
├── heatmap       # リスクヒートマップ
├── gate          # Gate判定
├── export        # 外部連携
│   ├── testrail
│   ├── xray
│   └── notion
└── run           # forward-test実行
```

### 実装構造

```
src/bb_harness/
├── __init__.py
├── cli.py         # argparse entry point
├── commands/
│   ├── validate.py
│   ├── ingest.py
│   ├── state_diagram.py
│   ├── regression_graph.py
│   ├── heatmap.py
│   ├── gate.py
│   ├── export.py
│   └── run.py
├── core/
│   ├── loader.py  # JSON/YAML loader
│   ├── validator.py
│   └── config.py
└── __main__.py    # python -m bb_harness
```

### pyproject.toml

```toml
[project]
name = "bb-harness"
version = "0.2.0"
description = "Manual black-box test harness CLI"
authors = [{name = "RNA4219"}]
requires-python = ">=3.11"

dependencies = [
    "pyyaml>=6.0",
]

[project.optional-dependencies]
api = ["requests>=2.28"]
notion = ["notion-client>=2.0"]
all = ["bb-harness[api,notion]"]

[project.scripts]
bb-harness = "bb_harness.cli:main"

[project.entry-points."pipx.run"]
bb-harness = "bb_harness.cli:main"
```

## インターフェース

### 使用例

```bash
# インストール
pip install bb-harness
pip install bb-harness[all]  # optional dependencies含む

# 検証
bb-harness validate skills/my-skill

# 仕様取り込み
bb-harness ingest --source markdown --input spec.md --output feature_spec.json

# 状態遷移図
bb-harness state-diagram --input test_model.json --output diagram.mmd

# リスクヒートマップ
bb-harness heatmap --input risk_register.json --output heatmap.html

# Gate判定
bb-harness gate --input artifacts/ --output gate_decision.json --profile standard

# 外部連携
bb-harness export testrail --input cases.json --output testrail.csv
bb-harness export notion --input report.json --db DATABASE_ID

# forward-test
bb-harness run forward-test --skill skills/manual-bb-test-harness --input goldens/order-cancel.input.md

# 共通オプション
bb-harness --verbose gate --input artifacts/
bb-harness --dry-run export notion --input report.json
```

### 出力形式

- 成功時: stdoutに結果サマリ
- 失敗時: stderrにエラー詳細
- JSON出力: 指定ファイルパス

## 制約

- Python 3.11+必須
- 外部API連携はoptional dependencies
- Windows/macOS/Linux対応
- pip/pipxインストール可能

## テスト観点

| 观点 | ケース |
|---|---|
| 正常系 | bb-harness --help表示 |
| 正常系 | bb-harness validate pass |
| 異常系 | bb-harness validate fail（error message） |
| 正常系 | bb-harness ingest markdown成功 |
| 異常系 | bb-harness ingest jira（API token未設定） |
| 正常系 | pip install成功 |
| 正常系 | pipx run bb-harness動作 |

## 受入基準

- [x] `bb-harness --help`で主要subcommand一覧表示
- [x] `bb-harness --version`でversion表示
- [x] `pip install -e .` / CI installでパッケージ化検証
- [x] 主要script機能を `bb-harness` subcommand から呼び出し可能
- [x] dry-runモードでNotion API送信回避
- [x] `bb-harness --verbose` が validate/ingest/gate/export/import で stderr に詳細ログを出力（PLAN-CLI-01 @ 2026-05-30）
- [x] `bb-harness import testrail` / `bb-harness import xray` が wrapper 経由で動作、dry-run/token未設定テスト付き（PLAN-CLI-02 @ 2026-05-30）
- [x] `bb-harness run forward-test --help` が表示され、`--skill` と `--input` を受け取りプロンプトテンプレートを出力（PLAN-CLI-03 @ 2026-05-30）
- [x] `RUNBOOK.md` に import/export/run CLI の実行手順を追記、CLI tests を追加（PLAN-CLI-04 @ 2026-05-30）
