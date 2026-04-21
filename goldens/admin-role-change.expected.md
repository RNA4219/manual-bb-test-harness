# Expected Review Anchors

## Required Coverage Items

- role matrix: actor_role x target_role x ownership_context x target_state
- 境界: 最後の owner / 複数 owner
- 状態: active member / invited user / suspended user
- 回帰: role_policy, audit_log, invitation_flow
- 品質 lens: 即時反映、監査可能性、エラーメッセージ、セッション更新

## Required Observations

- owner は member のロールを変更できる。
- admin は owner を変更できない。
- viewer/editor は変更操作できない。
- 最後の owner 降格は禁止。
- invited user は招待更新へ誘導される。
- 監査ログに before/after が残る。
- 変更後の対象ユーザー権限が即時反映される。

## Required Risk Shape

- 権限昇格または不正降格は P0 または P1。
- 監査ログ欠落は P1 以上。
- 即時反映遅延は影響範囲により P1/P2。

## Required Case Shape

- role x action x resource_state x ownership_context が明示される。
- 最後の owner は境界値として扱われる。
- invited user は通常 member と分ける。
- audit_log は gray evidence として補助扱いにする。
