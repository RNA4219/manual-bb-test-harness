# Output Templates

## Markdown Response

```md
## Intake Status
- status: ok | degraded | blocked
- assumptions:
- blockers:

## 根拠付き観点
| id | coverage_item | mandatory | title | view | techniques | source | rationale |
|---|---|---|---|---|---|---|---|

## Coverage Model
- data_partitions:
- boundaries:
- rule_columns:
- states:
- valid_transitions:
- invalid_transitions:
- role_matrix:
- regression_edges:
- quality_lenses:

## リスク
| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|

## 手動テストケース
| tc_id | priority | title | preconditions | steps | expected | oracle | trace_to | minutes |
|---|---|---|---|---|---|---|---|---:|

## 探索チャーター
| id | priority | title | scope | questions | trace_to | minutes |
|---|---|---|---|---|---|---:|

## 工数
- prep:
- execution:
- evidence:
- retry buffer:
- total:

## Gate
- profile:
- decision: go | conditional_go | no_go
- reasons:
- blocking_risks:
- waivers:

## Go/No-Go Brief
- feature:
- decision:
- top risks:
- coverage gaps:
- evidence:
- residual risk:
- required follow-up:
```

## Release Brief

```md
# Release Brief

## Summary
- feature:
- decision: go | conditional_go | no_go
- residual_risk:
- top_risks:

## Evidence
- auto_gate:
- manual_execution:
- open_defects:

## Waivers
- id:
- owner:
- expires_at:
- containment:

## Required Follow-up
- item:
- due:
```

## Execution Evidence

```json
{
  "run_id": "RUN-2026-04-22-0017",
  "tc_id": "TC-001",
  "feature_id": "FEATURE-001",
  "build_id": "web-1.42.0+1289",
  "env": "stg",
  "device": "iPhone 15 / iOS 18.4",
  "network_profile": "4g-lossy",
  "tester": "qa_a",
  "oracle_type": "specified",
  "oracle_refs": ["AC-2"],
  "expected": ["キャンセル不可メッセージを表示"],
  "actual": ["注文状態が cancelled へ遷移した"],
  "result": "fail",
  "attachments": ["s3://evidence/RUN-001/step2.png"],
  "anomaly_notes": ["出荷済み状態でも CTA が活性だった"],
  "defect_stub": {
    "title": "出荷済み注文がキャンセル可能",
    "severity": "high"
  }
}
```
