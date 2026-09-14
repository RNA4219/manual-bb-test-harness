# Expected Review Anchors

この golden は完全一致ではなく、Skill 出力レビュー用の期待アンカー。

## Required Coverage Items

- 状態: pending, shipped, cancelled, payment_failed
- 無効遷移: shipped -> cancelled, cancelled -> cancelled, payment_failed -> cancelled
- ルール組合せ: order_state x coupon_used x actor
- 権限: buyer own order, buyer other user's order, CS delegated cancellation
- 回帰: inventory_service, coupon_service, order_detail
- mobile 対象: iOS / Android の代表 platform_matrix
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
- 自動テストへ移管済みの手動ケースは `status: retired`、`retired_reason`、`replacement_refs`、必要に応じて `placement_change_ref` を持つ。

## Gate Expectations

- coupon restoration の代替 integration evidence と観点との対応を確認する。代替参照だけで検証完了にしない。
- P0/P1 未実行なら Go にしない。
- retired case は P0/P1 未実行とは区別し、gate output の `retired_cases` に残す。
- Gate には `build_id` と `evidence_summary` を含め、仕様・観点・自動テスト証跡を必須入力にする。
- waiver はリスクに結び付いた明示的な承認記録とし、`owner`、`expires_at`、`containment`、`rollback` を要求する。
- 必須観点の未検証や証跡不足が残る場合は `no_go` とし、理由と不足条件を示す。

### No-Go example の条件

`examples/artifacts/order-cancel.gate_decision.json` は waiver を指定せず生成した例。TC-001、TC-002、CHARTER-001 は pass、TC-003 は retired で、必須観点の実行率は 2/3（66.7%）。代替参照だけで OBS-DATA-01 を完了扱いにしないため No-Go となる。既存 waiver sample を明示的に渡す場合の条件付き判定は、この未承認シナリオと区別する。

## 実行証跡の保持

- 構成を計画したcaseは全対象構成のpassを要求し、構成ごとの未実行と失敗を残す。
- 再実行passだけで未解決欠陥を閉じない。ID付き台帳と解決時点の確認証跡を照合する。
- 自動証跡には必須suiteの成否・件数・出典を含める。カバレッジだけで合格にしない。
- Gateのevidence_summaryはmanual_execution_results、open_defects、automation_test_suitesを含める。
- これらを同時に確認する例は[evidence-lifecycle](../examples/evidence-lifecycle/)。
