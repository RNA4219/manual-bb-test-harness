# 注文キャンセル機能

## Feature

出荷前の注文のみ購入者がキャンセルできる。キャンセル成功時は在庫を戻し、クーポン利用注文ではクーポン残数を復元する。

## Acceptance Criteria

- AC-1: 出荷前の注文のみキャンセルできる。
- AC-2: 出荷済み注文はキャンセル不可メッセージを表示する。
- AC-3: キャンセル成功時は在庫を戻す。
- AC-4: クーポン利用注文ではクーポン残数を復元する。

## Business Rules

- BR-1: 決済失敗注文はキャンセル済み扱いにしない。
- BR-2: 二重キャンセルは不可。
- BR-3: CS 担当は購入者依頼を受けて代理キャンセルできる。

## Changed Areas

- order_detail
- inventory_service
- coupon_service

## Existing Evidence

- unit: order state transition tests exist.
- integration: coupon restoration is not covered.

## Environments

- Web
- iOS
- Android
