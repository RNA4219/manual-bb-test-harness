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
| Severity copied to priority | A vulnerability finding rated high becomes P0 without the risk formula | Score it with the formula; promote the case only for a listed reason |
| Unrouted finding | A vulnerability finding has no case, no unit-test proposal and no recorded out-of-scope reason | Route every finding and record the reason for each one that did not become a case |
| Test that exhausts a shared resource | A security case really uses up a shared number range, quota or mailbox | Stop at the limit, record the remaining amount before starting, and use prepared data only |
| Keyword-based routing | A step is sent to a human because it mentions a camera or a printer, without checking what the step actually needs | Route by what the step requires: an object outside the screen, an unreachable dialog, or a human sense |
| LLM pass without evidence | An LLM-executed item is marked pass with no observed value or attachment, or after steps that were not in the case | Record the observed value and evidence per expected result; use blocked when the steps cannot be followed |
| LLM run counted as automation | An LLM-executed run is used as automation evidence or as credit A | Count it as manual execution evidence only |
| Dropped review findings | Review findings are skipped with no recorded reason | Decide each finding; record the rejected ones with the reason |
| Scope-out kept as skip or waiver | Out-of-scope checks stay in the case set as skipped, or are listed as waivers | Remove out-of-scope cases from the set, record who decided and when, and name the owner of that risk in the brief |
| Silent slimming | The output is shortened without a request, or a light version drops the risk table or the Gate | Slim only on request; keep sourced observations, the risk table and the Gate; list what was cut and why |
| Unsorted open questions | Every `[要確認]` is forwarded as a question, including items the sources already answer | Triage first: resolve from the sources, rewrite the expected result, mark implementation-only behavior for confirmation, and ask only the rest |
| Unexplained promotion | A risk-table priority is rewritten above the formula band, or a case is rated above its risks with no recorded reason | Keep the risk table at the formula band; promote the case only for a listed reason and record it in `trace_to` |
| Unrecorded automation exclusion | Manual cases are dropped because automated tests exist, but the excluded observations and the covering tests are not listed | List each excluded observation with the test location, cite it for credit A, and keep the P0 main flow manual |
| Go before execution | The design-time Gate says `go` or `conditional_go` although no manual result exists | Use `no_go`, state that it is before execution, and list the unmet conditions |
| Hand-computed risk scores | A score or priority in the Markdown risk table does not match the documented formula | Run `bb-harness check risk --input <design.md>` and fix every mismatch and unverifiable row before delivery |

## Review Questions

- Are all P0/P1 observations backed by source refs or explicit assumptions?
- Does every scripted case have an oracle and observable expected result?
- Are boundary, invalid transition, duplicate operation, permission, and recovery checks present where relevant?
- Does the Gate decision mention unresolved assumptions and residual risks?
- Are gray/white signals used as supporting evidence instead of replacing black-box acceptance?
