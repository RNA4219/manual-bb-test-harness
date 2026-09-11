# 要件信頼度の実案件調整

現行の点数は運用ルールによる評価です。実案件データによる重み・閾値の校正はまだ行っていません。
分析補助ツールは観測記録を比較し、既存の採点policyやGateを変更しません。

## 記録手順

1. 実装前の要件評価を実行し、`requirements_confidence.json`を変更せず保存します。
2. 社名・個人名を含まない案件IDを付けます。1案件につき事前に選んだ1回の評価だけを使います。
3. 後日の結果を見る前に、案件を`calibration`と`holdout`へ分けます。同案件を両群へ入れません。
4. 全案件で同じ日数（初期例は30日）の観測窓を決めます。実装ミス一般と分け、要件漏れ・曖昧さ・矛盾に起因した不具合と手戻り時間を記録します。定義や検出方法も案件間で揃えてください。
5. 窓が終了して記録が揃うまでは`complete=false`、件数と時間を`null`にします。「記録なし」を0へ変えません。
6. snapshotのSHA-256、日付、結果をdatasetへ記入して分析します。snapshotの本文は集計結果へ転記しません。公開repoには実案件データを入れないでください。

## 入力形式

`examples/requirements-calibration/dataset.json`はデータなしの開始用です。
snapshotはdatasetと同じディレクトリ以下へ保存し、相対パスで参照します。

```json
{
  "data_kind": "real",
  "window_days": 30,
  "cases": [{
    "project_id": "project-001",
    "split": "calibration",
    "evaluated_at": "2026-09-01",
    "window_end": "2026-10-01",
    "report_path": "snapshots/project-001.json",
    "report_sha256": "保存したsnapshotファイルのSHA-256（64桁）",
    "complete": false,
    "defects": null,
    "rework_hours": null
  }]
}
```

模擬データでは`data_kind=synthetic`を必ず使います。上の1件例は記入方法の説明であり、実測データではありません。

```powershell
uv run python tools/analyze_requirements_outcomes.py --input path/to/dataset.json --output tmp/calibration-study
```

出力先は新規ディレクトリを指定します。`analysis.json`に入力datasetのhash、件数、
除外理由、帯別集計、相関、閾値比較が出ます。`summary.md`は人が読む要約です。

## 調整の判断

候補閾値は60/70/80/85/90。点数が閾値未満なら追加確認対象とします。
陽性は観測窓に要件起因の不具合または手戻りがあった案件です。
調整群で見逃し5・過剰警告1の損失を最小化し、同点なら見逃しが少なく、現行85に近い候補を選びます。
保留群は候補選択に使用せず、選んだ候補と85を比較します。

調整20案件・保留10案件以上、各群の陽性と陰性がそれぞれ3案件以上という条件は探索の最低条件です。
条件成立は統計的な精度保証ではありません。相関は因果関係を示さず、点数を正しさの確率へ変換しません。
模擬データや不足データでは候補を出しません。十分なデータでも結果は提案に留めます。
重大事項の上限やReady条件は維持し、重み変更は別途検証して仕様へ反映します。
