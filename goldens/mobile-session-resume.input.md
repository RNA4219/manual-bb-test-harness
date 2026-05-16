# モバイル本人確認送信

## Feature

本人確認書類を撮影して送信する。送信中にアプリがバックグラウンドへ移っても、復帰後に送信状態を再開できる。

## Acceptance Criteria

- AC-1: iOS / Android で本人確認書類を撮影して送信できる。
- AC-2: 送信中にアプリをバックグラウンド化しても、復帰後に送信状態を再開できる。
- AC-3: 通信断が起きた場合は再試行でき、同一書類が重複送信されない。
- AC-4: カメラ権限が拒否された場合は設定案内を表示する。

## Business Rules

- BR-1: 1 申請につき有効な本人確認書類は 1 件のみ。
- BR-2: push 通知から再開した場合も通常起動と同じ申請状態を表示する。

## Changed Areas

- document_capture
- upload_session
- push_resume_router

## Environments

- iOS
- Android

## Mobile Contexts

- foreground
- background_resume
- offline
- push_notification_entry
