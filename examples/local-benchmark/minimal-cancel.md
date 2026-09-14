# 注文取消の小規模比較仕様

## Feature

Webで注文を取り消す。これは生成方式の比較用の合成仕様であり、実案件の品質校正データではない。

## Acceptance Criteria

- AC-1: pending状態の注文は取消後にcancelledと表示される。
- AC-2: shipped状態の注文は取消不可と表示され、状態はshippedのまま維持される。
- AC-3: cancelled状態の注文を再度取り消しても状態は変わらない。

## Business Rules

- BR-1: pendingからcancelledへの取消成功時だけ在庫を注文数量分戻す。再取消で在庫を追加しない。

## Changed Areas

- order_detail
- inventory

## Environments

- Web
