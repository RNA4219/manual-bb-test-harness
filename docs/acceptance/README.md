---
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: active
last_reviewed_at: 2026-05-16
next_review_due: 2026-10-11
---

# Acceptance Records

`docs/acceptance/` は変更ごとの検収記録を残す場所です。

## 使い方

1. `ACCEPTANCE_TEMPLATE.md` を複製する。
2. `AC-YYYYMMDD-xx.md` 形式で保存する。
3. front matter と本文を埋める。
4. 対応する task seed と相互リンクする。

## 命名規則

- `AC-YYYYMMDD-xx.md`
- 例: `AC-20260516-01.md`

## 必須項目

- front matter
  - `acceptance_id`
  - `task_id`
  - `intent_id`
  - `owner`
  - `status`
  - `reviewed_at`
  - `reviewed_by`
- 本文
  - `## Scope`
  - `## Acceptance Criteria`
  - `## Evidence`
  - `## Verification Result`
