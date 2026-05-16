# Expected Review Anchors

この golden は mobile 対応の review anchor。

## Required Coverage Items

- `platform_matrix`: iOS / Android、foreground / background_resume、offline / online recovery、push entry
- 権限: camera allowed / denied
- 状態: idle, capturing, uploading, retry_wait, submitted
- 無効遷移: submitted -> uploading, uploading -> duplicate_submit
- 回帰: document_capture, upload_session, push_resume_router
- 品質 lens: recovery, compatibility, idempotency, permission handling

## Required Observations

- background 復帰後に送信状態を再開できる。
- offline 後の再試行で重複送信されない。
- camera denied 時に設定案内が表示される。
- push 経由と通常起動で申請状態が一致する。

## Required Risk Shape

- 重複送信、復帰失敗、誤った申請状態表示は P1 以上。
- camera denied 時の案内欠落は P2 以上。

## Required Case Shape

- scripted case に `OS x lifecycle x network` の根拠が見える。
- background / offline / permission は少なくとも 1 件ずつ P1/P2 case または charter に現れる。
- 端末差だけで oracle が薄い観点は探索チャーターへ落とす。

## Gate Expectations

- iOS / Android の代表端末実行証跡が未了なら Go にしない。
- push entry の oracle が未確定なら `degraded` または `conditional_go` を検討する。
