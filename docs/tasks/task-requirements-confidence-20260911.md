---
task_id: 20260911-requirements-confidence
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: completed
last_reviewed_at: 2026-09-11
next_review_due: 2026-10-11
---

# 要件定義信頼度の評価

要確認項目数等から要件定義の信頼度を評価したい、という依頼。既存936 testsの差分を保持し、[spec-07](../specs/spec-07-requirements-confidence.md)を仕様化してから決定的評価エンジン、CLI、契約・例・検証を実装する。

実装・検証を完了。全1001件、coverage 88.18%、Gate専用107件・91.01%、wheel／sdist smoke成功。[検収記録](../acceptance/AC-20260911-requirements-confidence.md)にサンプル・根拠・制約を記録した。採点のLLM呼出は0回。
