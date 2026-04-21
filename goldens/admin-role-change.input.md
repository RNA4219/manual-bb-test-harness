# 管理者ロール変更機能

## Feature

オーナーはワークスペース内ユーザーのロールを viewer, editor, admin に変更できる。ただし最後の owner は降格できない。

## Acceptance Criteria

- AC-1: owner は member のロールを変更できる。
- AC-2: admin は viewer/editor のロールを変更できるが owner は変更できない。
- AC-3: viewer/editor はロールを変更できない。
- AC-4: 最後の owner は降格できない。
- AC-5: ロール変更後、対象ユーザーの権限が即時反映される。

## Business Rules

- BR-1: 自分自身の owner 降格は禁止。
- BR-2: 招待中ユーザーにはロール変更ではなく招待更新を使う。
- BR-3: 監査ログに actor, target, before_role, after_role を記録する。

## Changed Areas

- workspace_members
- role_policy
- audit_log
- invitation_flow

## Existing Evidence

- unit: role_policy allow/deny tests exist.
- integration: audit_log write is covered.
- e2e: no current e2e coverage.
