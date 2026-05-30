# Workflow Cookbook Adoption Tiers

プロジェクトが workflow-cookbook のドキュメント標準にどの程度準拠しているかを示す段階的フレームワーク。

## Overview

Adoption Tiers は、プロジェクトの成熟度とドキュメントの完全性を測定するための4段階のフレームワークです。

| Tier | Name | Description |
|------|------|-------------|
| 0 | Basic | 最小限のドキュメント（README.md のみ） |
| 1 | Structured | 構造化されたドキュメントとナビゲーション |
| 2 | Operational | 運用手順と評価基準 |
| 3 | Complete | 完全なトレーサビリティと知識マップ |

## Tier Definitions

### Tier 0: Basic

**目的**: プロジェクトの基本的な説明を提供

**必須ファイル**:
- `README.md`

**特徴**:
- プロジェクトの概要と使用方法
- インストール手順
- 基本的な使い方

**対象プロジェクト**:
- プロトタイプ
- 個人プロジェクト
- 実験的コード

---

### Tier 1: Structured

**目的**: AI エージェントと人間の両方にとって明確なナビゲーションを提供

**必須ファイル**:
- `README.md`
- `HUB.codex.md`
- `BLUEPRINT.md`

**特徴**:
- HUB による構造化されたナビゲーション
- BLUEPRINT による設計原則とアーキテクチャ
- AI エージェントが自律的に作業できる構造

**対象プロジェクト**:
- チームプロジェクト
- 継続的にメンテナンスされるコード
- 外部貢献者を受け入れるプロジェクト

---

### Tier 2: Operational

**目的**: 運用手順と品質基準を明確化

**必須ファイル**:
- Tier 1 の全ファイル
- `RUNBOOK.md`
- `GUARDRAILS.md`
- `EVALUATION.md`

**特徴**:
- RUNBOOK による標準運用手順
- GUARDRAILS による制約と禁止事項
- EVALUATION による品質基準と検証方法

**対象プロジェクト**:
- 本番環境で運用されるシステム
- 複数人での運用が必要なプロジェクト
- 品質保証が重要なプロジェクト

---

### Tier 3: Complete

**目的**: 完全なトレーサビリティと知識管理

**必須ファイル**:
- Tier 2 の全ファイル
- `docs/acceptance/` (受け入れ記録)
- `docs/tasks/` (タスク追跡)
- `docs/workflow-cookbook/` (知識マップ)

**特徴**:
- 受け入れ記録による変更の追跡
- タスク管理による作業の可視化
- Workflow Cookbook 知識マップによるドキュメント構造の自動化
- 28個のカプセルによる詳細なドキュメント要約

**対象プロジェクト**:
- エンタープライズシステム
- 長期にわたる大規模プロジェクト
- 複数チームが関わるプロジェクト

---

## Checking Your Tier

`check_workflow_cookbook_tier.py` ツールを使用して、プロジェクトの現在の Tier を確認できます。

```bash
# テキスト形式で確認
python tools/ci/check_workflow_cookbook_tier.py --repo /path/to/project

# JSON 形式で確認（CI/CD 統合用）
python tools/ci/check_workflow_cookbook_tier.py --repo /path/to/project --json

# 期待される Tier を指定（CI/CD ゲート用）
python tools/ci/check_workflow_cookbook_tier.py --repo /path/to/project --expected-tier 2
```

### 出力例

```
============================================================
Workflow Cookbook Tier Check
============================================================
Repository: /path/to/project
Current Tier: Tier 3: Complete

[OK] Tier 3: Complete: Complete traceability with acceptance records and knowledge maps

Workflow Cookbook Status:
  index.json: [OK]
  hot.json: [OK]
  caps/: [OK]
  Capsule count: 28
  Nodes: 28
  Edges: 45

============================================================
```

---

## Upgrading Tiers

### Tier 0 → Tier 1

**追加が必要**:
1. `HUB.codex.md` を作成
   - プロジェクトのナビゲーション構造を定義
   - 主要ファイルへのポインターを提供
2. `BLUEPRINT.md` を作成
   - 設計原則とアーキテクチャを文書化
   - 制約と決定事項を記録

**テンプレート**:
```bash
cp templates/tier1/HUB.codex.md ./HUB.codex.md
cp templates/tier1/BLUEPRINT.md ./BLUEPRINT.md
```

**作業時間**: 2-4時間

---

### Tier 1 → Tier 2

**追加が必要**:
1. `RUNBOOK.md` を作成
   - 標準運用手順を文書化
   - トラブルシューティングガイドを提供
2. `GUARDRAILS.md` を作成
   - プロジェクトの制約と禁止事項を定義
   - セキュリティとコンプライアンスの要件を記録
3. `EVALUATION.md` を作成
   - 品質基準と検証方法を定義
   - テスト戦略と受け入れ基準を記録

**テンプレート**:
```bash
cp templates/tier2/RUNBOOK.md ./RUNBOOK.md
cp templates/tier2/GUARDRAILS.md ./GUARDRAILS.md
cp templates/tier2/EVALUATION.md ./EVALUATION.md
```

**作業時間**: 4-8時間

---

### Tier 2 → Tier 3

**追加が必要**:
1. `docs/acceptance/` ディレクトリを作成
   - 受け入れ記録のテンプレートを配置
   - 変更の追跡と承認プロセスを確立
2. `docs/tasks/` ディレクトリを作成
   - タスク追跡のテンプレートを配置
   - 作業の可視化と優先順位付けを実施
3. `docs/workflow-cookbook/` ディレクトリを作成
   - `index.json` でノードとエッジを定義
   - `hot.json` で主要エントリポイントを定義
   - `caps/*.json` で各ノードの詳細要約を作成

**テンプレート**:
```bash
cp -r templates/tier3/docs ./
```

**Workflow Cookbook 初期化**:
1. `docs/workflow-cookbook/index.json` を作成（全ドキュメントをノードとして追加）
2. `docs/workflow-cookbook/hot.json` を作成（主要エントリポイントを定義）
3. 各ドキュメントに対応する `caps/*.json` ファイルを作成

**作業時間**: 8-16時間

---

## CI/CD Integration

`check_workflow_cookbook_tier.py` を CI/CD パイプラインに統合して、Tier の維持を自動化できます。

### GitHub Actions 例

```yaml
name: Workflow Cookbook Compliance

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  check-tier:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Check Workflow Cookbook Tier
        run: |
          python tools/ci/check_workflow_cookbook_tier.py \
            --repo . \
            --expected-tier 2
      
      - name: Validate Workflow Cookbook (Tier 3 only)
        if: success()
        run: |
          node -e "JSON.parse(require('fs').readFileSync('docs/workflow-cookbook/index.json'))"
          node -e "JSON.parse(require('fs').readFileSync('docs/workflow-cookbook/hot.json'))"
```

### Exit Codes

- `0`: プロジェクトが期待される Tier を満たしている
- `1`: プロジェクトが期待される Tier を満たしていない、またはエラーが発生

---

## Best Practices

### Tier の選択

- **小規模プロジェクト**: Tier 0-1 で十分
- **チームプロジェクト**: 最低 Tier 1 を目指す
- **本番システム**: Tier 2 以上を推奨
- **エンタープライズ**: Tier 3 を目標

### 段階的な移行

1. 現在の Tier を確認
2. 次の Tier に必要なファイルを特定
3. テンプレートを使用してファイルを作成
4. チームでレビュー
5. CI/CD で自動チェックを追加

### 継続的な改善

- 定期的に Tier を再評価
- 新しい要件が発生したら Tier を上げる
- プロジェクトの成長に合わせて Tier を進化

---

## Reference Implementation

`manual-bb-test-harness` は Tier 3 のリファレンス実装です。

**Tier 3 の特徴**:
- 6つの必須ドキュメント（README, HUB, BLUEPRINT, RUNBOOK, GUARDRAILS, EVALUATION）
- 3つのディレクトリ（docs/acceptance, docs/tasks, docs/workflow-cookbook）
- 28個の Workflow Cookbook カプセル
- 28ノード、45エッジの知識マップ
- 7つの quick paths

詳細は `docs/workflow-cookbook/` を参照してください。

---

## Tools and Templates

### ツール

- `tools/ci/check_workflow_cookbook_tier.py`: Tier チェックツール
- `scripts/validate-workflow-cookbook.sh`: Workflow Cookbook JSON 検証スクリプト

### テンプレート

- `templates/tier1/`: Tier 1 用のテンプレート
- `templates/tier2/`: Tier 2 用のテンプレート
- `templates/tier3/`: Tier 3 用のテンプレート

---

## FAQ

### Q: Tier を下げることはできますか？

A: 推奨されません。ただし、プロジェクトの規模が縮小した場合や、一時的な簡素化が必要な場合は、Tier を下げて文書化してください。

### Q: 部分的な準拠はどう評価されますか？

A: `check_workflow_cookbook_tier.py` は各 Tier の要件を個別にチェックします。一部のファイルが欠けている場合、現在の Tier と不足しているファイルを表示します。

### Q: カスタムファイルを追加しても良いですか？

A: はい。必須ファイルに加えて、プロジェクト固有のドキュメントを追加することを推奨します。ただし、必須ファイルの名前と構造は維持してください。

### Q: 複数のプロジェクトで同じ Tier を維持する必要がありますか？

A: いいえ。各プロジェクトの要件と規模に応じて、適切な Tier を選択してください。

---

## Related Documentation

- `docs/workflow-cookbook/README.md`: Workflow Cookbook 知識マップの使用方法
- `docs/acceptance/README.md`: 受け入れ記録の作成方法
- `docs/tasks/README.md`: タスク追跡の方法
- `RUNBOOK.md`: 標準運用手順
- `GUARDRAILS.md`: プロジェクトの制約
