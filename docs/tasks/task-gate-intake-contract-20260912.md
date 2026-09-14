---
task_id: 20260912-gate-intake-contract
intent_id: INT-GATE-TEST-BASIS
owner: Codex
status: completed
last_reviewed_at: 2026-09-12
next_review_due: 2026-10-12
---

# Task Seed: 判断材料の欠落と集計漏れをテスト先行で修正する

## 背景

TestRail の R12・R13 に続き、R11、R16、R18 の非有限数値、R20 と、既存の script/package/schema 不整合を修正する。期待値を正して失敗を確認した後に実装を変更する。

## ゴール

必要な判断材料が欠けた入力を成功扱いせず、ケース定義と実績を集計で失わない。Markdown のテストベースを保持し、既存の retired 対応を Gate 2.0 と共存させる。

## 実施対象

1. feature/observations と受入条件の欠落、ID重複、非有限数値の拒否。
2. 結果区分の排他集計。
3. Markdown の階層、繰り返し節、環境の保持と、ACなしの中断。
4. retired の理由・移管先保持、分母除外、package と wrapper と schema の整合。

## 完了条件

- [x] 対象不具合を製品変更前のテストで再現。
- [x] 関連テストと全体 pytest を検証。
- [x] lint、Skill、artifact の検証結果を記録。
- [x] [検収記録](../acceptance/AC-20260912-gate-intake-contract.md)とレビュー対応状況を更新。

## 参照

- [第2回レビュー](../istqb-review-round2-20260912.md)
- [運用](../../RUNBOOK.md)
- [Gate 方針](../../skills/manual-bb-test-harness/references/risk-and-gate-policy.md)
