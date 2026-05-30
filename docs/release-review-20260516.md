# Release Review: manual-bb-test-harness mobile / docs alignment

## Intake Status

- status: ok
- assumptions:
  - 本検収は repo 内 artifact と docs の release readiness を対象にし、外部 SaaS 設定や実機クラウドは対象外とする。
- blockers:
  - なし

## 根拠付き観点

| id | coverage_item | mandatory | title | view | techniques | source | rationale |
|---|---|---|---|---|---|---|---|
| OBS-CONTRACT-01 | schema / artifact | yes | mobile 契約が artifact chain に通っている | black | equivalence_partitioning | `schemas/feature_spec.schema.json`, `schemas/test_model.schema.json` | 新規 mobile 対応の本体だから |
| OBS-INGEST-01 | flow | yes | Markdown intake で mobile context を失わない | black | state_transition | `scripts/spec-ingest.py`, `tests/test_spec_ingest.py` | intake で落ちると後段設計に出ない |
| OBS-DOCS-01 | regression | yes | workflow docs の正本導線が揃う | black | checklist | `README.md`, `HUB.codex.md`, `AGENTS.md` | docs 改修の主要価値だから |
| OBS-GOLDEN-01 | regression | yes | mobile golden が future review anchor になる | black | equivalence_partitioning | `goldens/mobile-session-resume.*` | 将来の退行検知に必要 |
| OBS-VALIDATION-01 | gate | yes | 既存 validation が壊れていない | white | evidence_review | test / validator results | release 判定の基礎証跡 |
| OBS-TRACKING-01 | traceability | yes | example / export / lockfile が追跡対象に含まれる | black | checklist | `examples/`, `exports/`, `uv.lock` | docs と repo state を一致させるため |

## Coverage Model

- data_partitions:
  - `feature_spec.mobile_contexts present / absent`
  - `test_model.platform_matrix present / absent`
- boundaries:
  - `Web-only -> mobile-targeted`
  - `docs-only update -> contract-affecting update`
- rule_columns:
  - `artifact_contract x schema x example x golden`
  - `README x HUB x AGENTS`
- states:
  - `pre-mobile`
  - `mobile-enabled`
  - `docs-aligned`
  - `release-reviewed`
- valid_transitions:
  - `pre-mobile -> mobile-enabled`
  - `mobile-enabled -> docs-aligned`
  - `docs-aligned -> release-reviewed`
- invalid_transitions:
  - `mobile-enabled -> release-reviewed` without golden
  - `docs-aligned -> release-reviewed` without validation evidence
- role_matrix:
  - `maintainer x update x artifact_contract x repo`
  - `reviewer x verify x release_readiness x repo`
- regression_edges:
  - `direct:schemas`
  - `direct:scripts/spec-ingest.py`
  - `direct:skills/manual-bb-test-harness`
  - `shared:README/HUB/docs`
  - `shared:examples/exports`
- platform_matrix:
  - `iOS x background_resume x 4g-lossy`
  - `Android x offline_to_online x foreground`
- quality_lenses:
  - `traceability`
  - `compatibility`
  - `recovery`
  - `documentation usability`

## リスク

| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|
| RISK-01 | mobile 契約が docs だけにあり schema / example に反映されない | 4 | 3 | D1 C2 X1 P0 A2 | 42 | P2 | 将来の出力揺れと機械連携不整合につながる |
| RISK-02 | intake が `mobile_contexts` を落として後段で mobile 観点が消える | 4 | 3 | D2 C2 X1 P0 A2 | 44 | P2 | 仕様取り込みから欠落すると silent failure になる |
| RISK-03 | docs の正本導線が曖昧で保守時に誤読する | 3 | 3 | D2 C2 X0 P0 A1 | 37 | P2 | 将来の変更時に重複更新や参照漏れを招く |
| RISK-04 | mobile golden 不足で将来の review が Web 偏重へ戻る | 4 | 2 | D2 C1 X1 P0 A1 | 35 | P2 | 新規拡張の退行検知が弱くなる |
| RISK-05 | 説明済みの example / export が未追跡で再現性が落ちる | 3 | 3 | D2 C2 X0 P0 A1 | 37 | P2 | docs と repository state が食い違う |

## 手動テストケース

| tc_id | priority | title | preconditions | steps | expected | oracle | trace_to | minutes |
|---|---|---|---|---|---|---|---|---:|
| TC-001 | P2 | mobile 契約の一貫性確認 | 更新後 workspace | schema、artifact-contract、example を順に確認 | `mobile_contexts` と `platform_matrix` が整合する | specified: `BLUEPRINT.md`, artifact contract | OBS-CONTRACT-01, RISK-01 | 8 |
| TC-002 | P2 | mobile context intake 確認 | `goldens/mobile-session-resume.input.md` が存在 | `spec-ingest.py` の section mapping と unit test を確認 | `Mobile Contexts` が `mobile_contexts` に保持される | specified: ingest test | OBS-INGEST-01, RISK-02 | 8 |
| TC-003 | P2 | docs 読み筋確認 | root docs 更新済み | README から HUB、BLUEPRINT、RUNBOOK、GUARDRAILS、EVALUATION へ辿る | 目的別の導線が一意に読める | specified: workflow docs | OBS-DOCS-01, RISK-03 | 8 |
| TC-004 | P2 | mobile golden 確認 | golden 追加済み | input / expected を確認 | lifecycle、permission、push、network が anchor に含まれる | specified: golden expected | OBS-GOLDEN-01, RISK-04 | 8 |
| TC-005 | P2 | 生成例の追跡確認 | example / export 追加済み | examples と exports の README を確認し git status と突き合わせる | 残す成果物が docs と git 管理対象に一致する | specified: docs | OBS-TRACKING-01, RISK-05 | 8 |

## 探索チャーター

| id | priority | title | scope | questions | trace_to | minutes |
|---|---|---|---|---|---|---:|
| CHARTER-001 | P3 | 将来 domain pack との重複探索 | `references/` の mobile / domain pack 境界 | mobile pack と future notification pack の責務は重ならないか | OBS-CONTRACT-01 | 10 |

## 工数

- prep: 5 min
- execution: 40 min
- evidence: 10 min
- retry buffer: 8 min
- total: 63 min

## Gate

- profile: standard
- decision: go
- reasons:
  - 当時の `uv run pytest` は passed[^1]
  - 現行再検証では `uv run pytest` が 145 passed @ 2026-05-30
  - Skill validator と PowerShell validator が成功
  - mobile contract、ingest、golden、docs 導線の観点を確認済み
  - example / export / lockfile の追跡範囲を確認済み
- blocking_risks:
  - なし
- waivers:
  - なし

## Go/No-Go Brief

- feature:
  - mobile 対応拡張と workflow-cookbook 準拠 docs 整備
- decision:
  - go
- top risks:
  - 将来の golden 未更新
  - domain pack 増加時の責務重複
- coverage gaps:
  - 実運用の forward-test canonical log は Notion 側で継続蓄積が必要
- evidence:
  - 当時の pytest passed[^1]
  - 現行再検証: 145 passed @ 2026-05-30
  - quick validator passed
  - PowerShell validator passed
  - feature_spec / test_model artifact validation passed
  - examples / exports の一覧を docs に反映済み
- residual risk:
  - low
- required follow-up:
  - forward-test 実績が増えた時点で Notion canonical log と repo golden を再同期する

[^1]: 当時の記録。古いテスト件数は現行値として扱わない。最新値は `uv run pytest` 実行で確認。
