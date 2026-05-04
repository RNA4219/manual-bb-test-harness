# Spec: CI/CD強化

## 概要

manual-bb-test-harnessの品質保証自動化。pre-commit hookとGitHub Actionsで、スキーマ検証、スクリプトテスト、golden diffチェックを自動実行。

## 目的

- コミット前に基本的な構造検証を強制
- PR時は全検証を実行し、品質Gateを自動判定
- リリース時はgolden差分を可視化し、破壊的変更を防止

## 要件

### R1: pre-commit hook

| id | 要件 | 優先度 |
|---|---|---|
| R1.1 | YAML frontmatter検証（name/description必須） | P0 |
| R1.2 | JSON syntax検証（schemas/*.json、examples/*.json） | P0 |
| R1.3 | TODO marker検出禁止 | P1 |
| R1.4 | 文字エンコーディングUTF-8強制 | P1 |

### R2: GitHub Actions（validate.yml）

| id | 要件 | 優先度 |
|---|---|---|
| R2.1 | quick-validate-skill.py実行 | P0 |
| R2.2 | JSON schema validation（ajv/cli） | P0 |
| R2.3 | 各scriptの--help動作確認 | P1 |
| R2.4 | evaluate-gate.pyのdry-runテスト | P1 |
| R2.5 | risk-heatmap.pyのSVG生成テスト | P1 |

### R3: GitHub Actions（golden-diff.yml）

| id | 要件 | 優先度 |
|---|---|---|
| R3.1 | golden input/outputファイルのdiff可視化 | P0 |
| R3.2 | schema変更時のbreaking change警告 | P1 |
| R3.3 | PRコメントにdiff結果を投稿 | P2 |

### R4: Release workflow

| id | 要件 | 優先度 |
|---|---|---|
| R4.1 | tag作成時にartifact zipを生成 | P1 |
| R4.2 | CHANGELOGY.md自動更新（commit logから） | P2 |

## 設計

### pre-commit hook構成

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: validate-skill
        name: Validate Skill Structure
        entry: python scripts/quick-validate-skill.py skills/manual-bb-test-harness
        language: system
        pass_filenames: false
        
      - id: validate-json
        name: Validate JSON Syntax
        entry: python -m json.tool
        language: system
        files: \.json$
        
      - id: check-utf8
        name: Check UTF-8 Encoding
        entry: python scripts/check-utf8.py
        language: system
        files: \.(md|py|yaml|json)$
```

### GitHub Actions構成

```yaml
# .github/workflows/validate.yml
name: Validate Skill

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: pip install pyyaml requests
        
      - name: Validate skill structure
        run: python scripts/quick-validate-skill.py skills/manual-bb-test-harness
        
      - name: Validate JSON schemas
        run: |
          for f in schemas/*.json examples/artifacts/*.json; do
            python -m json.tool "$f" > /dev/null || exit 1
          done
          
      - name: Test script help
        run: |
          for script in scripts/*.py; do
            python "$script" --help || exit 1
          done
          
      - name: Test evaluate-gate
        run: |
          python scripts/evaluate-gate.py \
            --input examples/artifacts \
            --output /tmp/gate_test.json \
            --profile standard
            
      - name: Test risk-heatmap
        run: |
          python scripts/risk-heatmap.py \
            --input examples/artifacts/order-cancel.risk_register.json \
            --output /tmp/heatmap_test.html
```

## インターフェース

### CLI（開発者向け）

```bash
# pre-commitインストール
pre-commit install

# 手動検証
pre-commit run --all-files

# GitHub Actionsローカル実行
act pull_request
```

### 出力

- validate.yml: 成功/失敗ログ、各stepの結果
- golden-diff.yml: diff HTML report、PRコメント

## 制約

- pre-commitはPython 3.11+必須
- GitHub Actionsはubuntu-latest使用
- 外部ネットワーク依存なし（CI内で完結）
- 実行時間5分以内

## テスト観点

| 观点 | ケース |
|---|---|
| 正常系 | 正しいコミット → hook pass |
| 異常系 | frontmatter欠損 → hook fail |
| 異常系 | invalid JSON → hook fail |
| 正常系 | PR作成 → validate.yml success |
| 異常系 | schema breaking change → golden-diff.yml warning |

## 受入基準

- [ ] pre-commit installでhook有効化
- [ ] TODO marker含むファイルでhook fail
- [ ] validate.ymlがPRで自動実行
- [ ] 全script --help動作確認pass
- [ ] 実行時間5分以内