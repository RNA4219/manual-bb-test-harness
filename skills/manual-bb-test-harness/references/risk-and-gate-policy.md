# Risk and Gate Policy

## Risk Formula

```text
I = impact (1..5)
L = likelihood (1..5)
D = detectability difficulty (0..3)
C = change surface / shared asset reach (0..3)
X = externality / network-device dependency (0..3)
P = privilege or data sensitivity (0..3)
A = auto coverage credit on impacted path (0..3)

raw = 4*(I*L) + 2*D + 2*C + 2*X + 2*P - 2*A
risk_score = round(min(100, raw * 100 / 124))
```

| priority | score |
|---|---|
| `P0` | `>= 70` |
| `P1` | `55..69` |
| `P2` | `35..54` |
| `P3` | `< 35` |

各scoreは平易な言葉で説明する。automation creditで高impact項目を下げる場合、根拠となる`source_refs`を示す。

## Gate Profiles 2.0

未指定時は`standard`。支払い、認証、個人データ、共有library、不可逆操作には`strict`を使い、`lean`はblast radiusが狭いhotfixに限定する。

| profile | automation | manual evidence |
|---|---|---|
| `strict` | changed-code >= 80%、blocker/critical 0、hotspot review 100% | P0/P1 100%、mandatory observation 100% |
| `standard` | changed-code >= 75%、blocker/critical 0 | P0 100%、P1 >= 95%、mandatory observation >= 95% |
| `lean` | impacted-module >= 60%、blocker/critical 0 | P0 100%、P1 >= 80%、mandatory observation >= 80% |

`manual_case_set`全件を分母にし、証跡なしは`untested`とする。同じcase/buildの複数証跡は最新timestampを採用し、同時刻は曖昧入力として拒否する。対象`feature_id`と`build_id`が一致する証跡だけを評価する。

## Decision Rules

Go:

- profileのautomation、P0/P1、mandatory observation閾値をすべて満たす
- open blocker/critical/high defectがない
- 未解決critical assumptionがない
- unwaived blocking riskがない
- 判定理由が1件以上ある

Conditional Go:

- waiver可能なのは、risk IDへ追跡できるP1閾値未達、mandatory observation未実行、またはstandard/strictの残余riskだけである
- 構造化`waiver_set`は`id / risk_ids / reason / owner / expires_at / containment / rollback`を持ち、未失効で、対象条件の全risk IDを覆う
- P0 fail/blocked/unknown/untested、open blocker/critical/high defect、未解決critical assumption、automation証跡不足またはprofile閾値未達はwaiver不可

No-Go:

- P0が0件、またはP0の非passが1件以上
- open blocker/critical/high defect
- 未解決critical assumption
- automation証跡不足またはprofile閾値未達
- mandatory observationまたはP1閾値未達で、有効なwaiverがない
- unwaived blocking riskがある

`no_go`は正常な評価結果なのでexit code 0。schema不正、identity不一致、timestamp欠落、曖昧な重複などの入力不正はexit code 1。

## Evidence Checks

次を一体で評価する。

1. spec completenessとcritical assumption
2. manual case全件の実行状態
3. automation coverage、新規issue、hotspot review
4. mandatory/high-risk observation実行率
5. open defect
6. residual/blocking riskとwaiver

coverage単独でrelease readinessを決めてはならない。

## Stakeholder Alignment

profile、coverage閾値、P0/P1、残余risk、waiver承認者、rollback/containmentをTech Lead・QA Lead・PM間で合意し、Go/No-Go briefには判定build、未充足条件、適用waiver、残余risk、rollbackを明記する。
