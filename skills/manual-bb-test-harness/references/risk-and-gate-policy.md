# Risk and Gate Policy

## Risk Formula

Use this default score.

```text
I = impact (1..5)
L = likelihood (1..5)
D = detectability difficulty (0..3)
C = change surface / shared asset reach (0..3)
X = externality / network-device dependency (0..3)
P = privilege or data sensitivity (0..3)
A = auto coverage credit on impacted path (0..3)

raw = 4*(I*L) + 2*D + 2*C + 2*X + 2*P - 2*A
risk_score = round(max(0, min(100, raw * 100 / 124)))
```

Priority:

| priority | score |
|---|---|
| `P0` | `>= 70` |
| `P1` | `55..69` |
| `P2` | `35..54` |
| `P3` | `< 35` |

Explain every score in plain language. If a high impact item receives a low score due to automation credit, state which evidence earns that credit.
自動テストと重なる観点を手動から外したときの A の根拠は、[case-design-policy.md](case-design-policy.md#自動テストと重なる観点) に従う。

## 点数の検算

点数と優先度は暗算で書かない。Markdown の設計書にリスク表を書いたら、提出前に式と照らす。

```powershell
uv run bb-harness check risk --input design.md
```

- I・L・点数の列を持つ表を検算する。補正は `modifiers` の 1 列（`D2 C2 X0 P2 A0`、`D=2 C=2 X=0 P=2 A=0`、`D2/C2/X0/P2/A0`）か、D・C・X・P・A の各列に書く。`raw` の列があれば raw も照らす。
- 補正が 1 つでも欠けた行、範囲外の値、数値として読めないセルは、0 で補わず検算不可として報告する。
- 整数の点数は上の式で照らす。小数 1 桁の点数は Local Mode の出力と同じ丸めで照らす。優先度は、計算し直した点数の帯と比べる。
- 優先度のセルに `P3→P2` のような書き換えがあるときは最後の値を使う。帯と違えば不一致として報告する。リスク表では昇格しない（[ケースの優先度と昇格](#ケースの優先度と昇格)）。
- 終了コードは、全行一致で 0、不一致・検算不可・リスク表なしで 2、入力エラーで 1。`--format json` で行ごとの結果を出す。
- コードブロックの中の表は検算しない。

検算が確かめるのは式との一致だけで、I・L・補正の値が妥当かどうかは人のレビューで確かめる。通る例は repo の `examples/markdown/order-cancel.risk-table.md`。

## ケースの優先度と昇格

リスク表の優先度は、式の帯のまま書く。式より高くしたいときは、リスク表を書き換えず、ケースの優先度を上げる。

- ケースの優先度は、trace 先のリスクのうち最も高い優先度から決める。
- それより上げるのは、次の理由があるときだけ。上げたケースの `trace_to` に `昇格(主経路)` のように理由を書く。
  - `主経路`: その経路が通らないと、機能そのものが使えない。
  - `取り消せない損害`: 失敗すると、資産・権限・個人情報・取り消せない操作に誤りが出る。その経路の代表だけを上げる。
  - `要件の名指し`: 要件や仕様の持ち主が、確認を名指しした経路や値の代表。
- 上げた件数と、理由ごとの内訳を、優先度の説明に書く。理由のない引き上げはしない。
- 期待結果に `[要確認]` が付くケースは P0 にしない。
- 同じリスクのケースを全部同じ優先度にしない。同じ流れの失敗の違い、環境の違い、影響の小さい確認は下げてよい。下げた決まりを優先度の説明に書く。
- mandatory の観点のケースは、優先度が P2 や P3 でも実行の対象になる。実行させるために優先度を上げない。

JSON の `manual_case_set` には昇格の理由を入れる項目が無い。理由は Markdown の優先度の説明と `trace_to` に書く。

## Gate Profiles

| profile | auto evidence | manual evidence | residual risk |
|---|---|---|---|
| `strict` | changed-code coverage >= 80%, new issues 0, hotspot review 100% | 計画したP0/P1 100% pass、high-risk observations 100% executed | unresolved high risk 0 |
| `standard` | changed-code coverage >= 75%, new blocker/critical 0 | 計画したP0 100% pass、P1 >= 95%、high-risk observations >= 95% executed | high 0, medium has owner |
| `lean` | impacted-module coverage >= 60%, new blocker 0 | 計画したP0 100% pass、direct and indirect required regression executed | mediumは明示waiverがある場合だけ受容可 |

If the user has no profile, choose `standard`. Use `strict` for payment, auth, personal data, broad shared-library changes, or irreversible operations. Use `lean` only for small hotfixes with narrow blast radius.

## Gate Decision

Go:

- blocker/high defect = 0
- リスク分析でP0を計画した場合はP0 all pass。P0が存在しない場合はN/Aとして理由を残す
- required P1 threshold met
- residual risk is within agreed threshold
- critical assumptionとblocker/critical/high defectは`resolved`である。`accepted`だけでは解消扱いにしない

Conditional Go:

- blocker = 0
- named waiver exists
- owner、ownerとは別人のapprover、未来でなく期限より前のapproved_at、approval_ref、due date、rollbackまたはcontainmentが存在する
- residual risk is explicitly accepted

No-Go:

- blocker > 0
- P0 fail exists
- critical assumption unresolved
- residual risk exceeds agreed threshold

## 実施前の Gate

設計を出す時点など、手動の実行結果がまだ無いときも Gate は出す。判定は `no_go` とし、`go` や `conditional_go` を仮に置かない。

- `reasons` に、実施前であることを書く。
- `unmet_conditions` に、Go に足りない条件を 1 行ずつ並べる。選んだ profile の閾値に対する未実施の P0/P1、未解決の critical assumption、まだ無い自動証跡を含める。
- Brief の decision も `no_go` とし、再判定に要るものを required follow-up に書く。
- 実行結果がそろったら、同じ profile で判定し直す。

`bb-harness gate` も、実行証跡が無い入力には `no_go` と `unmet_conditions` を返す。

## 対象外・blocked の書き方

- 対象外（scope out）と例外の承認（waiver）を分ける。対象外は、今回の確認の範囲に入れないと決めたもの。waiver は、範囲に入るが、理由と責任者を付けて今回は例外として認めるもの。
- 対象外にしたケースは、ケースの一覧から外す。skip で残すと、未実施として分母に残る。
- 対象外にしたものは、決めた根拠（誰が・いつ）を書く。その範囲のリスクは、持ち主を付けて Brief の residual risk に書き、この Gate の Go がその範囲を保証しないことを書く。
- blocked のケースは、止めている原因と、外れる条件を書く。blocked を実施済みや完了に数えない。
- 外部の表やツールの結果の区分を使うときは、pass / fail / skip / blocked / unknown / untested との対応を先に書く。

## Evidence Checks

Evaluate these six conditions in parallel:

1. spec completeness
2. traceability completeness
3. automation evidence
4. manual pass status
5. open defect status
6. residual risk sign-off

Coverage alone never decides release readiness.

Gateの入力には、受入条件を持つfeature_spec、非空でID付き母集団を持つtest_model、非空のobservation_setを必須とする。
全観点が明示的に optional の集合は、観点未提供・空集合と区別する。
ケースとチャーターをまたぐ ID 重複、および NaN/Infinity を含む入力は判定前に拒否する。
実績の pass / fail / skip / blocked / unknown / untested は排他的に集計し、各区分の和を実行対象数と一致させる。

Retired manual cases are not counted as unexecuted manual evidence. If a case has
`status = retired`, the gate output must list it under `retired_cases` and exclude it from
P0/P1 manual pass-rate denominators. This harness only preserves and validates the
placement-change state; it does not decide whether a case should be retired or whether the
replacement automation is sufficient.

retired の除外後も、自動証跡、未解決欠陥、必須観点の実施状況はそれぞれ検証する。

追加契約1.1.0の `coverage_report` は設計済み・実施済み・合格を分離する。failも実施率へ計数し、unknownとblockedは別表示する。現在はshadowとしてevidence_summaryへ添え、上記profileの閾値・waiver条件・Go/No-Go判断は変えない。ケース更新時はreportを再生成する。詳細は [technique-coverage.md](technique-coverage.md) を参照。

## Stakeholder Alignment

Before using gate profiles, confirm alignment with stakeholders:

### Alignment Checklist

| Item | Question | Stakeholder |
|---|---|---|
| Profile selection | Which profile (strict/standard/lean) applies to this release? | Tech Lead |
| Coverage threshold | Is the coverage threshold acceptable? | Dev Team |
| Manual evidence | Are P0/P1 pass rate thresholds achievable? | QA Lead |
| Residual risk | What is the acceptable residual risk level? | PM |
| Waiver process | Who approves waivers and what is the approval flow? | PM + Tech Lead |
| Rollback plan | Is there a rollback or containment plan for Conditional Go? | Tech Lead |

### Profile Decision Matrix

| Release Type | Recommended Profile | Rationale |
|---|---|---|
| Payment/Auth/Personal Data | `strict` | Regulatory compliance, irreversible operations |
| New Feature Launch | `standard` | Default for most releases |
| Hotfix/Narrow Scope | `lean` | Limited blast radius, fast turnaround |
| Shared Library Change | `strict` | Broad impact across dependent services |
| Mobile App Release | `standard` + platform_matrix | Device/network variation coverage |

### Waiver Template

When granting a waiver, document:

```markdown
- Risk ID: [RISK-XXX]
- Content: [Brief description]
- Owner: [Name/Role]
- Due Date: [YYYY-MM-DD]
- Containment: [Rollback plan or monitoring]
- Approval: [Name/Role] approved on [YYYY-MM-DD]
```

### Stakeholder Communication

For Go/No-Go brief:

1. Summarize in 1 page
2. Highlight blockers and waivers
3. State residual risks with owners
4. Provide rollback/containment summary
5. Request explicit sign-off

## 実行構成・欠陥・suiteの判定

- 手動caseは全対象構成のpassが揃ったときだけpassにする。別環境の成功で失敗を上書きしない。未実行構成を詳細実績へ残す。
- 欠陥は全入力履歴と`defect_register`を使ってID単位で扱う。再テストpassだけで未解決欠陥を落とさず、修正済み・確認待ち・再オープンも未解決に含める。
- 台帳のresolvedは、解決時点の確認run、対象構成、時刻を照合してから反映する。IDなしの旧stubはタイトルで自動統合しない。
- 必須suiteは全件成功を要求する。失敗、中断、未実行、skip、0件実行は全profileでNo-Goとなり、waiverで覆さない。
- LLM が実施した結果は、手動の実行結果として数える。自動証跡には数えない。P0 の pass は、人が証跡を確かめた記録があるときだけ数える（[execution-routing.md](execution-routing.md)）。

フィールドと移行手順は[artifact契約](artifact-contract.md#実行構成と欠陥履歴)を正本とする。
