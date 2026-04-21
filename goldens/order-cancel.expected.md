# Expected Review Anchors

この golden は完全一致ではなく、Skill 出力レビュー用の期待アンカー。

## Required Coverage Items

- 状態: pending, shipped, cancelled, payment_failed
- 無効遷移: shipped -> cancelled, cancelled -> cancelled, payment_failed -> cancelled
- ルール組合せ: order_state x coupon_used x actor
- 権限: buyer own order, buyer other user's order, CS delegated cancellation
- 回帰: inventory_service, coupon_service, order_detail
- 品質 lens: 二重実行、外部サービス失敗、復帰性、エラーメッセージ

## Required Observations

- 出荷済み注文はキャンセル不可。
- キャンセル成功時に在庫が戻る。
- クーポン利用時にクーポン残数が戻る。
- 二重キャンセルが拒否される。
- 決済失敗注文がキャンセル済み扱いにならない。
- CS 代理キャンセルと購入者本人キャンセルの差分。

## Required Risk Shape

- 出荷済み注文がキャンセルできるリスクは P1 以上。
- 在庫またはクーポン復元漏れは P1 以上。
- 二重キャンセルによる重複復元は P1 以上。
- UI 文言のみの軽微な問題は P2 以下でもよい。

## Required Case Shape

- scripted case には oracle refs がある。
- 仕様根拠が薄い UX 妥当性は探索チャーターに落とす。
- P0/P1 ケースが state, rule, role, regression を横断する。
- 工数には evidence capture と retry buffer が含まれる。

## Gate Expectations

- coupon restoration の integration evidence がないことを residual risk に残す。
- P0/P1 未実行なら Go にしない。
- waiver がある場合は owner, due date, containment を要求する。
