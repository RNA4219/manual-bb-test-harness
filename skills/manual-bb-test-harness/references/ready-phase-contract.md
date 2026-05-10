# Ready Phase Contract

## 目的

企画、モック、ラフな要件メモを、開発に渡せる Phase 1 契約へ正規化する。リリース前の品質ゲートではなく、締め切りや実装着手を決める前の Definition of Ready を扱う。

## 入力

- モック、画面遷移、企画メモ、ユーザーストーリー
- 想定ユーザー、業務課題、成功条件、制約
- 既知の締め切り、依存先、技術前提
- 過去の不具合、問い合わせ、競合仕様、法務や運用メモ

## 必須項目

`phase_contract` では次を必須にする。根拠がない項目は推測で埋めず、`open_questions` または `spec_gaps` に落とす。

| field | 内容 | blocked 条件 |
|---|---|---|
| `problem_owner` | 誰のどの課題か | 対象ユーザーや課題が特定できない |
| `success_conditions` | Phase 1 成功を判定できる条件 | 検証可能な成功条件がない |
| `phase1_scope` | Phase 1 で作ること | 主要 flow が in scope として切れない |
| `phase1_non_goals` | Phase 1 でやらないこと | 範囲外が曖昧でスコープ膨張が避けられない |
| `open_questions` | 未決事項 | critical の未決事項が残る |
| `spec_gaps` | 仕様不足 | oracle や状態、権限、データ境界が決められない |
| `technical_risks` | 実装前に見えている技術リスク | Phase 1 の成立性に関わる高リスクが未対策 |
| `metrics` | 観測する指標 | 成功条件と結びつく指標がない |
| `test_lenses` | 初期テスト観点 | 最低限の happy path / boundary / state / role 観点がない |

## Ready 判定

`readiness.status` は `ok / degraded / blocked` のいずれかにする。

- `ok`: Phase 1 の対象ユーザー、成功条件、in/out、主要 oracle、未決事項の owner が揃っている。
- `degraded`: 軽微または中程度の未決事項はあるが、仮説と owner と期限があり、Phase 1 の範囲を壊さない。
- `blocked`: critical 未決事項、検証不能な成功条件、主要状態/権限/データ境界の欠落、または外部依存の未合意がある。

`critical` な未決事項または仕様不足が 1 件でも open の場合、Ready は `blocked` に寄せる。例外として明示 waiver がある場合のみ `degraded` にできる。

## モックからの変換ルール

1. 画面や導線から `phase1_scope` を抽出する。
2. 画面に存在しないが成功条件に必要な状態、権限、エラー、データ境界を `spec_gaps` にする。
3. 文言や配置から推測した意図は `assumptions` に置き、成功条件にはしない。
4. 実装方式、API、DB、外部連携の不明点は `technical_risks` または `open_questions` に分ける。
5. Phase 1 で確認できる最小の `test_lenses` を作る。詳細ケース化は通常 workflow の `model_test_surface` 以降で行う。

## Markdown 出力

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
