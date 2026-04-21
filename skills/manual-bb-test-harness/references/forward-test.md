# Forward Test Guide

Use this guide to test whether the skill works on realistic inputs.

## Prompt Template

```text
Use $manual-bb-test-harness at <repo>/skills/manual-bb-test-harness to create a manual black-box test design for <golden input path>.

Return:
1. intake status
2. coverage model
3. observations
4. risks
5. manual cases
6. exploratory charters
7. effort
8. gate decision
9. Go/No-Go brief
```

## Recommended Golden Runs

- `goldens/order-cancel.input.md`
- `goldens/admin-role-change.input.md`

Compare the output against the matching `.expected.md`. The expected files are review anchors, not exact snapshots.

If the team uses Notion as the primary reporting surface, record the run with `docs/notion-report-guide.md` and `docs/notion-forward-test-template.md`. Keep repository files as templates and reusable evaluation assets, not as the canonical run log.

## Pass Criteria

- Output includes a coverage model before manual cases.
- Required coverage items and observations from the expected file are present.
- P0/P1 risks are justified and not assigned to every item.
- Scripted cases include oracle refs.
- Unsupported UX or unclear expected results become exploratory charters.
- Gate decision reflects evidence gaps and residual risk.

## Iteration Rule

If an output fails, update the skill or references rather than only fixing the golden answer. The repo should improve the reusable behavior.
