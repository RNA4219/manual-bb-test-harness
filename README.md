# manual-bb-test-harness

手動ブラックボックス QA 設計 Skill の配布・保守 repo。
人間向け概要は [docs/human-readme.md](docs/human-readme.md) を参照。

<!-- LLM-BOOTSTRAP v1 -->
**For AI Agents**: 読む順番:

1. `docs/workflow-cookbook/index.json` — ノード一覧・隣接関係 (28 nodes, 45 edges)
2. `docs/workflow-cookbook/hot.json` — 主要エントリポイント (6 hot nodes)
3. `docs/workflow-cookbook/caps/<path>.json` — 必要ノードだけ point read

**フォーカス手順**:

- 直近変更ファイル ±2 hop のノードIDを `index.json` から取得
- 対応する `caps/*.json` のみ読み込み
- 全文読みは避ける (トークン節約)

**Quick Paths**:

- Skill 実行: `hot.json#quick_paths.skill_execution`
- CLI 操作: `hot.json#quick_paths.cli_operations`
- 品質確認: `hot.json#quick_paths.quality_assurance`
<!-- /LLM-BOOTSTRAP -->

---

## Quick Start (人間向け)

```powershell
# インストール
uv sync

# 全テスト実行
uv run pytest

# Lint
uv run ruff check .

# Skill 構造検証
uv run python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness

# Artifact 検証 (14 files)
uv run python .\scripts\validate-artifact.py --all examples\artifacts --strict

# Spec 検証 (4 specs)
uv run python .\scripts\validate-spec.py --all

# Workflow Cookbook Tier チェック
python tools/ci/check_workflow_cookbook_tier.py --repo .
```

### CLI で import / export / run

```powershell
# Import dry-run (API token 不要)
uv run bb-harness import testrail --project 12 --run 1234 --output tmp-import --dry-run
uv run bb-harness import xray --exec TEST-1 --output tmp-import --dry-run

# Export dry-run (API token 不要)
uv run bb-harness --dry-run export notion --score 90 --status pass --db dummy_db

# Forward-test (Skill 評価プロンプト出力)
uv run bb-harness run forward-test --input goldens/order-cancel.input.md

# 詳細出力
uv run bb-harness --verbose validate
uv run bb-harness --verbose gate --input examples/artifacts --output gate.json

# ヘルプ
uv run bb-harness --help
```

---

## For AI Agents

この repo は、手動ブラックボックス前提の QA 設計 Skill `manual-bb-test-harness` を配布・保守する正本 repo。

### Task Classifier

| user intent | read first |
|---|---|
| Skill を使って手動 QA 設計を作る | `skills/manual-bb-test-harness/SKILL.md` → `references/*.md` → `goldens/` |
| repo の読み順を決める | `HUB.codex.md` |
| 設計方針や I/O 契約を確認する | `BLUEPRINT.md` → `references/artifact-contract.md` |
| 実行手順や検証手順を確認する | `RUNBOOK.md` → `scripts/` |
| 変更時の境界や禁止事項を確認する | `GUARDRAILS.md` → `AGENTS.md` |
| artifact/schema を変える | `BLUEPRINT.md` → `schemas/` → `examples/artifacts/` → `goldens/` |
| mobile 対応を確認する | `references/platform-pack-mobile.md` → `goldens/mobile-session-resume.*` |
| forward-test を評価・記録する | `references/forward-test.md` → `docs/evaluation-rubric.md` |

### Required Output Chain

Skill を実行する場合は、原則として次の順に出力する。

1. 根拠付き観点
2. リスク
3. 優先度
4. 手動テストケース
5. 工数
6. Gate 判定
7. Go/No-Go brief

機械連携が必要な場合は Markdown に加えて JSON artifact を併記する。`traceability`、`source_refs`、`assumptions`、`confidence` または根拠文を落とさない。

### Execution Prompt

```text
Use $manual-bb-test-harness at ./skills/manual-bb-test-harness to create a manual black-box test design for ./goldens/order-cancel.input.md.
```

入力に iOS / Android / mobile が含まれる場合は、`platform-pack-mobile.md` を読む。

---

## Core Files

| file | role |
|---|---|
| `HUB.codex.md` | repo 全体の AI 向け読み順 |
| `AGENTS.md` | repo 内作業時の指示 |
| `BLUEPRINT.md` | 目的、scope、I/O contract、主要設計 |
| `RUNBOOK.md` | 実行手順、検証、更新時の確認 |
| `GUARDRAILS.md` | 運用原則、境界、禁止事項 |
| `EVALUATION.md` | 受入条件、品質基準、検証チェック |
| `SPEC.md` | 実装済み機能と改修履歴の仕様メモ |
| `CHANGELOG.md` | 変更履歴 (Keep a Changelog 形式) |
| `skills/manual-bb-test-harness/SKILL.md` | Skill 実行時の主導線 |
| `skills/manual-bb-test-harness/references/` | 詳細方針、domain pack、出力テンプレート |
| `goldens/` | 出力品質を見る review anchors |
| `schemas/` | JSON artifact schema |
| `examples/artifacts/` | schema 化した artifact の最小例 |
| `exports/` | TestRail / Xray 連携の生成例 |
| `docs/workflow-cookbook/` | AI 向け知識マップ (index.json, hot.json, caps/) |
| `docs/workflow-cookbook/adoption-tiers.md` | Workflow Cookbook 準拠段階フレームワーク |
| `templates/` | Tier 1-3 用のドキュメントテンプレート |
| `tools/ci/check_workflow_cookbook_tier.py` | Workflow Cookbook Tier チェックツール |
| `docs/` | 評価、記録、調査、人間向け補助文書 |

---

## Update Rules

- `SKILL.md` は短い運用手順に保つ。
- 詳細な契約、方針、テンプレートは `references/` に置く。
- artifact contract を変える場合は `schemas/`、`examples/artifacts/`、`goldens/` を同時に見る。
- 出力品質が変わる場合は `goldens/`、`docs/evaluation-rubric.md`、forward-test 記録を更新する。
- repo の正本関係は `HUB.codex.md` に集約し、README は AI routing と最短導線を優先する。
- 原典調査や長文メモは `docs/research/` に置き、Skill 本体へ直接詰め込まない。
