# 注文キャンセル: リスク表の検算の例

`bb-harness check risk --input examples/markdown/order-cancel.risk-table.md` が終了コード 0 になる例。
点数と優先度は `bb_harness.risk_policy` で計算した値で、手計算の値ではない。

## リスク

| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|
| RISK-01 | 出荷済みの注文がキャンセルできてしまう | 5 | 4 | D2 C2 X1 P1 A0 | 74 | P0 | 売上・配送・返金の整合が崩れる。状態の判定を変更した |
| RISK-02 | pending の注文をキャンセルしても在庫が戻らない | 4 | 4 | D2 C2 X2 P0 A0 | 61 | P1 | 在庫の連携先に依存し、画面からは気づきにくい |
| RISK-03 | 同じ注文を二重にキャンセルして返金が重なる | 4 | 3 | D2 C2 X1 P0 A2 | 44 | P2 | 再送の防止は自動テストが通っているので A=2 とした |
| RISK-04 | クーポンの残数が戻らない | 3 | 3 | D2 C1 X0 P0 A1 | 32 | P3 | 影響はクーポンの利用回数に留まる |
