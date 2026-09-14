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

## Gate Profiles

| profile | auto evidence | manual evidence | residual risk |
|---|---|---|
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

フィールドと移行手順は[artifact契約](artifact-contract.md#実行構成と欠陥履歴)を正本とする。
