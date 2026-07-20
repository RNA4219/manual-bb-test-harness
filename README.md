# manual-bb-test-harness

[![license: RNA-TPSAL-1.0](https://img.shields.io/badge/license-RNA--TPSAL--1.0-blue.svg)](LICENSE)
[![source-available](https://img.shields.io/badge/source--available-yes-orange.svg)](LICENSE)

手動ブラックボックステスト設計を、根拠付きartifactと決定的な品質Gateで支援する。

## Local Mode

Local Modeは、provider障害時にもOpenAI互換のローカルLLMでテスト設計を継続するための明示的な実行モード。LLMを候補生成器に限定し、schema、risk・工数計算、lint、Gateはホスト側で制御する。

### Qwen3.6 27Bで実行

llama.cppまたはLM Studioで `qwen3.6-27b` をOpenAI互換APIとして起動し、次を実行する。`qwen36` profileは既定で `http://127.0.0.1:8084/v1` を使う。

```powershell
uv sync
uv run bb-harness run local-design `
  --input goldens/order-cancel.input.md `
  --output tmp/order-cancel-local `
  --profile qwen36
```

### LM Studio・任意のllama.cpp serverで実行

`generic` profileへendpointとmodel IDを明示する。

```powershell
uv run bb-harness run local-design `
  --input goldens/order-cancel.input.md `
  --output tmp/order-cancel-local `
  --profile generic `
  --base-url http://127.0.0.1:1234/v1 `
  --model local-model-id
```

出力先には `manual-test-design.md`、schema検証済みartifact群、`lint_report.json`、`quality_report.json`、`run_manifest.json` が生成される。実行証跡がない場合、Gateは常に `no_go` になる。

Local Modeは本リポジトリに統合済みで、別リポジトリの導入は不要。設定、成果物、fail closed条件の詳細は [Local Mode guide](docs/local-model-guide.md) を参照。

現行リリース系列: **3.0.0** / 検証済みテスト: **765件** / Workflow Cookbook: **33 nodes・45 edges・33 capsules** / 次回レビュー: **2026-10-11**
人間向け概要は [docs/human-readme.md](docs/human-readme.md) を参照。

## ライセンス

このバージョンは、RNA Third-Party Service Attribution License 1.0に基づくsource-availableソフトウェアです。

個人利用、研究、教育、オープンソース活動、および企業による自社内利用は無償です。

第三者向けの有償QA、テスト、開発支援、コンサルティング等で利用する場合は、顧客の技術担当者が確認できる文書に、ツール名、原開発者、公式リポジトリ、使用versionまたはcommit、改変の有無を案件単位で一度記載してください。

帰属表示を省略するホワイトラベル利用には、[別途書面による商用ライセンス](COMMERCIAL-LICENSE.md)が必要です。

過去のMIT版は、引き続きMIT Licenseの条件で利用できます。詳細は[LICENSING.md](LICENSING.md)を参照してください。

## License

This version is source-available under the RNA Third-Party Service Attribution License 1.0.

Personal use, research, education, open-source activities, and internal business use are permitted without charge.

When the software is used to provide a paid QA, testing, development, consulting, managed, outsourced, or similar service to a third party, a one-time attribution notice must be provided in project documentation reasonably accessible to the Customer technical team.

Attribution-free white-label use requires a [separate written commercial license](COMMERCIAL-LICENSE.md).

Previously released MIT-licensed versions remain available under their original MIT terms. See [LICENSING.md](LICENSING.md).

<!-- LLM-BOOTSTRAP v1 -->
**For AI Agents**: 読む順番:

1. `docs/workflow-cookbook/index.json` — ノード一覧・隣接関係 (33 nodes, 45 edges)
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

## Full Validation

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

この repo は、手動ブラックボックス前提の QA 設計 Skillと、そのLocal Modeを管理する正本。
Local Modeは `run local-design` で明示的に選択し、固有部分は `docs/local-model-guide.md` を入口にする。

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

## Gate 2.0

既定profileは`standard`です。Gateは`manual_case_set`全件を分母にし、証跡のないcaseを`untested`として評価します。`--input`へartifact directoryを渡すと規定名のrisk、case、feature、observation、automation、waiverを自動検出します。 P0非pass・hard automation failure・open blocker/critical/high・critical assumptionは常に`no_go`で、waiverはrisk IDへ追跡できるP1/mandatory observation/残余riskだけに適用されます。

```powershell
uv run bb-harness gate --input examples/artifacts --build-id build-20260711.1 --output gate.json
uv run bb-harness gate --evidence evidence --risk risk.json --cases cases.json --feature feature.json --observations observations.json --automation automation.json --waivers waivers.json --build-id build-20260711.1 --output gate.json
```

`no_go`は正常な判定なのでexit code 0、schema不正・feature/build不一致・曖昧な重複証跡はexit code 1です。旧artifactは2.0では読み取りません。

## Distribution Verification

wheelとsdistはrepo外の一時directoryへ隔離installし、主要subcommandを実行して検証します。

```powershell
uv run python tools/ci/package_smoke.py
uv run python scripts/validate-release-bundle.py --dry-run --package-smoke
```
