# manual-bb-test-harness

AI-first README. 人間向けの概要と利用説明は [docs/human-readme.md](docs/human-readme.md) を読む。

## AI Routing

この repo は、手動ブラックボックス前提の QA 設計 Skill `manual-bb-test-harness` を配布・保守するための正本 repo。

使うべきとき:

- 仕様、受入条件、変更点、不具合履歴、自動テスト証跡から、手動テスト観点とケースを作る。
- リリース前に P0/P1 の手動確認範囲、残余リスク、Gate 判定、Go/No-Go brief を整理する。
- 仕様不足、oracle 不足、権限、状態遷移、回帰影響、mobile 固有差分を QA 観点として洗い出す。
- Skill の artifact 契約、schema、golden、評価基準、export/import 補助を保守する。

使わないとき:

- 自動テストフレームワークそのものを実装する。
- 実機クラウド、MDM、外部 SaaS の本番設定を構築する。
- プロダクト固有の業務ルール正本をこの repo に集約する。

## Task Classifier

| user intent | read first | then |
|---|---|---|
| Skill を使って手動 QA 設計を作る | `skills/manual-bb-test-harness/SKILL.md` | 必要な `skills/manual-bb-test-harness/references/*.md`、`goldens/` |
| repo の読み順を決める | `HUB.codex.md` | 目的別の正本 |
| 設計方針や I/O 契約を確認する | `BLUEPRINT.md` | `skills/manual-bb-test-harness/references/artifact-contract.md` |
| 実行手順や検証手順を確認する | `RUNBOOK.md` | `scripts/`、`.github/workflows/validate.yml` |
| 変更時の境界や禁止事項を確認する | `GUARDRAILS.md` | `AGENTS.md` |
| 受入条件や品質基準を見る | `EVALUATION.md` | `docs/evaluation-rubric.md`、`goldens/` |
| artifact/schema を変える | `BLUEPRINT.md` | `schemas/`、`examples/artifacts/`、`goldens/` |
| mobile 対応を確認する | `skills/manual-bb-test-harness/references/platform-pack-mobile.md` | `goldens/mobile-session-resume.*` |
| forward-test を評価・記録する | `skills/manual-bb-test-harness/references/forward-test.md` | `docs/evaluation-rubric.md`、`docs/notion-report-guide.md` |
| 人間向け説明を読む | `docs/human-readme.md` | 必要に応じて root docs |

## Required Output Chain

Skill を実行する場合は、原則として次の順に出力する。

1. 根拠付き観点
2. リスク
3. 優先度
4. 手動テストケース
5. 工数
6. Gate 判定
7. Go/No-Go brief

機械連携が必要な場合は Markdown に加えて JSON artifact を併記する。traceability、source_refs、assumptions、confidence または根拠文を落とさない。

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
| `skills/manual-bb-test-harness/SKILL.md` | Skill 実行時の主導線 |
| `skills/manual-bb-test-harness/references/` | 詳細方針、domain pack、出力テンプレート |
| `goldens/` | 出力品質を見る review anchors |
| `schemas/` | JSON artifact schema |
| `examples/artifacts/` | schema 化した artifact の最小例 |
| `exports/` | TestRail / Xray 連携の生成例 |
| `docs/` | 評価、記録、調査、人間向け補助文書 |

## Execution Prompt

Skill を repo 内から試す場合:

```text
Use $manual-bb-test-harness at ./skills/manual-bb-test-harness to create a manual black-box test design for ./goldens/order-cancel.input.md.
```

入力に iOS / Android / mobile が含まれる場合は、`platform-pack-mobile.md` を読む。EC、SaaS RBAC、finance の主題では対応する domain pack を読む。

## Validation

変更後は、影響範囲に応じて次を実行する。

```powershell
uv run pytest
uv run python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness
.\scripts\validate-skill.ps1
```

Skill Creator validator が必要な場合:

```powershell
$env:PYTHONUTF8='1'
uv run --with pyyaml python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" ".\skills\manual-bb-test-harness"
```

## Update Rules

- `SKILL.md` は短い運用手順に保つ。
- 詳細な契約、方針、テンプレートは `skills/manual-bb-test-harness/references/` に置く。
- artifact contract を変える場合は `schemas/`、`examples/artifacts/`、`goldens/` を同時に見る。
- 出力品質が変わる場合は `goldens/`、`docs/evaluation-rubric.md`、forward-test 記録を更新する。
- repo の正本関係は `HUB.codex.md` に集約し、README は AI routing と最短導線を優先する。
- 原典調査や長文メモは `docs/research/` に置き、Skill 本体へ直接詰め込まない。
