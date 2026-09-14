---
task_id: 20260912-evidence-lifecycle
intent_id: INT-EVIDENCE-LIFECYCLE
owner: Codex
status: completed
last_reviewed_at: 2026-09-12
next_review_due: 2026-10-12
---

# 実行構成・欠陥状態・自動テスト成否をGateへ追加する

対象はR1、R2、R18の残り。必要構成の未実行、未解決欠陥、suiteの失敗を保持し、誤ったGoを防ぐ。

- [x] 回帰テストを追加し、訂正済みテストを改修前コードの隔離コピーでも再確認する。
- [x] 実行構成、欠陥IDと確認証跡、suite実績の契約と実装を追加する。
- [x] schema、CLI、例、golden、運用文書を揃える。
- [x] 全体テスト・lint・artifact・配布を検証し、[検収記録](../acceptance/AC-20260912-evidence-lifecycle.md)へ残す。
