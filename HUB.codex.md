---
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: active
last_reviewed_at: 2026-05-16
next_review_due: 2026-10-11
release_version: 3.0.0
test_count: 756
knowledge_map: 33 nodes, 45 edges, 33 capsules
---

# manual-bb-test-harness HUB

`HUB_SCOPE_DECLARATION`: 本ファイルの適用範囲は `manual-bb-test-harness/` 全体。

この repo は、手動ブラックボックス QA 設計 Skill の正本を管理する。  
最初に AI-first 入口の `README.md` で task classification を行い、次に目的に応じて下記の正本へ進む。

## 1. 正本ドキュメント

| file | role |
|---|---|
| `README.md` | AI-first 入口、task classification、最短導線 |
| `docs/human-readme.md` | 人間向け概要、利用説明 |
| `BLUEPRINT.md` | 目的、Scope、I/O 契約、主要設計 |
| `RUNBOOK.md` | 実行手順、検証、更新時の確認 |
| `GUARDRAILS.md` | 変更時の運用原則、境界 |
| `EVALUATION.md` | 受入条件、品質基準、検証チェック |
| `SPEC.md` | 実装済み機能と改修履歴の仕様メモ |
| `skills/manual-bb-test-harness/SKILL.md` | Skill 実行時の主導線 |
| `docs/workflow-cookbook/` | 知識マップ (index.json, hot.json, caps/) |
| `docs/tasks/` | Task Seed |
| `docs/acceptance/` | 検収記録 |

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

## 3. 更新ルール

- Skill の振る舞いを変えるときは、`SKILL.md`、参照 docs、schema、example、golden、評価基準を一緒に見る。
- repo の正本関係はこの HUB に集約し、README に詳細仕様を重複させすぎない。
- `SPEC.md` は履歴を含む実装仕様メモとして扱い、運用導線は `RUNBOOK.md` へ寄せる。
- mobile / domain pack のような拡張観点は `references/` に置き、Skill 本体は短く保つ。
- 変更単位の正本は `docs/tasks/`、検収記録は `docs/acceptance/` に置く。
