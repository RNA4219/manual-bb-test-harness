# Output Templates

## Ready / Phase Contract

[ready-phase-contract.md](ready-phase-contract.md) の「Markdown 出力」と同じ内容。直すときは両方を直す。

```md
## Definition of Ready
- status: ok | degraded | blocked
- decision: ready | ready_with_conditions | not_ready
- reasons:
- required_before_dev:

## Phase Contract
- problem_owner:
- target_problem:
- success_conditions:
- phase1_scope:
- phase1_non_goals:
- metrics:

## 未決事項
| id | severity | question | owner | due | blocks_ready | source |
|---|---|---|---|---|---|---|

## 仕様不足
| id | severity | gap | impact | needed_oracle | source |
|---|---|---|---|---|---|

## 技術リスク
| id | severity | risk | mitigation | owner | source |
|---|---|---|---|---|---|

## 初期テスト観点
| id | lens | title | rationale | trace_to |
|---|---|---|---|---|

## Go/No-Go 判断材料
- go_when:
- no_go_when:
- deadline_risk:
- evidence_needed:
```

## Markdown Response

```md
## Intake Status
- status: ok | degraded | blocked
- assumptions:
- blockers:

## 自動テストと重なるので外した観点
| 外した観点 | 自動テストの根拠（ファイルと行、テスト名） | 手動に残したもの |
|---|---|---|

## 根拠付き観点
| id | coverage_item | mandatory | title | view | techniques | source | rationale |
|---|---|---|---|---|---|---|---|

## Coverage Model
- data_partitions:
- boundaries:
- rule_columns:
- states:
- valid_transitions:
- invalid_transitions:
- role_matrix:
- regression_edges:
- platform_matrix:
- quality_lenses:
  - id / lens / applicable / reason / owner / oracle:
- improvement_feedback:

## リスク
| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|

## 優先度
- ケースの優先度の決め方:
- 上げたケース（理由ごとの件数）:
- 下げた決まり:

## 手動テストケース
| tc_id | priority | title | preconditions | steps | expected | oracle | trace_to | executor | minutes |
|---|---|---|---|---|---|---|---|---|---:|

## 探索チャーター
| id | priority | title | scope | questions | timebox | session notes | findings | retrospective | trace_to |
|---|---|---|---|---|---:|---|---|---|---|

## テスト計画
- objective / test_level:
- entry_criteria:
- stop_conditions:
- resume_conditions:
- data_readiness / environment_readiness:
- executors（LLM と手動の件数、LLM の道具と環境の前提、手動に残した理由）:
- estimate_basis / uncertainty:

## 工数
- prep:
- execution:
- evidence:
- retry buffer:
- total:

## Gate
- profile:
- decision: go | conditional_go | no_go
- reasons:
- unmet_conditions:
- blocking_risks:
- waivers:

## Go/No-Go Brief
- feature:
- decision:
- top risks:
- coverage gaps:
- evidence:
- residual risk:
- required follow-up:

## 未決事項
| id | severity | question | known | blocks | owner | due | source |
|---|---|---|---|---|---|---|---|

## 変更の記録
| date | trigger | changed | not_adopted_and_why |
|---|---|---|---|
```

`executor` は `LLM` か `手動：理由`。決まりは [execution-routing.md](execution-routing.md) を使う。

`question` は選べる形で書く。`known` は今わかっていること、`blocks` は決まらないと止まるケース・観点・Gate の条件。

`変更の記録` は、出したあとに直したときに足す。`trigger` は、レビュー・回答・差分のどれで、誰の何か。`changed` は、変えた観点・リスク・ケースの ID。採らなかった指摘は、理由を付けて `not_adopted_and_why` に書く。

## 質問の下書き

未決事項を仕様の持ち主に渡すときの形。追認だけを頼むものは、質問と分ける。

```md
期待結果を決められない所が <件数> 件あります。資料で決まる所は外してあります。

1. <A にするか、B にするか>（<止まるケースの ID>）
   今わかっていること: <出典つきの事実>

追認だけお願いしたいもの
- <実装の動きを仮の期待結果にした点>（<ケースの ID>）
```

## 出したあとに直すとき

レビューの指摘、未決事項への回答、仕様や実装の差分を受けて直すときの決まり。

- 指摘は 1 件ずつ、採る・採らないを決める。採らない指摘は理由を付けて残す。理由のない見送りを残さない。
- 別のモデルや別の人のレビューは、原文と照らして確かめてから採る。指摘の件数や一致の数で採否を決めない。
- 回答は、誰が・いつ・どこで答えたかを根拠に残して反映する。
- 直した観点・リスク・ケースの ID を `変更の記録` に書く。リスク表を直したら、検算をやり直す。
- Gate と Brief は、直したあとの内容で書き直す。前の判定を引き継がない。

## 既存の設計をレビューするとき

ほかの人や以前の版が作った設計・ケースを見るときの形。頼まれるまで新しいケースは足さず、元の表は書き換えない。

```md
## 対象と範囲
- 見たもの（版・更新日時）:
- 見ていないもの:
- 自分で確かめたこと / 他者の報告のまま扱うこと:

## 指摘
| id | severity | target | problem | evidence | verified | fix |
|---|---|---|---|---|---|---|

## 既存ケースごとの判定
| target | verdict | required_fix | trace_to |
|---|---|---|---|

## 維持してよい点

## 未決事項
| id | severity | question | known | blocks | owner | due | source |
|---|---|---|---|---|---|---|---|
```

- `severity` は、出す前に直す・直すことを勧める・表記、の 3 段。
- `verified` は、自分で確かめた範囲。再現したのか、資料や実装を読んだだけなのかを書く。
- `verdict` は、残す・直す・分ける・外す、のどれか。
- 観点の母集合、リスク、Gate は、新しく作るときと同じ決まりで見る。足りない観点は指摘として返す。
- [failure-modes.md](failure-modes.md) の表と質問を使う。

## 表計算や外部ツールへ展開するとき

ケースを表計算、TestRail、Xray などの決まった形へ移すときの決まり。

- 作る前に、出力先の列の数・名前・順・意味を確かめる。出したあとで列を合わせ直す前提にしない。
- 出力先が自動で振る番号などの列は、こちらで埋めない。
- 期待結果は、1 項目に 1 つの判定を書く。出力先が 1 行 1 判定の形でも、分けずに移せる。
- ケースの数と、判定の数を分けて数える。
- 移したあと、元の設計と出力先を機械的に比べ、件数と内容が合うことを確かめる。
- 移したあとは、どちらを正本にするかを書く。正本を直したら、もう片方も直すか、古いと書く。

## 日本語の見出しで渡すとき

人に渡す Gate と Brief は、項目名を日本語にしてよい。JSON のキーと、判定の値（`go` / `conditional_go` / `no_go`）は変えない。

| 英語の項目 | 日本語の項目 |
|---|---|
| profile | 判定の基準 |
| decision | 判定 |
| reasons | 理由 |
| unmet_conditions | Go に足りない条件 |
| blocking_risks | 止めているリスク |
| waivers | 例外の承認 |
| top risks | 主なリスク |
| coverage gaps | 見ていない範囲 |
| evidence | 証跡 |
| residual risk | 残るリスク |
| required follow-up | 次に要ること |

## 軽い版

依頼者が軽い版（簡易・軽量）を求めたときだけ使う。こちらの判断で軽くしない。出力の量を絞る話で、Gate の profile とは別。`lean` を選ぶ条件は変わらない。

省かないもの:

- 根拠付き観点。数は絞ってよいが、残した観点には出典を付ける。
- リスク表（式の入力・点数・優先度）と、その検算。
- Gate。実行結果が無ければ、実施前の `no_go` と足りない条件を書く。閾値は緩めない。
- 何を省いたかと、その理由。省いた確認は、Brief の coverage gaps と residual risk に書く。

絞ってよいもの:

- 手動ケース。P0 と P1 の代表に絞り、残りは観点の列挙に留めてよい。
- Coverage Model。当てはまる項目だけを書く。
- 探索チャーターの件数と timebox。
- 環境の組み合わせ。代表の構成に絞り、省いた構成を書く。
- 節の数。8 項目の順は保ったまま、隣り合う項目を 1 つの節にまとめてよい。

観点だけを求められたときは、ケースと工数を作らず、未作成であることと理由を書く。

## Release Brief

```md
# Release Brief

## Summary
- feature:
- decision: go | conditional_go | no_go
- residual_risk:
- top_risks:

## Evidence
- auto_gate:
- manual_execution:
- open_defects:

## Waivers
- id:
- owner:
- approver:
- approved_at:
- approval_ref:
- expires_at:
- containment:

## Required Follow-up
- item:
- due:
```

## Execution Evidence

```json
{
  "run_id": "RUN-2026-04-22-0017",
  "tc_id": "TC-001",
  "feature_id": "FEATURE-001",
  "build_id": "web-1.42.0+1289",
  "case_revision": "case-rev-2",
  "spec_revision": "spec-rev-7",
  "oracle_revision": "oracle-rev-3",
  "case_content_hash": "sha256:case-content",
  "timestamp": "2026-07-11T10:00:00+09:00",
  "env": "stg",
  "device": "iPhone 15 / iOS 18.4",
  "network_profile": "4g-lossy",
  "tester": "qa_a",
  "oracle_type": "specified",
  "oracle_refs": ["AC-2"],
  "expected": ["キャンセル不可メッセージを表示"],
  "actual": ["注文状態が cancelled へ遷移した"],
  "result": "fail",
  "attachments": ["s3://evidence/RUN-001/step2.png"],
  "anomaly_notes": ["出荷済み状態でも CTA が活性だった"],
  "defect_stub": {
    "title": "出荷済み注文がキャンセル可能",
    "severity": "high",
    "status": "open"
  }
}
```
