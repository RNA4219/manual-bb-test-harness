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

開発着手前の入力を扱う場合は、通常 chain の前に `phase_contract` を作る。`phase_contract.readiness.status = blocked` の場合は、詳細な手動ケース生成へ進まず、未決事項、仕様不足、Go/No-Go 判断材料を返す。

| artifact | purpose | produced by |
|---|---|---|
| `phase_contract` | 企画、モック、要件メモを Definition of Ready と Phase 1 契約へ正規化する | `normalize_ready_intake` |
| `feature_spec` | 仕様、AC、業務ルール、変更点、環境、前提を正規化する | `normalize_intake` |
| `test_model` | flow/state/rule/data/role/regression の coverage item を表す | `model_test_surface` |
| `observation_set` | 根拠付き観点を表す | `derive_observations` |
| `risk_register` | 各観点やシナリオのリスクと優先度を表す | `assess_risk` |
| `manual_case_set` | 実行可能な手動ケースと探索チャーターを表す | `synthesize_manual_cases` |
| `effort_plan` | 実行順、担当、工数、buffer を表す | `estimate_effort` |
| `gate_decision` | go/conditional_go/no_go と理由を表す | `evaluate_gates` |
| `release_brief` | ステークホルダー向け判断材料を表す | `assemble_release_brief` |
| `execution_evidence` | feature/buildに紐づく手動実行結果とdefectを表す | `ingest_execution_evidence` |
| `automation_evidence` | coverage scope、coverage率、新規issue、hotspot review、source refsを表す | `ingest_automation_evidence` |
| `waiver_set` | owner・期限・containment・rollbackを持つ明示的なrisk受容を表す | `approve_waivers` |

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
企画段階では `mock / memo / interview / metric` も使える。

## Minimal Schema Shape

Use this reduced schema when the user asks for machine-readable output.

```json
{
  "phase_contract": {
    "contract_id": "string",
    "feature_id": "string",
    "readiness": {
      "status": "ok | degraded | blocked",
      "decision": "ready | ready_with_conditions | not_ready",
      "reasons": ["string"],
      "required_before_dev": ["string"]
    },
    "problem_owner": {
      "persona": "string",
      "problem": "string"
    },
    "success_conditions": [
      {
        "id": "SC-1",
        "text": "string",
        "metric": "string",
        "source_refs": ["MOCK-1"]
      }
    ],
    "phase1_scope": ["string"],
    "phase1_non_goals": ["string"],
    "open_questions": [
      {
        "id": "Q-1",
        "severity": "critical",
        "question": "string",
        "owner": "string",
        "blocks_ready": true
      }
    ],
    "spec_gaps": [
      {
        "id": "GAP-1",
        "severity": "high",
        "gap": "string",
        "impact": "string",
        "needed_oracle": "string"
      }
    ],
    "technical_risks": [
      {
        "id": "TR-1",
        "severity": "medium",
        "risk": "string",
        "mitigation": "string"
      }
    ],
    "metrics": ["string"],
    "test_lenses": [
      {
        "id": "TL-1",
        "lens": "state",
        "title": "string",
        "rationale": "string",
        "trace_to": ["SC-1"]
      }
    ],
    "source_refs": [],
    "assumptions": []
  },
  "feature_spec": {
    "feature_id": "string",
    "title": "string",
    "summary": "string",
    "actors": ["string"],
    "acceptance_criteria": ["string"],
    "business_rules": ["string"],
    "changed_areas": ["string"],
    "devices": ["string"],
    "mobile_contexts": ["foreground", "background_resume", "offline", "push_notification_entry"],
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
    "platform_matrix": ["iOS x background_resume x 4g-lossy"],
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
    "build_id": "string",
    "status": "go",
    "profile": "standard",
    "reasons": ["all profile conditions met"],
    "evidence_summary": {
      "manual_by_priority": {},
      "mandatory_observation_rate": 100
    },
    "unmet_conditions": []
  }
}
```

## Gate Artifacts 2.0

2.0では旧artifactの読み取り互換を提供しない。schemaを正本とし、以下を必須とする。

- `execution_evidence`: `run_id / feature_id / build_id / timestamp / result`と、`tc_id`または`charter_id`のどちらか一方。defectは`severity`と`open / resolved / accepted`のstatusを持つ。
- `automation_evidence`: `feature_id / build_id / coverage_scope / coverage_percent / new_issues / source_refs`。strict profileでは`hotspot_review_percent`も判定に使う。
- `waiver_set`: `feature_id / build_id / waivers`。各waiverに`id / risk_ids / reason / owner / expires_at / containment / rollback`を要求する。Gateがwaiverを自動生成してはならない。 P1/mandatory observation/残余riskに適用する場合は、未達artifactの`trace_to`から導出されるrisk IDを全て`risk_ids`で覆う。P0、重大defect、critical assumption、automation failureはwaiver不可で、全Gate入力は評価前にschema検証する。
- `gate_decision`: `feature_id / build_id / status / profile / reasons / evidence_summary`を必須とし、`waivers / unmet_conditions / residual_risks / blocking_risks`を必要に応じて記録する。`reasons`が0件のGoは禁止する。

```json
{
  "execution_evidence": {
    "run_id": "RUN-42",
    "tc_id": "TC-001",
    "feature_id": "order-cancel",
    "build_id": "build-20260711.1",
    "timestamp": "2026-07-11T10:00:00+09:00",
    "result": "pass"
  },
  "automation_evidence": {
    "feature_id": "order-cancel",
    "build_id": "build-20260711.1",
    "coverage_scope": "changed_code",
    "coverage_percent": 78,
    "new_issues": {"blocker": 0, "critical": 0},
    "source_refs": [{"id": "CI-42", "kind": "auto_test"}]
  },
  "waiver_set": {
    "feature_id": "order-cancel",
    "build_id": "build-20260711.1",
    "waivers": [{
      "id": "W-1",
      "risk_ids": ["RISK-12"],
      "reason": "限定的な表示差分",
      "owner": "qa-lead",
      "expires_at": "2026-08-11T00:00:00+09:00",
      "containment": "監視を追加",
      "rollback": "feature flagを無効化"
    }]
  }
}
```
