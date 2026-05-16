---
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: active
last_reviewed_at: 2026-05-16
next_review_due: 2026-06-16
---

# Blueprint

## 1. Problem Statement

`manual-bb-test-harness` は、仕様から直接ケースを量産するのではなく、  
coverage model、観点、リスク、ケース、gate、release brief を段階的に接続し、  
手動ブラックボックス QA を監査可能な chain として扱うための Skill repo である。

Web だけでなく iOS / Android も対象に含めるため、mobile 固有の lifecycle、権限、
通知入口、network 差分も coverage model の first-class 要素として扱う。

## 2. Scope

- In:
  - `phase_contract` から `release_brief` までの artifact 契約
  - 手動 black-box を主軸にした観点抽出、リスク付け、case synthesis
  - schema / example / golden / evaluation rubric の同期
  - Web / API / iOS / Android をまたぐ対象環境差分
  - TestRail / Xray / Notion 連携用の export / import 補助
- Out:
  - 実機クラウドや MDM など mobile 実行基盤の構築
  - 自動テストフレームワークそのものの実装
  - 外部 SaaS の本番運用設定
  - 各プロダクト固有の業務ルール正本

## 3. Constraints / Assumptions

- `SKILL.md` は短く保ち、詳細な方針は `references/` に分離する。
- scripted case には oracle と traceability を必須にする。
- `black` を release acceptance の主役とし、`gray` / `white` は補助証跡に留める。
- artifact contract を変えるときは `schemas/`、`examples/artifacts/`、`goldens/` を同時更新する。
- mobile 対象では `platform_matrix` を必須 lens として扱う。
- golden は厳密 snapshot ではなく review anchor として扱う。

## 4. I/O Contract

- Input:
  - 仕様、受入条件、業務ルール、変更点、既存証跡
  - 必要に応じて対象端末、OS、mobile context、既知 defect、waiver
- Output:
  - `phase_contract`
  - `feature_spec`
  - `test_model`
  - `observation_set`
  - `risk_register`
  - `manual_case_set`
  - `effort_plan`
  - `gate_decision`
  - `release_brief`
  - `execution_evidence`

## 5. Minimal Flow

```mermaid
flowchart LR
  A["Spec / AC / Evidence"] --> B["feature_spec"]
  B --> C["test_model"]
  C --> D["observation_set"]
  D --> E["risk_register"]
  E --> F["manual_case_set"]
  F --> G["effort_plan"]
  G --> H["gate_decision"]
  H --> I["release_brief"]
```

## 6. Interfaces

- Skill:
  - `skills/manual-bb-test-harness/SKILL.md`
- Schemas:
  - `schemas/*.schema.json`
- Examples:
  - `examples/artifacts/*.json`
- Evaluation:
  - `docs/evaluation-rubric.md`
  - `goldens/*.expected.md`
- Scripts:
  - `scripts/spec-ingest.py`
  - `scripts/evaluate-gate.py`
  - `scripts/export-testrail.py`
  - `scripts/export-xray.py`
