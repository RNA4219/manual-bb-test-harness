# Task Seeds

`docs/tasks/` は、変更単位ごとの背景、ゴール、完了条件を残す場所です。

## 使い方

1. `TASK_TEMPLATE.md` を複製する。
2. `task-<slug>-YYYYMMDD.md` 形式で保存する。
3. front matter と本文を埋める。
4. 完了後は対応する acceptance record へリンクする。

## 命名規則

- `task-<slug>-YYYYMMDD.md`
- 例: `task-mobile-docs-release-readiness-20260516.md`

## 必須項目

- front matter
  - `task_id`
  - `intent_id`
  - `owner`
  - `status`
  - `last_reviewed_at`
  - `next_review_due`
- 本文
  - `## 背景`
  - `## ゴール`
  - `## 実施対象`
  - `## 完了条件`
