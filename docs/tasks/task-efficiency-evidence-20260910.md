---
task_id: 20260910-efficiency
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: completed
last_reviewed_at: 2026-09-10
next_review_due: 2026-10-11
---

# 生成効率と証跡版の追加実装

ユーザー承認済みの追加4点を、[spec-05](../specs/spec-05-efficient-generation-evidence-revisions.md)へ先に反映してから実装する。

開始時点はISTQB拡張の未コミット差分を含む835 tests版。前段の原本・コード・検収記録を保持する。
実装順: 契約 → 消費量と予算 → compact生成 → 版照合 → 回帰 → 実モデル小規模比較 → 条件成立時の9-run。

[検収記録](../acceptance/AC-20260910-efficiency.md)

仕様の8受入項目を確認。全898 tests、coverage 87.07%、Gate 90.94%、wheel/sdist、Skill/schema/spec/freshnessは成功。実LLMは両runともJSON出力未完了のため削減率null、9-runを見送った。分割生成は検収記録の残る評価課題として明示。
