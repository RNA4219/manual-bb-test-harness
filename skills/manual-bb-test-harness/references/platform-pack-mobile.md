# Platform Pack: Mobile

## 使う条件

`feature_spec.devices` に `iOS`、`Android`、`mobile` のいずれかが含まれるときに読む。

## 追加で正規化する項目

- `mobile_contexts`: `foreground`、`background_resume`、`cold_start`、`offline`、`online_recovery`、`push_notification_entry`、`deep_link_entry`
- 権限差: `notification_allowed / notification_denied`、必要に応じて `camera / location / photo`
- 配布状態: `fresh_install`、`upgrade_install`
- OS / 端末差: iOS / Android、画面サイズ、OS バージョンの代表値

## Coverage Checklist

| lens | prompts |
|---|---|
| lifecycle | 起動、バックグラウンド化、復帰、強制終了後再起動で状態が壊れないか |
| interruption | 通話、通知、画面ロック、アプリ切替、権限ダイアログで中断されても復帰できるか |
| connectivity | offline、低速、瞬断、復帰後再送、重複送信防止 |
| entrypoint | push、deep link、通常起動で同じ業務結果へ到達するか |
| permission | 許可、拒否、後から変更、OS 設定からの復帰 |
| compatibility | iOS / Android、代表端末、OS バージョン差で主要導線が崩れないか |
| install_state | fresh install、upgrade install、既存セッション保持 |

## Case / Charter ルール

- `platform_matrix` には最低でも `OS x lifecycle x network` の代表組合せを置く。
- 主要業務導線は scripted case で守り、互換性や端末依存の探索は charter に分ける。
- push / deep link が入口になる機能は、通常起動との差分を first-class に扱う。
- background 中断と offline 復帰は、送信系操作では idempotency と組み合わせて確認する。
- 仕様根拠がない UX 妥当性や端末差は scripted case に押し込まず、`[要確認]` を残した charter に落とす。

## 典型リスク

- 復帰後に二重送信される
- offline 中の操作が黙って失われる
- push / deep link 経由だけ権限や初期化順が異なる
- OS 権限拒否後の再試行導線が詰まる
- upgrade install 後だけ古いキャッシュが残る

## Intake 判定

- `degraded`: 対象 OS、主要端末、通知 / 権限 / network 条件のいずれかが不足しているが、主経路の black-box case は作れる。
- `blocked`: push / deep link / permission が主要要件なのに oracle がない、または mobile 固有の状態遷移が仕様上未定義で主要業務結果を判定できない。
