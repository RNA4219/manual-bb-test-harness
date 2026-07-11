---
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: active
last_reviewed_at: 2026-05-16
next_review_due: 2026-10-11
---

# Guardrails

## 目的

- Skill 本体を短く保ち、詳細を `references/` へ逃がす。
- 根拠のない expected result を scripted case にしない。
- artifact contract、schema、example、golden、rubric の同期崩れを防ぐ。
- Web と mobile の差分を、単なる端末名ではなく coverage model の一部として扱う。

## ドキュメント原則

1. `README.md` は入口、`HUB.codex.md` は読み順、`BLUEPRINT.md` は設計正本、
   `RUNBOOK.md` は実行手順、`EVALUATION.md` は検収、`GUARDRAILS.md` は原則を担う。
2. 長文の補助説明は `docs/`、Skill 実行時に読む必要がある詳細方針は `references/` に置く。
3. 同じ仕様を複数ファイルへ重複転記しすぎない。必要な場合は正本を明記してリンクする。
4. 変更履歴は `CHANGELOG.md`、実装済み仕様の記録は `SPEC.md` に置く。

## 実装原則

- `feature_spec` を変えたら、対応する ingest、schema、example、test を確認する。
- `test_model` を変えたら、出力テンプレート、rubric、golden を確認する。
- P0/P1 の scripted case には oracle refs を必須にする。
- `degraded` と `blocked` の閾値を曖昧にせず、missing info を assumption として残す。
- mobile 対象では background、network、permission、entrypoint の差分を無視しない。

## 変更時チェック

- `uv run pytest`
- `uv run python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness`
- `.\scripts\validate-skill.ps1`
- artifact contract 変更時は example と golden の更新有無を確認

## 例外

- 仕様根拠がない UX 妥当性は scripted case ではなく exploratory charter に落とす。
- domain 固有の追加観点は `platform-pack-*` または `domain-pack-*` として分離する。
