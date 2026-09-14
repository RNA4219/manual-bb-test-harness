---
task_id: 20260720-local-70
intent_id: INT-LOCAL-MODEL-70
owner: RNA4219
status: completed
last_reviewed_at: 2026-07-20
next_review_due: 2026-08-20
---

# Task Seed: ローカルLLM版を70点台へ引き上げる

## 背景

- provider障害時にも manual-bb のテスト設計を継続できるローカル実行経路が必要。
- Qwen3.6 27Bの自由生成は自己レビュー後でも60点、決定的検証を加えて65点だった。
- 主な失点はリスク・工数の算術、oracle/source/trace不足、境界・状態・権限・mobile観点の欠落、証跡のない楽観Gateだった。

## ゴール

- OpenAI互換APIを使うローカルモデル向けパイプラインを実装し、3 fixture x 3 runで70点台を安定して出す。
- LLMは意味候補の生成に限定し、型・算術・lint・Gateはホスト側で決定的に処理する。
- 既存 `manual-bb-test-harness` の成果物スキーマとGate権限を維持する。

## 実施対象

1. `generic` / `qwen36` profile、loopback制約、モデル検出を持つOpenAI互換client。
2. feature_spec → test_model → observation_set → risk_register → manual_case_set の段階生成。
3. artifactごとのschema検証と最大1回のrepair。
4. リスク点数、工数、証跡なしGate、release briefの決定的生成。
5. oracle/source/trace/boundary/state/auth/race/mobile lintとrun manifest。
6. order-cancel / admin-role-change / mobile-session-resume の3回反復評価。

## 完了条件

- [x] 全9 runの成果物がschema validでautomatic failなし。
- [x] fixtureごとの中央値70以上、全体中央値70以上、最低65以上。
- [x] 1 run 10分以内。
- [x] リスク・工数・Gateの決定的検査が100%成功。
- [x] README、運用ガイド、acceptance record、テストを更新。

## 参照

- `docs/evaluation-rubric.md`
- `skills/manual-bb-test-harness/SKILL.md`
- `goldens/*.input.md`
- `docs/local-model-benchmark-20260720.md`
