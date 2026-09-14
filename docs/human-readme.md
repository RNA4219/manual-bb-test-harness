# 利用ガイド

セットアップと最小の実行例は [README](../README.md#はじめる) を参照してください。このガイドでは、設計の依頼に必要な情報と、結果の確認方法を説明します。

## 入力を用意する

| 入力 | 記載すること |
|---|---|
| 仕様・受入条件 | 利用者の操作と期待する結果、その根拠となる文書や ID |
| 業務ルール・変更点 | 上限・期限・権限・状態遷移、今回変わる範囲と影響先 |
| 対象環境 | Web / iOS / Android、端末、ネットワーク、実行が必要な構成 |
| 既知の不具合 | 症状、重大度、再発条件、修正・再確認の状況 |
| 実行済みの証跡 | 対象 build、自動テストの suite 結果、手動結果、未実行範囲 |

仕様が決まっていない部分は、そのまま未決事項として渡します。期待結果の根拠を作り足さず、要確認事項・探索チャーター・判定を止める条件として扱います。

RanD の要求候補や文書監査を使う場合は、[RanD 連携](../skills/manual-bb-test-harness/references/rand-integration.md)で設計入力と依頼文を生成できます。

## Skill へ依頼する

```text
./skills/manual-bb-test-harness の $manual-bb-test-harness を使い、
./goldens/order-cancel.input.md の手動ブラックボックステストを設計してください。
根拠付き観点、リスク、優先度、手動ケース、工数、Gate 判定、Go/No-Go brief を作成してください。
仕様が不足している部分は未決事項として残し、確認が必要な内容を示してください。
```

Skill はテスト設計を作成します。CLI は仕様の取り込み、成果物の検証、実行証跡の集計や外部ツールとの入出力を支えます。手動テストの実行結果は、実際に確認してから記録します。

## 設計結果を確認する

出力は「根拠付き観点 → リスク → 優先度 → 手動ケース → 工数 → Gate 判定 → Go/No-Go brief」の順に読みます。

- **根拠と網羅範囲**: 仕様・受入条件から、フロー、状態、ルール、データ、権限、回帰影響まで追跡できるか。
- **ケースと期待結果**: 同値分割・境界値・条件の組合せ・状態遷移が具体化され、期待結果の根拠があるか。
- **優先度と工数**: リスクに応じた実行順になり、準備・実行・証跡保存・再実行の時間が見積もられているか。
- **判断材料**: 未実行、未解決欠陥、未決事項、承認が必要な残余リスクが判断理由に残っているか。

CLI の Gate に渡す JSON は [artifact 契約](../skills/manual-bb-test-harness/references/artifact-contract.md)に従います。入力の版・実行構成・欠陥履歴の扱いは [RUNBOOK](../RUNBOOK.md#gate-の実行)を参照してください。

## サンプルを選ぶ

| 対象 | 入力 | 出力例 |
|---|---|---|
| 注文キャンセル・期限・状態遷移 | [order-cancel](../goldens/order-cancel.input.md) | [設計例](../goldens/order-cancel.expected.md) |
| 管理者の権限変更 | [admin-role-change](../goldens/admin-role-change.input.md) | [設計例](../goldens/admin-role-change.expected.md) |
| モバイルの中断復帰 | [mobile-session-resume](../goldens/mobile-session-resume.input.md) | [設計例](../goldens/mobile-session-resume.expected.md) |

`goldens/` の出力例はレビュー時の基準です。対象仕様が異なる場合は、根拠と網羅範囲に合わせて設計を調整します。iOS / Android が対象なら [mobile pack](../skills/manual-bb-test-harness/references/platform-pack-mobile.md)も参照してください。

## 出力品質を評価する

Skill を改修したときは、[forward-test の手順](../skills/manual-bb-test-harness/references/forward-test.md)と[評価基準](evaluation-rubric.md)を使います。

```powershell
uv run bb-harness run forward-test --input goldens/order-cancel.input.md
```

このコマンドは評価用プロンプトを出力します。生成した設計を採点し、[記録テンプレート](forward-test-report-template.md)に沿って結果を残します。

環境・CLI・成果物検証の失敗は [Failure Triage](../RUNBOOK.md#failure-triage)、全体検証は [RUNBOOK](../RUNBOOK.md#4-repo-全体を検証する)を参照してください。

## 用語

| 用語 | 意味 |
|---|---|
| coverage model | 確認対象をフロー、状態、ルール、データ、権限、回帰影響に分けたモデル |
| oracle | 期待結果を判断する根拠。仕様、受入条件、業務ルールなど |
| artifact | 設計や実行の段階ごとに作る構造化された成果物 |
| Gate | テスト結果、欠陥状態、残余リスクから行うリリース可否の判定 |
| golden | 出力品質をレビューするための入力と出力の例 |
