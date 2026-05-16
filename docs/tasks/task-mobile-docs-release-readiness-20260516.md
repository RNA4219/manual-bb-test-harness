---
task_id: 20260516-01
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: done
last_reviewed_at: 2026-05-16
next_review_due: 2026-06-16
---

# Task Seed: Mobile Docs Release Readiness

## 背景

- `manual-bb-test-harness` は Web 前提から iOS / Android を扱える形へ拡張された。
- 既存 repo には Skill、schema、golden はある一方、`workflow-cookbook` 準拠の正本 docs と検収導線が不足していた。

## ゴール

- mobile 対応を artifact / Skill / golden / ingest に一貫反映する。
- `README -> HUB -> BLUEPRINT / RUNBOOK / GUARDRAILS / EVALUATION` の読み筋を整える。
- repo 自体を `manual-bb-test-harness` で検収し、release readiness を記録する。

## 実施対象

1. `mobile_contexts` と `platform_matrix` の追加
2. mobile platform pack と mobile golden の追加
3. `HUB.codex.md`、`BLUEPRINT.md`、`RUNBOOK.md`、`GUARDRAILS.md`、`EVALUATION.md` の追加
4. `docs/tasks/` と `docs/acceptance/` の運用導線追加
5. self-review と acceptance record の作成
6. 既存 example / export / lockfile の追跡対象化

## 完了条件

- [x] mobile 対応の contract / example / golden が揃う
- [x] repo 正本 docs の読み筋が明示される
- [x] self-review が `go / conditional_go / no_go` で記録される
- [x] `uv run pytest` と validator が通る
- [x] docs に記載する example / export / lockfile が追跡対象に含まれる

## 参照

- [Blueprint](../../BLUEPRINT.md)
- [Runbook](../../RUNBOOK.md)
- [Release Review](../release-review-20260516.md)
- [Acceptance Record](../acceptance/AC-20260516-01.md)
