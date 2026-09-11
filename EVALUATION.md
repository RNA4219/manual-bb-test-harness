---
intent_id: INT-MBB-001
owner: manual-bb-test-harness
release_version: 4.0.1
test_count: 1039
knowledge_map: 33 nodes, 45 edges, 33 capsules
next_review_due: 2026-10-11
status: active
last_reviewed_at: 2026-05-16
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
- local-designの9-run benchmarkがschema、automatic fail、70点、時間、決定的算術の条件を満たす。
- 技法被覆の変更は `tests/test_coverage_engine.py` と `tests/test_technique_extended.py` で入力点・制約・連続経路・決定表の等価性・実行証跡を確認する。golden `discount-domain` をレビューし、未対応・unknown・failを100%やpassに読み替えない。
- 形式的な被覆の合格はLLM出力の意味的品質を保証しない。実モデルの9-run benchmarkを省略した場合、その制約を検収記録に明示する。

## Quality Gates

| gate | criterion |
|---|---|
| Documentation | 正本ドキュメントの読み順が `HUB.codex.md` から辿れる |
| Traceability | task seed と acceptance record が相互参照できる |
| Contract | schema と example が contract と矛盾しない |
| Skill | `SKILL.md` と references の責務分離が保たれる |
| Mobile | mobile 対象で lifecycle / network / permission / entrypoint が欠けない |
| Regression | 既存 golden と validator が通る |
| Local model | 3 fixtures x 3 runsの中央値70以上、最低65以上、各10分以内 |

## Test Outline

要件定義の信頼度は`tests/test_requirements_confidence.py`で、未レビュー・重大未解決の上限、重複、密度、解決根拠、入力版照合、CLI・例を検証する。採点policyの充足と仕様の意味的正しさは分け、実案件データによる校正は未実施として扱う。[spec-07](docs/specs/spec-07-requirements-confidence.md)を参照。

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
- local model:
  - `uv run pytest tests\test_local_runtime.py tests\test_local_pipeline.py`
  - `uv run bb-harness run local-design --input goldens\order-cancel.input.md --output tmp\local-order --profile qwen36`

## Local 70-point benchmark

`order-cancel`、`admin-role-change`、`mobile-session-resume`を各3回実行し、補正後artifactを `docs/evaluation-rubric.md` で生成主体とは別に採点する。`quality_report.json` は構造preflightであり、独立採点の代用にしない。

合格条件:

- 9/9 runがschema validでautomatic fail 0。
- fixture別中央値70以上、全体中央値70以上、最低65以上。
- 9/9 runが10分以内。
- risk score/priority、effort合計、evidenceなしGateの決定的検算が100%。
- 未達時はgoldenを変更せず、profile、stage prompt、validator、repair単位を修正する。

## Verification Checklist

- [x] `README.md` から正本ドキュメントへ辿れる
- [x] `HUB.codex.md` の読み順が repo 実態と一致する
- [x] artifact contract / schema / example / golden が同期している
- [x] mobile golden が追加観点を検知できる（`mobile-session-resume`: lifecycle/permission/network/push_entry観点あり @ 2026-05-30）
- [x] `uv run pytest` が成功する（765 tests passed @ 2026-07-21）
- [x] validator が成功する（quick-validate-skill, validate-skill.ps1, validate-artifact --all --strict）
- [x] branch coverage が 85% 以上（86.00% @ 2026-07-21）
- [x] Gate branch coverage 90% 以上（gate_engine: 92.76% @ 2026-07-12）
- [x] Black-box Fidelity Gate PASS（P0/P1 scripted case 100% source_ref/oracle/trace_to、user-visible behavior で説明できない scripted case 0件 @ 2026-05-30）
  - order-cancel: TC-001(P1), TC-002(P0), TC-003(P1) 全て source_ref/oracle/trace_to 明示済み
  - mobile-session-resume: TC-MOBILE-001(P0), TC-MOBILE-002(P1), TC-MOBILE-004(P1) 全て source_ref/oracle/trace_to 明示済み
  - admin-role-change: TC-ADMIN-001(P0), TC-ADMIN-002(P1), TC-ADMIN-003(P1), TC-ADMIN-004(P0), TC-ADMIN-006(P1) 全て source_ref/oracle/trace_to 明示済み
  - gray-box cases (TC-003, TC-ADMIN-006) は補助証跡扱いとして black-box release判定から分離済み
- [x] Release Artifact Bundle Validation PASS（wheel/sdist隔離smokeを含む @ 2026-07-12）
- [x] Security / Dependency Scan 実行結果記録済み（uv.lock 再現性、依存関係 audit、GitHub Actions pinned version、secret 境界 @ 2026-05-30）
- [x] release review と acceptance record が作成されている（docs/release-review-20260530.md, docs/acceptance/AC-20260530-02.md @ 2026-05-30）
- [x] 残余リスクなし（全 P0 スクリプト coverage 80%以上達成 @ 2026-05-30）
- [x] 最終判定 **go**（全完了条件満足 @ 2026-05-30）

## 生成効率・証跡版（2026-09-10）

追加仕様[spec-05](docs/specs/spec-05-efficient-generation-evidence-revisions.md)は `test_generation_efficiency.py / test_evidence_revisions.py` で、予算境界・unknown usage・差分保持・版照合を確認する。実モデル比較は `tools/benchmark_local_efficiency.py` でfull→compactを順次実行する。両方のschema・構造・必須被覆100%・実測usageが揃わなければ削減率をnullにし、9-runへ進めない。独立した意味的品質採点は別に必要。

2026-09-10追加検収: 898 tests成功、分岐を含むcoverage 87.07%、Gate専用103件 90.94%。実LLM比較は両runのJSON出力未完了により不成立。[検収・実測記録](docs/acceptance/AC-20260910-efficiency.md)を参照。

2026-09-10分割生成の追加検収: 936 tests成功、分岐を含むcoverage 87.53%、Gate専用107件 91.01%、wheel／sdist smoke成功。実LLMはモデルと観点の生成まで進んだが、必須観点2件のリスク分析漏れで停止。全段完走・削減率・独立した意味的品質採点は未達／未判定。[検収・実測記録](docs/acceptance/AC-20260910-batched.md)を参照。

## 分割生成・完了判定（2026-09-10）

[spec-06](docs/specs/spec-06-bounded-generation-readiness.md)は`tests/test_batched_generation.py`で、打切り、分割統合／有限停止／予算、既存出力保護、比較ファイルの欠損／改変、設計状態を検証する。生成終了や構文成功を、意味的品質の合格と同一視しない。
## 要件定義信頼度の追加検収（2026-09-11）

全1001件成功、分岐を含むcoverage 88.18%。新機能の評価エンジン・CLIは98.14%、Gate専用107件・91.01%。schema例29件、仕様書7件、Skill validator、wheel／sdist smoke成功。[検収記録](docs/acceptance/AC-20260911-requirements-confidence.md)を参照。要件信頼度の点数を生成品質や実LLMの完走評価へ流用しない。
