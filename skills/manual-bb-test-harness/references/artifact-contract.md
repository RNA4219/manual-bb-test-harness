# Artifact Contract

## Suite Manifest

```yaml
suite_id: manual-bb-harness
version: 0.1.0
primary_view: black
critical_multi_run: 3
normal_multi_run: 1
merge_strategy: weighted_union
policies:
  require_source_refs: true
  require_oracle_per_case: true
  require_traceability: true
  degrade_on_missing_info: true
  block_on_missing_critical_oracle: true
  white_view_is_supplementary: true
```

## Core Artifacts

Use these artifacts in order.

| artifact | purpose | produced by |
|---|---|---|
| `feature_spec` | 仕様、AC、業務ルール、変更点、環境、前提を正規化する | `normalize_intake` |
| `test_model` | flow/state/rule/data/role/regression の coverage item を表す | `model_test_surface` |
| `observation_set` | 根拠付き観点を表す | `derive_observations` |
| `risk_register` | 各観点やシナリオのリスクと優先度を表す | `assess_risk` |
| `manual_case_set` | 実行可能な手動ケースと探索チャーターを表す | `synthesize_manual_cases` |
| `effort_plan` | 実行順、担当、工数、buffer を表す | `estimate_effort` |
| `gate_decision` | go/conditional_go/no_go と理由を表す | `evaluate_gates` |
| `release_brief` | ステークホルダー向け判断材料を表す | `assemble_release_brief` |
| `execution_evidence` | 実行結果、expected/actual、添付、incident を表す | `ingest_execution_evidence` |

## Shared Fields

Prefer these fields across artifacts.

```json
{
  "source_refs": [
    {"id": "AC-1", "kind": "ac", "excerpt": "出荷前の注文のみキャンセルできる"}
  ],
  "assumptions": [
    {
      "id": "ASM-1",
      "text": "在庫復元は非同期に完了すると仮定",
      "severity": "medium",
      "impact_on_coverage": "結果確認を待機付きにする"
    }
  ],
  "confidence": "high"
}
```

`SourceRef.kind` は `spec / ac / rule / bug / auto_test / code_review / ops` を基本にする。

## Minimal Schema Shape

Use this reduced schema when the user asks for machine-readable output.

```json
{
  "feature_spec": {
    "feature_id": "string",
    "title": "string",
    "summary": "string",
    "actors": ["string"],
    "acceptance_criteria": ["string"],
    "business_rules": ["string"],
    "changed_areas": ["string"],
    "devices": ["string"],
    "source_refs": [],
    "assumptions": []
  },
  "test_model": {
    "feature_id": "string",
    "flows": ["string"],
    "data_partitions": ["string"],
    "boundaries": ["string"],
    "rule_columns": ["string"],
    "states": ["string"],
    "valid_transitions": ["string"],
    "invalid_transitions": ["string"],
    "role_matrix": ["role x action x resource_state x ownership_context"],
    "regression_edges": ["direct/shared_asset/external_integration"],
    "quality_lenses": ["usability", "compatibility", "recovery"]
  },
  "observation_set": [
    {
      "id": "OBS-STATE-01",
      "title": "状態差で結果が変わる",
      "view": "black",
      "coverage_item_id": "STATE-shipped-cancel",
      "mandatory": true,
      "techniques": ["state_transition"],
      "rationale": "キャンセル可否が注文状態に依存するため",
      "source_refs": []
    }
  ],
  "risk_register": [
    {
      "id": "RISK-01",
      "scenario": "出荷済み注文がキャンセルできてしまう",
      "risk_score": 66,
      "priority": "P1",
      "rationale": "売上、配送、返金の整合性を損なう"
    }
  ],
  "manual_case_set": [
    {
      "tc_id": "TC-001",
      "title": "出荷済み注文はキャンセル不可",
      "priority": "P1",
      "primary_view": "black",
      "techniques": ["state_transition"],
      "preconditions": ["注文状態=shipped"],
      "steps": ["注文詳細を開く", "キャンセル操作を行う"],
      "expected_results": ["キャンセル不可メッセージを表示", "注文状態は変化しない"],
      "oracle": {"type": "specified", "refs": ["AC-2"]},
      "estimate_minutes": 8,
      "trace_to": ["OBS-STATE-01", "RISK-01"]
    }
  ],
  "exploratory_charters": [
    {
      "id": "CHARTER-001",
      "title": "キャンセル操作のエラー表示と復帰性を探索する",
      "scope": "network loss and retry during cancellation",
      "questions": ["二重実行にならないか", "ユーザーに再試行可否が伝わるか"],
      "trace_to": ["OBS-RECOVERY-01"]
    }
  ],
  "gate_decision": {
    "feature_id": "string",
    "status": "go",
    "reasons": ["string"],
    "blocking_risks": [],
    "waivers": []
  }
}
```
