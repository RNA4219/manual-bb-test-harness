---
task_id: 20260530-02
intent_id: INT-MBB-RELEASE-READINESS-001
owner: manual-bb-test-harness
status: completed
last_reviewed_at: 2026-05-30
next_review_due: 2026-06-06
---

# Task Seed: Release Readiness Training

## 背景

- `manual-bb-test-harness` は Workflow Cookbook Tier 3、Skill 検証、schema / artifact 検証、419 件のテストを満たしている。
- 一方で、公開リポジトリとして release readiness を示すには、総合 coverage、release artifact 検証、security / dependency scan、CI gate の証跡がまだ薄い。
- 2026-05-30 の実測では `uv run pytest --cov=scripts --cov=src\bb_harness --cov-report=term-missing` が 419 passed、総合 coverage 53%。
- 弱点は `evaluate-gate.py`、`risk-heatmap.py`、`validate-spec.py`、`spec-ingest.py`、TestRail / Xray import の direct script main / error branch 周辺に集中している。

## ゴール

- 「基本的な保守品質」から「監査可能な release readiness」へ引き上げる。
- coverage 数値だけでなく、gate 判定、release artifact、security、dependency、traceability の証跡を揃える。
- 完了時に `conditional_go` ではなく `go` と判断できる acceptance record を作成する。

## 実施対象

1. Coverage training
   - `evaluate-gate.py` の判定分岐、profile 差分、defect / waiver / residual risk のテストを追加する。
   - `risk-heatmap.py` の HTML 出力、空入力、P0-P3 表示、invalid JSON / schema 欠落のテストを追加する。
   - `validate-spec.py` の requirement / acceptance 抽出、失敗条件、CLI exit code をテストする。
   - `spec-ingest.py` の Confluence / Jira stub、mobile context、missing oracle、blocked / degraded assumption を追加検証する。
   - TestRail / Xray import の API error、token 不足、unknown status、attachment / defect edge を direct script と CLI の両方で確認する。
2. Black-box fidelity training
   - coverage 強化によって、成果物評価が white-box 偏重にならないようにする。
   - `order-cancel`、`mobile-session-resume`、`admin-role-change` の golden を black-box review anchor として再評価する。
   - P0 / P1 scripted case の `source_ref`、`oracle`、`trace_to`、user-visible expected result を確認する。
   - 内部関数名、内部変数、実装順序に依存した expected result があれば、unit test または exploratory charter に移す。
   - release review に coverage gate とは別に black-box fidelity 判定を記録する。
3. CI gate training
   - CI に coverage report を必須証跡として残す。
   - coverage gate の初期基準を 70% に置き、80%、90% へ段階的に上げる。
   - Windows / Ubuntu / macOS と Python 3.10 / 3.11 / 3.12 の既存 matrix を維持する。
4. Release artifact training
   - tag release 時に skill bundle、schemas、examples、goldens、exports、docs を含む artifact を生成する。
   - artifact zip の中身、JSON schema、Skill frontmatter、UTF-8、README 導線を release validation で検証する。
5. Security / dependency training
   - `uv lock` の再現性、依存関係 audit、GitHub Actions の pinned version 方針を確認する。
   - secret が不要な dry-run と、secret 必須の本実行の境界を RUNBOOK に明記する。
6. Audit evidence training
   - `docs/release-review-YYYYMMDD.md` に coverage、CI、artifact、security、残余リスクを記録する。
   - `docs/acceptance/AC-YYYYMMDD-xx.md` に実行コマンド、結果、判定、waiver 有無を残す。
   - Workflow Cookbook freshness check を変更後に再実行する。

## 優先度

| 優先度 | 対象 | 理由 |
|---|---|---|
| P0 | coverage gate と direct script main の補強 | 実測 53% は監査時に最初の説明コストになる |
| P0 | black-box fidelity gate | coverage 強化で手動 QA 設計が white-box 偏重になるのを防ぐ |
| P0 | release artifact validation | 配布物と repo の差分を説明できないと release readiness が弱い |
| P1 | security / dependency scan | 外部利用・監査で必ず聞かれる |
| P1 | acceptance / release review 証跡 | 「通った」ではなく「誰が何を根拠に Go としたか」を残す |
| P2 | coverage 90% への段階引き上げ | 一気に 90% を狙うより、薄い領域を潰してから gate 化する |

## 完了条件

- [x] `uv run pytest` が成功する
- [x] `uv run ruff check .` が成功する
- [x] `uv run python scripts\quick-validate-skill.py skills\manual-bb-test-harness` が成功する
- [x] `.\scripts\validate-skill.ps1` が成功する
- [x] `uv run python scripts\validate-artifact.py --all examples\artifacts --strict` が成功する
- [x] `uv run python scripts\validate-spec.py --all` が成功する
- [x] `uv run python tools\ci\check_workflow_cookbook_tier.py --repo . --expected-tier 3` が成功する
- [x] `uv run python tools\ci\check_workflow_cookbook_freshness.py --repo . --strict` が成功する
- [x] 総合 coverage が 70% 以上になる
- [x] P0 対象スクリプトの主要分岐 coverage が 80% 以上になる
- [x] P0 / P1 scripted case の 100% が `source_ref`、`oracle`、`trace_to` を持つ
- [x] user-visible behavior で説明できない scripted case が 0 件になる
- [x] release review に black-box fidelity 判定を記録する
- [x] release artifact validation の dry-run が成功する
- [x] security / dependency scan の結果と残余リスクを release review に記録する
- [x] acceptance record を作成し、判定を `go` または明示的な waiver 付き `conditional_go` にする

## トレーニングメニュー

### Day 1: Coverage Baseline

- 現在の coverage XML / term-missing を保存する。
- coverage 53% の内訳から P0 ファイルを固定する。
- `evaluate-gate.py` と `risk-heatmap.py` の branch map を作る。

### Day 2: Gate / Heatmap 強化

- gate 判定の `go / conditional_go / no_go` 分岐を fixture 化する。
- defect、waiver、blocked、P0 fail、critical assumption のケースを追加する。
- heatmap の正常 / 空 / 不正入力を CLI と関数単位で検証する。
- coverage 目的の white-box テストと、release 判定用の black-box golden を分けて記録する。

### Day 3: Spec / Ingest 強化

- `validate-spec.py` の失敗パターンを増やす。
- `spec-ingest.py` の Markdown / Confluence / Jira / mobile 差分を fixture 化する。
- missing oracle と assumption の degraded / blocked 境界を明文化する。
- `order-cancel`、`mobile-session-resume`、`admin-role-change` の golden を black-box fidelity の観点で再確認する。

### Day 4: Import / Export 強化

- TestRail / Xray import の API 失敗、unknown status、attachment、defect edge を追加する。
- Notion export の dry-run と secret 必須実行の境界をテストする。
- CLI wrapper と direct script の差分を潰す。

### Day 5: Release / Security 証跡

- release artifact dry-run を追加する。
- dependency / security scan の手順を RUNBOOK に追記する。
- release review と acceptance record を作成する。

## Go / No-Go 基準

- Go:
  - 完了条件をすべて満たし、black-box fidelity gate が pass、残余リスクが P1 以下で owner / due date 付き。
- Conditional Go:
  - coverage 70% 以上、P0 分岐 coverage 80% 以上、black-box fidelity gate pass、release artifact validation 成功。ただし security scan などに P1 残余リスクがある。
- No-Go:
  - P0 fail、coverage 70% 未満、black-box fidelity gate fail、artifact validation failure、critical assumption unresolved、または secret / release 手順の未定義が残る。

## 参照

- [Agent Instructions](agent-instructions-release-readiness-training-20260530.md)
- [Blueprint](../../BLUEPRINT.md)
- [Runbook](../../RUNBOOK.md)
- [Evaluation](../../EVALUATION.md)
- [Guardrails](../../GUARDRAILS.md)
- [Workflow Cookbook Tier Check](../workflow-cookbook/adoption-tiers.md)
