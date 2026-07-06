---
task_id: 20260530-02
intent_id: INT-MBB-RELEASE-READINESS-001
owner: manual-bb-test-harness
status: ready
last_reviewed_at: 2026-05-30
next_review_due: 2026-06-06
---

# Agent Instructions: Release Readiness Training

## 目的

`manual-bb-test-harness` を、公開リポジトリとして説明しやすい release readiness へ引き上げる。

この作業では、単に coverage 数値を上げるのではなく、次の問いに証跡付きで答えられる状態を作る。

- どの品質ゲートを満たしているか。
- どの artifact が release 対象で、検証済みか。
- どのテストが P0 / P1 リスクを押さえているか。
- coverage 強化によって、manual case が white-box 偏重になっていないか。
- security / dependency / secret 境界に未解決リスクが残っていないか。
- 最終的に Go / Conditional Go / No-Go のどれか。

## 作業対象

- repo: `..\manual-bb-test-harness`
- task seed: `docs/tasks/task-release-readiness-training-20260530.md`
- acceptance record 予定: `docs/acceptance/AC-20260530-02.md`
- release review 予定: `docs/release-review-20260530.md`

## 最初に読むもの

1. `AGENTS.md`
2. `README.md`
3. `HUB.codex.md`
4. `BLUEPRINT.md`
5. `RUNBOOK.md`
6. `GUARDRAILS.md`
7. `EVALUATION.md`
8. `docs/tasks/task-release-readiness-training-20260530.md`

必要になった場合だけ読む。

- `skills/manual-bb-test-harness/SKILL.md`
- `skills/manual-bb-test-harness/references/artifact-contract.md`
- `skills/manual-bb-test-harness/references/risk-and-gate-policy.md`
- `docs/workflow-cookbook/adoption-tiers.md`

## 実行方針

- 日本語で記録する。
- 既存の repo 構造、命名、テスト方針を優先する。
- `SKILL.md` は短く保ち、長い説明は `references/` または `docs/` に置く。
- artifact contract を変える場合は、`schemas/`、`examples/artifacts/`、`goldens/`、tests を同時に見る。
- golden は厳密 snapshot ではなく review anchor として扱う。
- 既存の未関係変更は戻さない。
- 変更ごとに validation を実行し、実行コマンドと結果を release review / acceptance record に残す。

## 現在の既知状態

- `uv run pytest`: 419 passed
- `uv run ruff check .`: All checks passed
- Skill validator: passed
- `validate-artifact --all --strict`: 14 valid, 0 invalid
- `validate-spec --all`: 4 PASS, 0 FAIL
- Workflow Cookbook Tier: Tier 3 Complete
- Workflow Cookbook freshness: PASS
- coverage 実測: 53%
- 主な弱点:
  - `scripts/evaluate-gate.py`
  - `scripts/risk-heatmap.py`
  - `scripts/validate-spec.py`
  - `scripts/spec-ingest.py`
  - `scripts/import-testrail.py`
  - `scripts/import-xray.py`

## 優先作業

### P0: Coverage Gate と Direct Script Main 補強

1. 現在の coverage baseline を再取得する。
2. `evaluate-gate.py` の `go / conditional_go / no_go` 分岐を fixture 化する。
3. `risk-heatmap.py` の HTML 出力、空入力、不正入力、P0-P3 表示をテストする。
4. `validate-spec.py` の成功 / 失敗 / exit code / quality score をテストする。
5. direct script と CLI wrapper の差分が残らないようにする。

### P0: Black-box Fidelity Gate

1. coverage を上げるための white-box / gray-box テストと、release 判定に使う black-box golden / scenario を分けて記録する。
2. `order-cancel`、`mobile-session-resume`、`admin-role-change` の golden を black-box review anchor として再評価する。
3. P0 / P1 scripted case の `source_ref`、`oracle`、`trace_to`、user-visible expected result を確認する。
4. 内部関数名、内部変数、実装順序を根拠にした manual case があれば、unit test または exploratory charter に移す。
5. release review に coverage gate とは別に black-box fidelity 判定を記録する。

禁止:

- coverage だけを release Go の根拠にする。
- 内部実装詳細を manual case の expected result にする。
- 仕様根拠のない expected result を scripted case に入れる。

### P0: Release Artifact Validation

1. release artifact に含める対象を明文化する。
2. dry-run で artifact を生成または検証できる script / command を用意する。
3. artifact 内の Skill frontmatter、schema JSON、example JSON、UTF-8、README 導線を検証する。
4. 結果を `docs/release-review-20260530.md` に記録する。

### P1: Security / Dependency Scan

1. `uv lock` の再現性と依存関係 audit 手順を確認する。
2. GitHub Actions の action version 方針を確認する。
3. secret 不要な dry-run と secret 必須の本実行の境界を RUNBOOK に記録する。
4. 未解決リスクがある場合は owner / due date / waiver を残す。

### P1: Acceptance / Release Review 証跡

1. `docs/release-review-20260530.md` を作成する。
2. `docs/acceptance/AC-20260530-02.md` を作成する。
3. 実行コマンド、結果、coverage、artifact、security、残余リスク、判定を記録する。

## 実行コマンド候補

まず baseline。

```powershell
uv run pytest
uv run ruff check .
uv run pytest --cov=scripts --cov=src\bb_harness --cov-report=term-missing
uv run python scripts\quick-validate-skill.py skills\manual-bb-test-harness
.\scripts\validate-skill.ps1
uv run python scripts\validate-artifact.py --all examples\artifacts --strict
uv run python scripts\validate-spec.py --all
uv run python tools\ci\check_workflow_cookbook_tier.py --repo . --expected-tier 3
uv run python tools\ci\check_workflow_cookbook_freshness.py --repo . --strict
```

必要に応じて対象テストを絞る。

```powershell
uv run pytest tests\test_error_branches.py tests\test_cli_coverage.py
uv run pytest tests\test_import_status.py tests\test_spec_ingest.py
uv run pytest tests\test_scripts_coverage.py
```

## 完了条件

- `uv run pytest` が成功する。
- `uv run ruff check .` が成功する。
- Skill validator が成功する。
- artifact / spec validation が成功する。
- Workflow Cookbook Tier 3 と freshness が維持される。
- 総合 coverage が 70% 以上になる。
- P0 対象スクリプトの主要分岐 coverage が 80% 以上になる。
- P0 / P1 scripted case の 100% が `source_ref`、`oracle`、`trace_to` を持つ。
- user-visible behavior で説明できない scripted case が 0 件になる。
- release review に black-box fidelity 判定が記録される。
- release artifact validation の dry-run が成功する。
- security / dependency scan の結果が release review に記録される。
- acceptance record が作成され、判定が `go` または明示的 waiver 付き `conditional_go` になる。

## Go / No-Go 判定

- Go:
  - 完了条件をすべて満たし、black-box fidelity gate が pass、残余リスクが P1 以下で owner / due date 付き。
- Conditional Go:
  - coverage 70% 以上、P0 分岐 coverage 80% 以上、black-box fidelity gate pass、release artifact validation 成功。ただし P1 残余リスクがある。
- No-Go:
  - P0 fail、coverage 70% 未満、black-box fidelity gate fail、artifact validation failure、critical assumption unresolved、または secret / release 手順の未定義が残る。

## エージェントへの開始プロンプト

```text
..\manual-bb-test-harness で release readiness training を実行してください。

まず AGENTS.md、README.md、HUB.codex.md、BLUEPRINT.md、RUNBOOK.md、GUARDRAILS.md、EVALUATION.md、docs/tasks/task-release-readiness-training-20260530.md、docs/tasks/agent-instructions-release-readiness-training-20260530.md を読んでください。

目的は、manual-bb-test-harness を監査可能な release readiness へ引き上げることです。現在の弱点は coverage 53%、特に evaluate-gate.py、risk-heatmap.py、validate-spec.py、spec-ingest.py、import-testrail.py、import-xray.py の direct script main / error branch 周辺です。coverage 強化によって manual case が white-box 偏重にならないよう、black-box fidelity gate も P0 として扱ってください。

最初に baseline validation を実行し、結果を確認してください。その後、P0 から順に coverage gate、black-box fidelity gate、release artifact validation、security / dependency scan、release review、acceptance record を整備してください。

完了時は uv run pytest、uv run ruff check .、Skill validator、validate-artifact、validate-spec、Workflow Cookbook Tier 3、freshness check を通し、coverage 70% 以上、P0 対象主要分岐 coverage 80% 以上、P0 / P1 scripted case の source_ref / oracle / trace_to 100%、user-visible behavior で説明できない scripted case 0 件を満たしてください。結果は docs/release-review-20260530.md と docs/acceptance/AC-20260530-02.md に日本語で記録してください。
```
