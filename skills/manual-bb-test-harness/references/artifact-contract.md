# Artifact Contract

## RanDからの取り込み

`rand_intake`（schema 2.0 / adapter 1）はmanual-bb所有の連携artifact。input snapshotとSHA256、要求ID・原文・AC・上流評価・差分分類・欠陥台帳・未解決assumptionを保持する。feature_specのACを補作せず、R&D候補を承認済みoracleへ昇格しない。操作と設計への接続は[rand-integration.md](rand-integration.md)、厳密な形は`schemas/rand_intake.schema.json`を参照。

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
| `test_plan` | 目的、テストレベル、開始・停止・再開条件、準備状況、見積根拠を表す | `plan_test` |
| `effort_plan` | 実行順、担当、工数、buffer を表す | `estimate_effort` |
| `gate_decision` | go/conditional_go/no_go と理由を表す | `evaluate_gates` |
| `release_brief` | ステークホルダー向け判断材料を表す | `assemble_release_brief` |
| `execution_evidence` | 実行結果、expected/actual、添付、incident を表す | `ingest_execution_evidence` |
| `automation_evidence` | coverage・静的解析と必須suiteの実績を表す | CI証跡の取り込み |
| `defect_register` | 欠陥IDごとの状態と解決確認を表す | 欠陥状態の取り込み |
| `waiver_set` | リスク受容の承認者、承認時刻、判断記録、期限、封じ込めを表す | リリース判断の取り込み |

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
    "revision": "string",
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
    "coverage_items": [
      {
        "id": "COV-STATE-SHIPPED-CANCEL",
        "dimension": "state",
        "technique": "state_transition",
        "applicability": "applicable",
        "mandatory": true,
        "coverage_criterion": "each_transition",
        "source_refs": [{"id": "AC-2", "kind": "ac"}]
      }
    ],
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
    "quality_lenses": [
      {
        "id": "QL-RECOVERY",
        "lens": "recovery",
        "applicable": true,
        "reason": "通信中断を伴う操作のため",
        "owner": "QA",
        "oracle": {"type": "specified", "refs": ["AC-1"]}
      }
    ],
    "improvement_feedback": [
      {
        "id": "FB-1",
        "source_refs": ["BUG-1"],
        "finding": "再試行案内が不明瞭だった",
        "action": "チェックリストを更新する",
        "target_refs": ["QL-RECOVERY"]
      }
    ]
  },
  "observation_set": {
    "feature_id": "string",
    "observations": [{
      "id": "OBS-STATE-01",
      "title": "状態差で結果が変わる",
      "view": "black",
      "coverage_item_id": "STATE-shipped-cancel",
      "mandatory": true,
      "techniques": ["state_transition"],
      "support_count": 1,
      "run_count": 3,
      "mandatory_reason": "AC-2 と P1 リスクに基づく",
      "rationale": "キャンセル可否が注文状態に依存するため",
      "source_refs": []
    }]
  },
  "risk_register": {
    "feature_id": "string",
    "risks": [{
      "id": "RISK-01",
      "scenario": "出荷済み注文がキャンセルできてしまう",
      "risk_score": 66,
      "priority": "P1",
      "rationale": "売上、配送、返金の整合性を損なう"
    }]
  },
  "manual_case_set": {
    "feature_id": "string",
    "spec_revision": "spec-rev-7",
    "manual_cases": [{
      "tc_id": "TC-001",
      "revision": "case-rev-1",
      "content_hash": "sha256:case-content",
      "oracle_revision": "oracle-rev-1",
      "title": "出荷済み注文はキャンセル不可",
      "priority": "P1",
      "primary_view": "black",
      "techniques": ["state_transition"],
      "preconditions": ["注文状態=shipped"],
      "steps": ["注文詳細を開く", "キャンセル操作を行う"],
      "expected_results": ["キャンセル不可メッセージを表示", "注文状態は変化しない"],
      "oracle": {"type": "specified", "refs": ["AC-2"]},
      "estimate_minutes": 8,
      "trace_to": ["OBS-STATE-01", "RISK-01"],
      "status": "active"
    },
    {
      "tc_id": "TC-099",
      "revision": "case-rev-1",
      "content_hash": "sha256:retired-case-content",
      "oracle_revision": "oracle-rev-1",
      "title": "クーポン残数復元は自動統合テストへ移管済み",
      "priority": "P1",
      "primary_view": "gray",
      "techniques": ["data_partition"],
      "preconditions": ["注文状態=pending", "クーポン使用済み"],
      "steps": ["自動テスト参照を確認する"],
      "expected_results": ["replacement_refs が QEG placement change の移管先を示す"],
      "oracle": {"type": "specified", "refs": ["AC-4"]},
      "estimate_minutes": 0,
      "trace_to": ["OBS-DATA-01", "RISK-03"],
      "status": "retired",
      "retired_reason": "QEG placement changeで自動テストへ移管済み",
      "replacement_refs": ["hate:AETE-COUPON-RESTORE-001"],
      "placement_change_ref": "qeg:PLC-ORD-CANCEL-20260702-001"
    }],
    "exploratory_charters": [
    {
      "id": "CHARTER-001",
      "title": "キャンセル操作のエラー表示と復帰性を探索する",
      "scope": "network loss and retry during cancellation",
      "questions": ["二重実行にならないか", "ユーザーに再試行可否が伝わるか"],
      "estimate_minutes": 30,
      "timebox_minutes": 30,
      "session_notes": ["通信断から再開した"],
      "findings": ["再試行案内が不明瞭"],
      "retrospective": "復帰性チェックリストを更新する",
      "trace_to": ["OBS-RECOVERY-01"]
    }
    ]
  },
  "test_plan": {
    "plan_id": "TP-1",
    "feature_id": "string",
    "objective": "主要な受入条件とリスクを確認する",
    "test_level": "system",
    "entry_criteria": [{"id": "ENTRY-1", "condition": "検証buildを配備済み", "status": "met"}],
    "stop_conditions": ["critical defectを検出した"],
    "resume_conditions": ["修正版を配備しsmoke testが通った"],
    "data_readiness": {"status": "ready", "notes": "標準データを作成済み"},
    "environment_readiness": {"status": "ready", "configuration_ids": ["WEB-CHROME"]},
    "estimate_basis": {
      "method": "historical",
      "source_refs": ["RUN-20260901"],
      "assumptions": ["QA担当1名"],
      "uncertainty": "medium"
    }
  },
  "waiver_set": {
    "feature_id": "string",
    "build_id": "build-id",
    "waivers": [{
      "id": "WAIVER-1",
      "risk_ids": ["RISK-03"],
      "reason": "限定公開中は影響を封じ込められる",
      "owner": "QA Lead",
      "approver": "Release Manager",
      "approved_at": "2026-09-12T12:00:00+09:00",
      "approval_ref": "DECISION-1",
      "expires_at": "2026-10-12T12:00:00+09:00",
      "containment": "監視と対象制限",
      "rollback": "機能フラグを無効化"
    }]
  },
  "gate_decision": {
    "feature_id": "string",
    "status": "go",
    "reasons": ["string"],
    "blocking_risks": [],
    "waivers": []
  }
}
```

### Coverage population and multi-run

`test_model.coverage_items[]`を設計網羅の母集団とする。各項目は一意なID、dimension、technique、applicability、mandatory、coverage criterion、source refsを持つ。`observation_set.observations[].coverage_item_id`はこの母集団を参照し、mandatoryな適用対象には観点とcase/charterのtraceが必要である。境界値とデシジョンテーブルは、選択値または実行可能列を構造化して残す。

multi-runの`support_count`と`run_count`は抽出の再現性を示す。少数runだけを理由にmandatoryやP0/P1をoptionalへ落とさない。AC、業務ルール、重大リスクに基づく観点は`mandatory_reason`を持たせて維持し、低supportはレビュー順や追加調査のシグナルとして使う。

`checklist_based`は独立したtechniqueであり、`checklist.id`、`revision`、項目別resultを保持する。探索チャーターの実行後はtimebox、session notes、findings、retrospectiveを記録し、次回のchecklist、risk、goldenへfeedbackを返す。

### Testware identity

`execution_evidence`はbuildだけでなく、`case_revision`、`spec_revision`、`oracle_revision`、`case_content_hash`、`oracle_refs`を必須とする。定義側もfeature specの`revision`、`manual_case_set.spec_revision`、case/charterの`revision`・`content_hash`・`oracle_revision`を必須とし、Gateは証跡と定義の一致を常に検査する。TestRail/Xray連携では`source_case_id`または`source_charter_id`、`source_feature_id`、ケース版、仕様版、オラクル版、ケース内容ハッシュ、オラクル参照をexport/importで往復させ、外部IDや可変な実行結果から元のidentityを推測しない。

### Test planning and quality feedback

`test_plan`は`effort_plan`と分ける。前者は目的、テストレベル、開始条件、停止・再開条件、データ・環境準備、見積根拠を扱い、後者は作業配分と工数を扱う。`quality_lenses[]`は文字列ではなく、適用判断、理由、ownerを持つ。適用対象にはoracleを必須とし、対象外にも理由を残す。`improvement_feedback[]`で発見事項、更新行動、更新対象を結び付ける。

### Waiver provenance

waiverはownerとapproverを別人にし、`approved_at`と`approval_ref`を必須にする。承認日時は未来でなく、有効期限より前でなければならない。期限、containment、rollbackも必要である。critical assumptionまたはblocker/critical/high defectは`accepted`だけでは解消せず、`resolved`となるまでNo-Goとする。lean profileでも未解消のP2残余リスクは無条件に受容せず、対応する承認済みwaiverが必要である。

### Manual Case Lifecycle

`manual_case_set.manual_cases[].status` は `active` を既定とし、`retired` は手動ケースが自動テストなどへ移管済みであることだけを表す。
この repo は引退可否や exit criteria を判定しない。QEG 側 placement change の結果を artifact に保持し、validation / gate / export で落とさない。

Retired case rules:

- `status = retired` では `retired_reason` と `replacement_refs[]` を必須にする。
- `replacement_refs[]` は `hate:AETE-xxx` など移管先 evidence を指す。
- `placement_change_ref` は QEG placement change record がある場合に入れる。
- Gate では retired case を手動未実施の分母に入れず、`retired_cases` として出力する。
- Retired case は replacement の妥当性を評価しない。妥当性判定は QEG / HATE 側の責務とする。

## 実行構成と欠陥履歴

`manual_case_set.execution_configurations[]`は`id`と`env`を必須とし、`device`と`network_profile`も指定できる。各case/charterの`configuration_ids`を省略すると、宣言した全構成を実行対象にする。指定時はその部分集合を対象にする。重複ID、未定義参照、構成IDの意味の変化を拒否する。

`execution_evidence.configuration_id`で計画へ結び付ける。明示計画ではIDを必須にし、提供された環境情報を定義と照合する。計画のない旧入力は`env × device × network_profile`の組で区別するが、未提供の構成は推定しない。複数構成の必要数を検証する場合は明示計画へ移行する。

再実行は同じcase/charterと構成の組の中で選ぶ。同時刻の別構成は別実績として扱い、同じ組の同時刻重複は拒否する。ケースの分母はケース数のままとし、全対象構成のpassが揃って初めてそのケースをpassにする。観点の実行率には、全対象構成でpass/failの実行結果があるケースだけを算入する。構成別の詳細はGateの`evidence_summary.manual_execution_results`に出す。

### 欠陥台帳

`defect_register`は同じ`feature_id`と`build_id`に属する欠陥状態の履歴またはsnapshot。`defects[]`には`defect_id`、`title`、`severity`、`status`、`updated_at`、`source_refs`を持たせる。CLIは`--defects`を受け取り、`--input`では`*defect_register*.json`を検出する。

| status | Gateでの扱い |
|---|---|
| open / in_progress / fixed / pending_confirmation / reopened | 未解決。blocker/critical/highならNo-Go |
| resolved | 明示的な解決記録と確認証跡の照合後に未解決一覧から外す |

`resolved`には`confirmation_run_ids`を必須とする。解決時点までの入力証跡でrun IDが一意であり、各報告対象case/構成の最新実績がpassであること、最後の未解決状態以降かつ解決記録以前の確認であることを検査する。後から別の成功実行が追加されても、過去の有効な解決記録を無効化しない。より新しいreopened報告は保持する。同時刻の矛盾した欠陥状態や、確認証跡不足は入力エラー。

Gateは最新case結果へ絞る前の全入力証跡から欠陥を読む。`defect_stub.defect_id`と`defects[].defect_id`を共通キーにし、複数caseから参照される同じ欠陥を重複計上しない。TestRail/Xray importは受領した欠陥IDを個別に残す。stubのresolvedや再実行passだけではID付き欠陥を閉じない。

IDのない旧stubも未解決のまま保持する。タイトル一致で台帳と結び付けないため、解決管理へ移行するときは元証跡へ安定した欠陥IDを補う。履歴と確認証跡を保存し、必要な台帳を毎回Gateへ渡す。入力に存在しない過去の欠陥や外部trackerの状態をこのCLIが自動復元する機能はない。

### 自動テストの実行結果

`automation_evidence.test_suites[]`は非空で、全suiteを必須として扱う。各要素に一意な`suite_id`、`status`、`total`、`passed`、`failed`、`errors`、`skipped`、`source_refs`を持たせる。件数は非負整数で、内訳の和をtotalへ一致させる。

全profileで`status=passed`、`total>0`、全件passedが必要。failed/error/cancelled/not_run、失敗・error・skipが残るsuite、実行0件はNo-Goで、waiverの対象にしない。カバレッジと静的解析の条件も引き続き適用する。未提供・空配列・件数の不整合は入力エラーとなる。

既存のカバレッジだけのartifactへ成功結果を推測で補わない。実際のCI結果と出典を追加する。`examples/`のsuiteは説明用データであり、利用者のプロジェクトで実行した証跡ではない。

[複合シナリオ](../../../examples/evidence-lifecycle/)は、Android再実行pass、iOS未実行、修正確認待ち欠陥、suite失敗を同時に保持する例。
