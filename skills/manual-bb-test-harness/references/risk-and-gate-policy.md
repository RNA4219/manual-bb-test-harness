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
risk_score = round(min(100, raw * 100 / 124))
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
| `strict` | changed-code coverage >= 80%, new issues 0, hotspot review 100% | P0/P1 100% pass, high-risk observations 100% executed | unresolved high risk 0 |
| `standard` | changed-code coverage >= 75%, new blocker/critical 0 | P0 100% pass, P1 >= 95%, high-risk observations >= 95% executed | high 0, medium has owner |
| `lean` | impacted-module coverage >= 60%, new blocker 0 | P0 100% pass, direct and indirect required regression executed | medium can be waived |

If the user has no profile, choose `standard`. Use `strict` for payment, auth, personal data, broad shared-library changes, or irreversible operations. Use `lean` only for small hotfixes with narrow blast radius.

## Gate Decision

Go:

- blocker/high defect = 0
- P0 all pass
- required P1 threshold met
- residual risk is within agreed threshold
- no critical assumption unresolved

Conditional Go:

- blocker = 0
- named waiver exists
- owner, due date, and rollback or containment exist
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
