# Task Seeds

このディレクトリには、進行中または計画中のタスク seed を格納します。

## Naming Convention

`task-<description>-YYYYMMDD.md` 形式で命名してください。

例: `task-mobile-docs-release-readiness-20260516.md`

## Template

```markdown
---
task_id: YYYYMMDD-NN
intent_id: INT-XXX
owner: your-handle
status: planned | in_progress | done
last_reviewed_at: YYYY-MM-DD
next_review_due: YYYY-MM-DD
---

# Task Seed: タイトル

## 背景

このタスクが必要な理由。

## ゴール

達成したい状態。

## 実施対象

1. 作業 1
2. 作業 2

## 完了条件

- [ ] 条件 1
- [ ] 条件 2

## 参照

- [関連ドキュメント](../../path/to/doc.md)
```

## Status Flow

`planned` → `in_progress` → `done`

完了したタスクは acceptance record を作成し、このファイルの status を `done` に更新します。
