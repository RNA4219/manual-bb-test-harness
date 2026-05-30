---
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: active
last_reviewed_at: 2026-05-16
next_review_due: 2026-06-16
---

# Evaluation

## Acceptance Criteria

- `README.md`、`HUB.codex.md`、`BLUEPRINT.md`、`RUNBOOK.md`、`GUARDRAILS.md`、`EVALUATION.md` の役割が明確である。
- `SKILL.md` が短く、詳細方針が `references/` に分離されている。
- artifact contract、schema、example、golden、rubric が同じ振る舞いを表している。
- scripted case に oracle refs と traceability がある。
- mobile 対象では `mobile_contexts` と `platform_matrix` が artifact と evaluation に現れる。
- `goldens/` が review anchor として主要な抜けを検知できる。
- task seed と acceptance record が変更単位を追跡できる。
- validator と test suite が通る。

## Quality Gates

| gate | criterion |
|---|---|
| Documentation | 正本ドキュメントの読み順が `HUB.codex.md` から辿れる |
| Traceability | task seed と acceptance record が相互参照できる |
| Contract | schema と example が contract と矛盾しない |
| Skill | `SKILL.md` と references の責務分離が保たれる |
| Mobile | mobile 対象で lifecycle / network / permission / entrypoint が欠けない |
| Regression | 既存 golden と validator が通る |

## Test Outline

- 単体:
  - `tests/test_spec_ingest.py`
  - `tests/test_quick_validate_skill.py`
  - `tests/test_validate_skill_ps1.py`
- 回帰:
  - `uv run pytest`
- Skill 構造:
  - `uv run python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness`
  - `.\scripts\validate-skill.ps1`
- artifact:
  - `uv run python .\scripts\validate-artifact.py --artifact .\examples\artifacts\order-cancel.feature_spec.json --type feature_spec`
  - `uv run python .\scripts\validate-artifact.py --artifact .\examples\artifacts\order-cancel.test_model.json --type test_model`

## Verification Checklist

- [x] `README.md` から正本ドキュメントへ辿れる
- [x] `HUB.codex.md` の読み順が repo 実態と一致する
- [x] artifact contract / schema / example / golden が同期している
- [x] mobile golden が追加観点を検知できる（`mobile-session-resume`: lifecycle/permission/network/push_entry観点あり @ 2026-05-30）
- [x] `uv run pytest` が成功する（654 tests passed @ 2026-05-30）
- [x] validator が成功する（quick-validate-skill, validate-skill.ps1, validate-artifact --all --strict）
- [x] coverage が 70% 以上（86% @ 2026-05-30）
- [x] P0 対象主要分岐 coverage が 80% 以上（evaluate-gate: 94%, risk-heatmap: 84%, validate-spec: 91%, import-testrail: 88%, import-xray: 90%, spec-ingest: 85% @ 2026-05-30）
- [x] Black-box Fidelity Gate PASS（P0/P1 scripted case 100% source_ref/oracle/trace_to、user-visible behavior で説明できない scripted case 0件 @ 2026-05-30）
  - order-cancel: TC-001(P1), TC-002(P0), TC-003(P1) 全て source_ref/oracle/trace_to 明示済み
  - mobile-session-resume: TC-MOBILE-001(P0), TC-MOBILE-002(P1), TC-MOBILE-004(P1) 全て source_ref/oracle/trace_to 明示済み
  - admin-role-change: TC-ADMIN-001(P0), TC-ADMIN-002(P1), TC-ADMIN-003(P1), TC-ADMIN-004(P0), TC-ADMIN-006(P1) 全て source_ref/oracle/trace_to 明示済み
  - gray-box cases (TC-003, TC-ADMIN-006) は補助証跡扱いとして black-box release判定から分離済み
- [x] Release Artifact Bundle Validation PASS（dry-run bundle 生成・検証成功 @ 2026-05-30）
- [x] Security / Dependency Scan 実行結果記録済み（uv.lock 再現性、依存関係 audit、GitHub Actions pinned version、secret 境界 @ 2026-05-30）
- [x] release review と acceptance record が作成されている（docs/release-review-20260530.md, docs/acceptance/AC-20260530-02.md @ 2026-05-30）
- [x] 残余リスクなし（全 P0 スクリプト coverage 80%以上達成 @ 2026-05-30）
- [x] 最終判定 **go**（全完了条件満足 @ 2026-05-30）
