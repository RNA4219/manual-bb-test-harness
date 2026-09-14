---
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: active
last_reviewed_at: 2026-05-16
next_review_due: 2026-10-11
release_version: 2.0.0
---

# manual-bb-test-harness HUB

`HUB_SCOPE_DECLARATION`: 本ファイルの適用範囲は `manual-bb-test-harness/` 全体。

この repo は、手動ブラックボックス QA 設計 Skill の正本を管理する。  
最初に [README](README.md) で概要と始め方を確認し、目的に応じて下記の正本へ進む。

## 1. 正本ドキュメント

| file | role |
|---|---|
| [README.md](README.md) | 概要、始め方、目的別の文書案内 |
| [docs/human-readme.md](docs/human-readme.md) | 入力の準備、設計結果の確認、サンプルと用語 |
| [BLUEPRINT.md](BLUEPRINT.md) | 目的、Scope、I/O 契約、主要設計 |
| [RUNBOOK.md](RUNBOOK.md) | 実行手順、検証、更新時の確認 |
| [GUARDRAILS.md](GUARDRAILS.md) | 変更時の運用原則、境界 |
| [EVALUATION.md](EVALUATION.md) | 受入条件、品質基準、検証チェック |
| [SPEC.md](SPEC.md) | 実装済み機能と改修履歴の仕様メモ |
| [CHANGELOG.md](CHANGELOG.md) | 変更履歴、検証記録への参照 |
| [skills/manual-bb-test-harness/SKILL.md](skills/manual-bb-test-harness/SKILL.md) | Skill 実行時の主導線 |
| [docs/workflow-cookbook/](docs/workflow-cookbook/) | 知識マップ (index.json, hot.json, caps/) |
| [docs/tasks/](docs/tasks/) | Task Seed |
| [docs/acceptance/](docs/acceptance/) | 検収記録 |

## 2. 目的別の読み順

### Skill を使いたい

1. `README.md`
2. `skills/manual-bb-test-harness/SKILL.md`
3. 必要な `skills/manual-bb-test-harness/references/*.md`
4. `goldens/` と `docs/evaluation-rubric.md`

### repo を保守したい

1. `README.md`
2. `BLUEPRINT.md`
3. `GUARDRAILS.md`
4. `RUNBOOK.md`
5. `EVALUATION.md`
6. `SPEC.md`
7. 必要に応じて `docs/tasks/` と `docs/acceptance/`
8. ドキュメント間関係を確認する場合は `docs/workflow-cookbook/index.json`

### artifact 契約を変えたい

1. `BLUEPRINT.md`
2. `skills/manual-bb-test-harness/references/artifact-contract.md`
3. `schemas/`
4. `examples/artifacts/`
5. `goldens/`
6. `EVALUATION.md`

### mobile 対応を確認したい

1. `README.md`
2. `skills/manual-bb-test-harness/references/platform-pack-mobile.md`
3. `goldens/mobile-session-resume.input.md`
4. `goldens/mobile-session-resume.expected.md`

### RanDと連携したい

1. `skills/manual-bb-test-harness/references/rand-integration.md`
2. `docs/tasks/task-rand-integration-20260912.md`
3. `goldens/rand-integration.expected.md`

## 3. 更新ルール

- Skill の振る舞いを変えるときは、`SKILL.md`、参照 docs、schema、example、golden、評価基準を一緒に見る。
- repo の正本関係はこの HUB に集約し、README に詳細仕様を重複させすぎない。
- `SPEC.md` は履歴を含む実装仕様メモとして扱い、運用導線は `RUNBOOK.md` へ寄せる。
- mobile / domain pack のような拡張観点は `references/` に置き、Skill 本体は短く保つ。
- 変更単位の正本は `docs/tasks/`、検収記録は `docs/acceptance/` に置く。
