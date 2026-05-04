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
| R3.4 | defect_stub生成（fail時） | P1 |

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
GET /get_test/{test_id}            → run_id, tc_id
  .status_id                       → result
    1=passed    → pass
    2=blocked   → blocked  
    3=untested  → skip
    4=failed    → fail
    5=retest    → skip
    
  .assigned_to_id                  → tester (lookup user)
  .custom_fields                   → device, env, network_profile
  .elapsed                         → time_spent_minutes
  . defects[]                      → defect_stub
  
GET /get_attachments/{test_id}     → attachments[]
```

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
  .testRun.defects[]               → defect_stub
  
GET /test/{test_key}               → oracle_refs, trace_to
```

### import-testrail.py設計

```python
"""Import TestRail test results to execution_evidence format.

Usage:
    python scripts/import-testrail.py --project <id> --run <id> --output <dir>
    python scripts/import-testrail.py --project <id> --date-range <start> <end> --output <dir>

Environment:
    TESTRAIL_URL: https://company.testrail.io
    TESTRAIL_USER: username
    TESTRAIL_API_KEY: API token

Example:
    python scripts/import-testrail.py \
        --project 12 \
        --run 1234 \
        --output examples/artifacts/execution_evidence/
"""

def import_testrail_results(project_id: int, run_id: int) -> list[dict]:
    """Fetch TestRail results and convert to execution_evidence."""
    results = []
    
    # Fetch tests in run
    tests = get_tests(run_id)
    
    for test in tests:
        evidence = {
            "run_id": f"TR-RUN-{run_id}-{test['id']}",
            "tc_id": map_tc_id(test['case_id']),  # Map to TC-XXX
            "feature_id": map_feature_id(test['case_id']),
            "tester": get_username(test['assigned_to_id']),
            "result": map_status(test['status_id']),
            ...
        }
        
        # Add defect if failed
        if evidence['result'] == 'fail':
            defects = get_test_defects(test['id'])
            if defects:
                evidence['defect_stub'] = {
                    'title': defects[0]['title'],
                    'severity': map_severity(defects[0]['priority_id'])
                }
        
        results.append(evidence)
    
    return results
```

### import-xray.py設計

```python
"""Import Xray test results to execution_evidence format.

Usage:
    python scripts/import-xray.py --exec <key> --output <dir>
    python scripts/import-xray.py --project <key> --date-range <start> <end> --output <dir>

Environment:
    JIRA_URL: https://company.atlassian.net
    JIRA_USER: username
    JIRA_API_KEY: API token

Example:
    python scripts/import-xray.py \
        --exec PROJ-TE-123 \
        --output examples/artifacts/execution_evidence/
"""

def import_xray_results(exec_key: str) -> list[dict]:
    """Fetch Xray results and convert to execution_evidence."""
    results = []
    
    # Fetch test execution
    exec_data = get_test_execution(exec_key)
    
    for testrun in exec_data['tests']:
        evidence = {
            "run_id": f"XRAY-{exec_key}-{testrun['test']['key']}",
            "tc_id": testrun['test']['key'],  # Jira test issue key
            "feature_id": map_feature_id(testrun['test']['key']),
            "tester": testrun['executed_by'],
            "result": map_xray_status(testrun['status']),
            ...
        }
        
        # Add defect if failed
        if evidence['result'] == 'fail' and testrun.get('defects'):
            evidence['defect_stub'] = {
                'title': get_jira_issue_title(testrun['defects'][0]),
                'severity': map_jira_priority(testrun['defects'][0])
            }
        
        results.append(evidence)
    
    return results
```

## インターフェース

### CLI

```bash
# TestRail
export TESTRAIL_URL="https://company.testrail.io"
export TESTRAIL_USER="qa_lead"
export TESTRAIL_API_KEY="xxx"

python scripts/import-testrail.py \
    --project 12 \
    --run 1234 \
    --output examples/artifacts/execution_evidence/

# Xray
export JIRA_URL="https://company.atlassian.net"
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
python scripts/evaluate-gate.py --input /tmp/ --risk risk.json --cases cases.json --output gate.json
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

- [ ] import-testrail.py作成
- [ ] import-xray.py作成
- [ ] TESTRAIL_API_KEY環境変数認証
- [ ] JIRA_API_KEY環境変数認証
- [ ] status変換100%正確
- [ ] execution_evidence.json形式出力
- [ ] gate判定スクリプト連携確認
- [ ] dry-runモード動作