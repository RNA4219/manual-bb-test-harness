# Spec: テスト結果インポート

## 概要

TestRail/Xrayから実行結果をインポートし、execution_evidence.json形式に変換。gate判定の入力データとして活用。

## 目的

- 手動テスト実行結果の自動収集
- Gate判定のデータソース拡張
- テスト管理システムとの双方向連携
- 重複入力作業の排除

## 要件

### R1: TestRailインポート

| id | 要件 | 優先度 |
|---|---|---|
| R1.1 | TestRail API v2接続 | P0 |
| R1.2 | Test Run結果取得 | P0 |
| R1.3 | status変換（passed→pass、failed→fail等） | P0 |
| R1.4 | custom_fieldsからdevice/env抽出 | P1 |
| R1.5 | attachments URL抽出 | P1 |

### R2: Xray（Jira）インポート

| id | 要件 | 優先度 |
|---|---|---|
| R2.1 | Xray API接続（Cloud/Server） | P0 |
| R2.2 | Test Execution結果取得 | P0 |
| R2.3 | status変換（PASS/FAIL/ABORTED等） | P0 |
| R2.4 | TestRunからdefect Jira issue抽出 | P1 |
| R2.5 | evidence attachments抽出 | P1 |

### R3: 出力形式

| id | 要件 | 優先度 |
|---|---|---|
| R3.1 | execution_evidence.json形式出力 | P0 |
| R3.2 | 複数run結果を配列出力 | P0 |
| R3.3 | tc_id/charter_id mapping | P0 |
| R3.4 | 欠陥ID単位のdefects配列と互換stub生成（fail時） | P1 |

### R4: 設定・認証

| id | 要件 | 優先度 |
|---|---|---|
| R4.1 | 環境変数認証（API token） | P0 |
| R4.2 | project_id/run_id指定 | P0 |
| R4.3 | incremental import（日付範囲） | P1 |
| R4.4 | dry-runモード（API呼び出しのみ） | P1 |

## 設計

### TestRail API Mapping

```
TestRail API                        execution_evidence.json
────────────────────────────────────────────────────────────────
GET /get_tests/{run_id}            → 各テストの run_id, tc_id
  .tests[].status_id               → result
    1=passed    → pass
    2=blocked   → blocked  
    3=untested  → skip
    4=retest    → skip
    5=failed    → fail
    
  .tests[].assigned_to_id          → tester (lookup user)

GET /get_results/{test_id}         → 最新結果1件（results[0]）
  .custom_fields                   → device, env, network_profile
  .elapsed                         → time_spent_minutes
  .defects[]                       → defects[] / defect_stub（先頭互換）
  
GET /get_attachments/{test_id}     → attachments[]（将来要件・未実装）
```

標準ステータス ID は [TestRail Statuses API](https://support.testrail.com/hc/en-us/articles/7077935129364-Statuses) に従う。
Retest を `skip` へ変換するのは本ツールの証跡形式への対応であり、再テスト完了を意味しない。

`get_tests` は `tests` 配列を含むページ応答を読み、`_links.next` がなくなるまで同じ run の全ページを取得する。
次ページは同じ API endpoint の相対リンクだけを受け入れ、循環リンクはエラーとする。
`get_results` は `results` 配列を含む応答を読み、API が新しい順に返す先頭1件を採用する。
両 API とも旧形式の配列応答を許容する。
詳細は [Tests API](https://support.testrail.com/hc/en-us/articles/7077990441108-Tests) と
[Results API](https://support.testrail.com/hc/en-us/articles/7077819312404-Results) を参照。

通信失敗、JSON 解析失敗、想定外の応答構造は取り込みエラーとして中断する。
全テストと必要な結果詳細の取得が成功した後に証跡を書き出し、取得途中の失敗では既存の出力を変更しない。
正常な空の結果配列は許容する。担当ユーザー名の取得失敗時は、従来どおりユーザー ID で代替する。
この中断・出力方針は本ツールの契約である。

### Xray API Mapping

```
Xray API                           execution_evidence.json
────────────────────────────────────────────────────────────────
GET /testexec/{exec_key}/tests     → run_id, tc_id
  .status                          → result
    PASS      → pass
    FAIL      → fail
    ABORTED   → blocked
    TODO      → skip
    EXECUTING → unknown
    
  .executed_by                     → tester
  .startedOn/finishedOn            → timestamp
  .testRun.evidences[]              → attachments[]
  .testRun.defects[]               → defects[] / defect_stub（先頭互換）
  
GET /test/{test_key}               → oracle_refs, trace_to
```

### import-testrail.py設計

変換の正本は`src/bb_harness/tools/import_testrail.py`。以下は取得済みの説明用データを変換する例で、APIへの接続は行わない。

```python
from bb_harness.tools.import_testrail import convert_to_execution_evidence

evidence = convert_to_execution_evidence(
    {"id": 100, "case_id": 42, "status_id": 5},
    {"defects": ["BUG-1", "BUG-2"]},
    tester_name="qa",
    run_id=1234,
    feature_id="ORDER-CANCEL",
)
assert evidence["result"] == "fail"
assert [item["defect_id"] for item in evidence["defects"]] == ["BUG-1", "BUG-2"]
```

### import-xray.py設計

変換の正本は`src/bb_harness/tools/import_xray.py`。

```python
from bb_harness.tools.import_xray import convert_to_execution_evidence

evidence = convert_to_execution_evidence(
    {"status": "FAIL", "defects": ["BUG-1", "BUG-2"]},
    exec_key="QA-EXEC-1",
    test_key="QA-TEST-1",
    feature_id="ORDER-CANCEL",
)
assert evidence["result"] == "fail"
assert [item["defect_id"] for item in evidence["defects"]] == ["BUG-1", "BUG-2"]
```

両importerともfailで受領した全欠陥IDを`defects[]`へ保持し、先頭を互換用`defect_stub`にも出す。重複IDは除き、文字列の場合はカンマ区切りも受け付ける。欠陥の重大度は従来どおり既定high、状態はopen。

importは受領した実行結果の変換であり、外部trackerの全未解決欠陥を自動同期する機能ではない。継続する欠陥と解決確認は`defect_register`で管理し、履歴・確認証跡とともにGateへ渡す。詳しくは[artifact契約](../../skills/manual-bb-test-harness/references/artifact-contract.md#実行構成と欠陥履歴)を参照。

## インターフェース

### CLI

```bash
# TestRail
export TESTRAIL_URL="https://example.testrail.io"
export TESTRAIL_USER="qa_lead"
export TESTRAIL_API_KEY="xxx"

python scripts/import-testrail.py \
    --project 12 \
    --run 1234 \
    --output examples/artifacts/execution_evidence/

# Xray
export JIRA_URL="https://example.atlassian.net"
export JIRA_USER="qa_lead"  
export JIRA_API_KEY="xxx"

python scripts/import-xray.py \
    --exec PROJ-TE-123 \
    --output examples/artifacts/execution_evidence/

# 日付範囲指定（incremental）
python scripts/import-testrail.py \
    --project 12 \
    --date-range 2026-04-01 2026-04-30 \
    --output examples/artifacts/execution_evidence/

# Gate判定連携
python scripts/import-testrail.py --project 12 --run 1234 --output /tmp/
python scripts/evaluate-gate.py --evidence /tmp/ --risk risk.json --cases cases.json --feature feature.json --observations observations.json --automation automation.json --defects defects.defect_register.json --output gate.json
```

### 出力ファイル構造

```
execution_evidence/
├── TC-001.json      # TestRail/Xray test result
├── TC-002.json
├── TC-003.json
├── CHARTER-001.json # Exploratory charter result (if exists)
└── summary.json     # Import summary
    {
      "source": "testrail",
      "project_id": 12,
      "run_id": 1234,
      "imported_count": 25,
      "pass_count": 20,
      "fail_count": 3,
      "skip_count": 2,
      "import_timestamp": "2026-05-04T..."
    }
```

## 制約

- TestRail API v2使用
- Xray Cloud/Server API使用（認証方式差異対応）
- ネットワークアクセス必須
- API rate limit遵守（TestRail: 180req/min）
- pagination対応（大規模run）

## テスト観点

| 观点 | ケース |
|---|---|
| 正常系 | TestRail run import成功 |
| 正常系 | Xray exec import成功 |
| 異常系 | API token未設定 → error |
| 畾常系 | network timeout → retry |
| 正常系 | status変換pass→pass、fail→fail |
| 正常系 | defect_stub生成（fail時） |
| 正常系 | 日付範囲incremental import |
| 正常系 | dry-runでAPI呼び出しのみ |

## 受入基準

- [x] import-testrail.py作成
- [x] import-xray.py作成
- [x] TESTRAIL_API_KEY環境変数認証
- [x] JIRA_API_KEY環境変数認証
- [x] execution_evidence.json形式出力
- [x] gate判定スクリプト連携確認
- [x] `--dry-run` が API token 未設定でも preview モードで成功（PLAN-IMPORT-02 @ 2026-05-30）
- [x] `bb-harness import testrail/xray` wrapper 経由で dry-run が動作（PLAN-IMPORT-03 @ 2026-05-30）
- [x] `tests/test_import_status.py` で TestRail/Xray の status/priority map 全分岐と convert 関数を検証（PLAN-IMPORT-01 @ 2026-05-30）
- [x] import 出力が `execution_evidence.schema.json` で検証可能、`timestamp` を schema に追加（PLAN-IMPORT-04 @ 2026-05-30）
- [x] `RUNBOOK.md` に import/export CLI 手順を追記、本specを更新（PLAN-IMPORT-05 @ 2026-05-30）
