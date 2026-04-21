# Notion Report Guide

Forward-test の主な保存先を Notion にする場合の運用ガイド。

## Database: Skill Forward Tests

Notion database を 1 つ作り、forward-test の実行ごとに 1 page を作る。

推奨 properties:

| property | type | example |
|---|---|---|
| `Name` | title | `order-cancel / v0.1.0 / run-001` |
| `Date` | date | `2026-04-22` |
| `Skill` | select | `manual-bb-test-harness` |
| `Skill revision` | text | git SHA or branch |
| `Golden input` | select | `order-cancel` |
| `Evaluator` | person/text | reviewer name |
| `Decision` | select | `pass`, `conditional pass`, `fail` |
| `Total score` | number | `84` |
| `Missing anchors` | multi-select | `audit log`, `invalid transition` |
| `Failure modes` | multi-select | `Oracle invention`, `Weak regression scope` |
| `Follow-up status` | status | `not started`, `in progress`, `done` |
| `Repo issue/PR` | url/text | link to issue or PR |

## Page Body

Use `docs/notion-forward-test-template.md` as the page body. Keep the body short enough to scan.

Recommended Notion block order:

1. `Summary`
2. `Score table`
3. `Anchor check`
4. `Failure modes`
5. `Decision rationale`
6. `Improvement tasks`
7. `Raw output link or pasted excerpt`

## Usage Rules

- Store the canonical review result in Notion.
- Keep repo templates as source templates, not as the primary run log.
- If a forward-test changes the Skill behavior, update `goldens/`, `references/`, or schemas in the repo.
- Do not paste huge raw outputs into the main Notion body. Put a short excerpt and link to the artifact if needed.
- Use the same category names as `docs/evaluation-rubric.md` so scores remain comparable.

## Decision Mapping

| Notion decision | meaning |
|---|---|
| `pass` | usable without repo change |
| `conditional pass` | usable, but one or more improvement tasks should be tracked |
| `fail` | update Skill/references before trusting the output |
