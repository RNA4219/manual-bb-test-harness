# Acceptance Records

このディレクトリには、完了したタスクの acceptance records を格納します。

## Naming Convention

`AC-YYYYMMDD-NN.md` 形式で命名してください。

例: `AC-20260530-01.md`

## Template

```markdown
---
acceptance_id: AC-YYYYMMDD-NN
task_id: TASK-ID
intent_id: INT-XXX
owner: your-handle
status: approved
reviewed_at: YYYY-MM-DD
reviewed_by: reviewer-name
---

# Acceptance Record: タイトル

## Scope

- 対象変更
- 非対象

## Acceptance Criteria

- [x] 基準 1
- [x] 基準 2

## Evidence

- 実行コマンド
- テスト結果
- 参照ドキュメント

## Decision

**Approved**: 理由
```

## Archive

古い acceptance records も保持し、履歴として参照可能にします。
