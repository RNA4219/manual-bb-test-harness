# Failure Modes

Use this reference when reviewing or improving outputs from this skill.

## Common Failure Modes

| failure | symptom | correction |
|---|---|---|
| Case-first generation | User story turns directly into test cases with no coverage model | Build `test_model` first and list coverage items before cases |
| Oracle invention | Expected results are plausible but not tied to source refs | Require `oracle.refs`; demote unsupported checks to exploratory charters |
| Over-broad P0/P1 | Almost every risk becomes high priority | Re-score with impact, likelihood, modifiers, and automation credit |
| Coverage-number bias | Gate decision follows code coverage only | Evaluate manual evidence, defects, residual risk, and sign-off separately |
| Missing invalid paths | Only happy path and simple negative checks appear | Add invalid transitions, unauthorized roles, duplicate operations, and external failure |
| Hidden role gaps | Roles are named but ownership context is missing | Use `role x action x resource_state x ownership_context` |
| State collapsed into rules | Lifecycle behavior is represented only as decision rows | Create states, valid transitions, and invalid transitions explicitly |
| Data as precondition only | Test data appears only inside cases | Extract data partitions, boundaries, and history seeds into `test_model` |
| Weak regression scope | Only changed UI is tested | Add direct, shared asset, and external integration regression edges |
| Vague exploratory work | Exploratory tests have no scope or questions | Use charters with scope, questions, timebox, and traceability |

## Review Questions

- Are all P0/P1 observations backed by source refs or explicit assumptions?
- Does every scripted case have an oracle and observable expected result?
- Are boundary, invalid transition, duplicate operation, permission, and recovery checks present where relevant?
- Does the Gate decision mention unresolved assumptions and residual risks?
- Are gray/white signals used as supporting evidence instead of replacing black-box acceptance?
