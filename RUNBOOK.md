---
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: active
last_reviewed_at: 2026-05-16
next_review_due: 2026-06-16
---

# Runbook

## Environments

- Local: repo 内で Skill / schema / script を編集して検証する
- CI: `.github/workflows/validate.yml` で repo 構造と Skill を検証する
- Consumer: Codex Skill として利用し、Markdown または JSON artifact を生成する

## Execute

### 1. Skill 出力を確認する

```powershell
Get-Content .\skills\manual-bb-test-harness\SKILL.md
Get-Content .\goldens\order-cancel.input.md
Get-Content .\goldens\order-cancel.expected.md
Get-Content .\docs\evaluation-rubric.md
```

mobile 対象の確認では次も読む。

```powershell
Get-Content .\skills\manual-bb-test-harness\references\platform-pack-mobile.md
Get-Content .\goldens\mobile-session-resume.input.md
Get-Content .\goldens\mobile-session-resume.expected.md
```

### 2. artifact 契約を変えたとき

1. `skills/manual-bb-test-harness/references/artifact-contract.md` を更新する。
2. 対応する `schemas/*.schema.json` を更新する。
3. `examples/artifacts/*.json` を更新する。
4. 出力品質が変わる場合は `goldens/` と `docs/evaluation-rubric.md` を更新する。

### 3. 仕様取り込みを変えたとき

```powershell
uv run pytest tests\test_spec_ingest.py
uv run python .\scripts\spec-ingest.py --source markdown --input .\goldens\order-cancel.input.md --output .\exports\order-cancel.feature_spec.json
```

### 4. repo 全体を検証する

```powershell
uv run pytest
uv run python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness
.\scripts\validate-skill.ps1
```

### 5. 変更単位を記録する

1. `docs/tasks/TASK_TEMPLATE.md` から task seed を作る。
2. 検収時に `docs/acceptance/ACCEPTANCE_TEMPLATE.md` から acceptance record を作る。
3. release readiness を残す場合は、必要に応じて `docs/release-review-YYYYMMDD.md` を追加する。

## Confirm

- `README.md`、`HUB.codex.md`、`BLUEPRINT.md`、`RUNBOOK.md`、`GUARDRAILS.md`、`EVALUATION.md` の役割が重複しすぎていない。
- task seed と acceptance record が相互参照できる。
- Skill の振る舞い変更が schema / example / golden / rubric に追随している。
- mobile 対象では `mobile_contexts` と `platform_matrix` が artifact と docs に反映されている。
- `uv run pytest` と Skill validator が通る。

## Rollback / Retry

- schema 変更で既存 example が通らない場合は、先に契約差分と example の期待値を見直す。
- golden 更新が必要な場合は、期待 anchor の意味を維持したまま更新する。
- validation が環境依存で失敗した場合は、Windows では `python` より `uv run python` を優先する。
