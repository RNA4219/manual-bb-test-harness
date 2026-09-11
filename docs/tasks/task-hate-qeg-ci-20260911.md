---
task_id: 20260911-hate-qeg-ci
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: in_progress
last_reviewed_at: 2026-09-11
next_review_due: 2026-10-11
---

# HATE・QEGをCIへ組み込む

「HATEとQEG組み込んで緑CIにして」という依頼。[spec-08](../specs/spec-08-hate-qeg-ci.md)を先に定義し、既存改修を保持してCI証跡収集・変換・判定・artifact保存を実装する。ローカル契約検証後にGitHub Actionsの実runを確認する。

実装とローカル検証は完了。全1026件・coverage 88.18%、Gate専用107件・91.01%、HATE export成功、QEG go、配布smoke成功。[検収記録](../acceptance/AC-20260911-hate-qeg-ci.md)を参照。専用ブランチ`agent/hate-qeg-ci`へのpushが自動承認レビューで拒否されたため、ユーザーの承認待ち。GitHubの緑CIは未確認。
