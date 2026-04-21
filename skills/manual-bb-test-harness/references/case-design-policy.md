# Case Design Policy

## Coverage Model

Split the test surface into these dimensions.

| dimension | prompts |
|---|---|
| `flow` | 主経路、代替経路、中断、再試行、戻る/キャンセル |
| `state` | 有効遷移、無効遷移、終端状態、二重実行 |
| `rule` | 条件組合せ、例外、優先順位、競合ルール |
| `data` | 同値クラス、境界値、null/empty、形式違反、履歴依存 |
| `role` | role x action x resource_state x ownership_context |
| `regression` | 直接影響、共有資産経由、外部連携経由 |

## Observation Extraction Checklist

Treat observation extraction as coverage item discovery. Do not jump directly from a user story to test cases.

1. Atomize acceptance criteria and business rules into one behavior per line.
2. Extract rule candidates from condition words such as `if`, `only when`, `unless`, `except`, `cannot`, `after`, `before`, and `when role is`.
3. Extract state candidates from lifecycle nouns and verbs such as draft, pending, approved, shipped, cancelled, expired, retry, revoke, restore, and archive.
4. Extract data dimensions from inputs, configuration values, time, external responses, locale, device, network profile, feature flags, and permissions.
5. Extract role dimensions as `role x action x resource_state x ownership_context`.
6. Extract regression edges from changed areas, shared libraries, schema changes, external integrations, and reused UI/API flows.
7. Mark each coverage item as mandatory or optional before synthesizing cases.

Minimum `test_model` coverage items:

- `data_partitions`
- `boundaries`
- `rule_columns`
- `states`
- `valid_transitions`
- `invalid_transitions`
- `role_matrix`
- `regression_edges`
- `quality_lenses`

## Technique Rules

- Use equivalence partitioning for input categories and valid/invalid classes.
- Use 3-value boundary value analysis for ordered high-risk partitions.
- Use decision tables when behavior depends on combinations of business rules.
- Use state transition tables for lifecycle features. Include invalid transitions for high-risk flows.
- Use exploratory charters for usability, compatibility, environment-specific behavior, and ambiguous areas.
- Add quality lenses outside pure function behavior: usability, compatibility, flexibility/adaptability, environment difference, user context, recovery, and error messaging.
- Include idempotency and duplicate operation checks for submit, cancel, refund, invite, retry, and webhook-like flows.
- Include interruption and recovery checks for multi-step flows, mobile app backgrounding, network loss, expired session, and partial external failure.

## Oracle Priority

| priority | oracle_type | rule |
|---|---|---|
| 1 | `specified` | AC、仕様、API 契約、業務ルール、状態遷移を優先する |
| 2 | `derived` | 旧版比較、既存承認挙動、DB 差分、ログ比較、メタモルフィック関係で補う |
| 3 | `implicit` | クラッシュしない、リンク切れしない、権限外アクセスしないなどの補助に限る |
| 4 | `human` | UX 妥当性やドメイン判断。`[要確認]` と reviewer を必須にする |

Scripted case requires `oracle.type` and `oracle.refs`. If no acceptable oracle exists, create an exploratory charter or a blocker instead.

## Data Strategy

Use these data layers.

| layer | use |
|---|---|
| `canonical_valid` | 標準的に成功するデータ |
| `invalid_single_fault` | 1 要因だけ壊したデータ |
| `boundary3` | min-1, min, min+1 / max-1, max, max+1 |
| `rule_combo` | business rule の重要組合せ |
| `state_seed` | lifecycle の初期状態 |
| `history_seed` | 過去注文、期限切れ、既使用、再実行など履歴依存 |

For multiple data dimensions, start with pairwise. Promote high-risk pairs to full combination only when the risk rationale is explicit.

## Case Quality Bar

A manual scripted case is acceptable only when it has:

- clear preconditions and required data,
- observable steps,
- expected results tied to an oracle,
- traceability to at least one observation and one source or assumption,
- priority derived from a risk item,
- an estimate that includes evidence capture when needed.

If a case is useful but lacks an oracle, convert it to an exploratory charter and label the open question.

## Missing Information

Classify sufficiency as:

- `ok`: scripted cases and gate can be produced.
- `degraded`: core black-box cases can be produced, but environment/device/network or secondary oracle is incomplete.
- `blocked`: critical rule oracle, permission matrix, state model, or change scope is missing.

Keep `[要確認]` in titles or notes for assumptions that affect coverage, expected results, or gate readiness.
