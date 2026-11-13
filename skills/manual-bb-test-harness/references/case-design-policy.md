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
| `platform` | OS、端末、アプリ状態、権限、通知入口、ネットワーク条件 |
| `quality` | 性能、使用性、アクセシビリティ、互換性、信頼性、セキュリティ、保守性、移植性の適用判断 |

## Observation Extraction Checklist

Treat observation extraction as coverage item discovery. Do not jump directly from a user story to test cases.

1. Atomize acceptance criteria and business rules into one behavior per line.
2. Extract rule candidates from condition words such as `if`, `only when`, `unless`, `except`, `cannot`, `after`, `before`, and `when role is`.
3. Extract state candidates from lifecycle nouns and verbs such as draft, pending, approved, shipped, cancelled, expired, retry, revoke, restore, and archive.
4. Extract data dimensions from inputs, configuration values, time, external responses, locale, device, network profile, feature flags, and permissions.
5. Extract role dimensions as `role x action x resource_state x ownership_context`.
6. Extract regression edges from changed areas, shared libraries, schema changes, external integrations, and reused UI/API flows.
7. For mobile targets, extract platform candidates from OS, app lifecycle, install/update state, notification entry, permission state, and network condition.
8. Mark each coverage item as mandatory or optional before synthesizing cases.
9. Record each quality lens as applicable or not applicable. Give applicable lenses an oracle and owner; give excluded lenses a reason and owner.
10. When the security lens applies, or a vulnerability finding is given, use [security-pack.md](security-pack.md) to derive observations and to route each finding.

Minimum `test_model` coverage items:

- `coverage_items` with stable IDs, applicability, criterion, and source refs
- `data_partitions`
- `boundaries`
- `rule_columns`
- `states`
- `valid_transitions`
- `invalid_transitions`
- `role_matrix`
- `regression_edges`
- `platform_matrix` when the target includes iOS, Android, or another mobile app surface
- `quality_lenses`

## Technique Rules

- Use equivalence partitioning for input categories and valid/invalid classes.
- Use 3-value boundary value analysis for ordered high-risk partitions. Treat every
  partition boundary as a value with one nearest value on each side; do not limit
  the analysis to the minimum and maximum of the valid partition.
- Use decision tables when behavior depends on combinations of business rules.
- Use state transition tables for lifecycle features. Include invalid transitions for high-risk flows.
- Use checklist-based testing as an independent technique. Preserve checklist ID, revision, and item-level results.
- Use exploratory charters for usability, compatibility, environment-specific behavior, and ambiguous areas. Preserve timebox, session notes, findings, and retrospective after execution.
- Add structured quality lenses outside pure function behavior: usability, accessibility, performance, compatibility, flexibility/adaptability, environment difference, user context, recovery, security, and error messaging. Record applicability, reason, owner, and an oracle when applicable.
- Include idempotency and duplicate operation checks for submit, cancel, refund, invite, retry, and webhook-like flows.
- Include interruption and recovery checks for multi-step flows, mobile app backgrounding, network loss, expired session, and partial external failure.
- For mobile apps, cover foreground/background/resume, rotation or viewport change when relevant, permission allow/deny, push/deep-link entry, offline to online recovery, and app update or cold-start state when they can alter behavior.

## Oracle Priority

| priority | oracle_type | rule |
|---|---|---|
| 1 | `specified` | AC、仕様、API 契約、業務ルール、状態遷移を優先する |
| 2 | `derived` | 旧版比較、既存承認挙動、DB 差分、ログ比較、メタモルフィック関係で補う |
| 3 | `implicit` | クラッシュしない、リンク切れしない、権限外アクセスしないなどの補助に限る |
| 4 | `human` | UX 妥当性やドメイン判断。`[要確認]` と reviewer を必須にする |

Scripted case requires `oracle.type` and `oracle.refs`. If no acceptable oracle exists, create an exploratory charter or a blocker instead.

実装から読んだ動きを `derived` にするときは、下の「`[要確認]` の仕分け」に従い、追認待ちと書く。

## Multi-run merge

Merge independently derived observations by stable ID and preserve `support_count` and total `run_count`. Use support as a review and confidence signal. Keep mandatory and priority decisions grounded in acceptance criteria, business rules, and product risk; a critical observation found in only one run stays mandatory when its source requires it.

## Data Strategy

Use these data layers.

| layer | use |
|---|---|
| `canonical_valid` | 標準的に成功するデータ |
| `invalid_single_fault` | 1 要因だけ壊したデータ |
| `boundary3` | 各同値パーティション境界とその両隣。min-step, min, min+step / max-step, max, max+step。stepは仕様の精度・入力刻みを使う |
| `rule_combo` | business rule の重要組合せ |
| `state_seed` | lifecycle の初期状態 |
| `history_seed` | 過去注文、期限切れ、既使用、再実行など履歴依存 |

複数次元では選択理由を残してbase-choice、pairwise、n-wise、全組み合わせを選ぶ。実行可能な完全割当から制約を満たすtupleを列挙し、ケース数だけでpairwise達成と判断しない。

形式的な被覆を報告する場合は [technique-coverage.md](technique-coverage.md) を適用する。DomainのON/OFFとIN/OUT、状態の単独遷移とn-switch、決定表の元ルールを統合後も保持する。タイトル、共通観点、ケース数の帳尻合わせでriskを接続しない。

### Boundary value contract

Record the equivalence partitions first, then record each boundary separately with:

- `analysis_type`: `two_value` or `three_value`
- the two partitions separated by the boundary
- whether the boundary value belongs to the lower or upper partition
- the smallest meaningful step, such as `1`, `0.01`, `P1D`, or one lifecycle transition
- the selected values and the selection rationale

For an integer valid range `1..100`, the partitions are `x <= 0`, `1 <= x <= 100`,
and `x >= 101`. The boundaries are `0/1` and `100/101`. A 3-value analysis across
those boundaries uses `-1, 0, 1, 2, 99, 100, 101, 102`; duplicate points may be
merged after recording which boundaries they cover. For dates, decimals, and ordered
states, use the declared step instead of applying a numeric `+/-1` mechanically.

## 自動テストと重なる観点

既存の自動テストがある変更では、ケースを作る前に自動テストを読み、同じ振る舞いを観測している観点を手動ケースから外す。自動テストの証跡は black-box の受け入れを置き換えないので、次の条件を守る。

- 外すのは、自動テストの本文で、同じ入力・条件・期待結果を観測していると確かめた観点だけ。テストの名前や件数だけで外さない。自動テストを読めないとき、根拠を示せないときは外さない。
- 外した観点、根拠（テストのファイルと行、テスト名）、手動に残したものを、出力の冒頭の表に書く。
- 外した観点のリスクは、補正 A にその根拠を書く。根拠のない A を付けない。
- 優先度が P0 の観点の主経路は、自動テストがあっても手動の scripted case を残す。
- 手動には、自動テストが観測していないものを残す。実際の画面や端末での挙動、外部や他システムへ実際に届いた値、目視でしか判定できない結果など。

## Case Quality Bar

A manual scripted case is acceptable only when it has:

- clear preconditions and required data,
- observable steps,
- expected results tied to an oracle,
- traceability to at least one observation and one source or assumption,
- priority derived from a risk item,
- an estimate that includes evidence capture when needed.

If a case is useful but lacks an oracle, convert it to an exploratory charter and label the open question.

ケースの優先度をリスクより上げる・下げるときの決まりは、[risk-and-gate-policy.md](risk-and-gate-policy.md#ケースの優先度と昇格) に従う。

## Missing Information

Classify sufficiency as:

- `ok`: scripted cases and gate can be produced.
- `degraded`: core black-box cases can be produced, but environment/device/network or secondary oracle is incomplete.
- `blocked`: critical rule oracle, permission matrix, state model, or change scope is missing.

Keep `[要確認]` in titles or notes for assumptions that affect coverage, expected results, or gate readiness.

### `[要確認]` の仕分け

`[要確認]` を質問に回す前に、1 件ずつ次の 4 つに分ける。分けた結果と、根拠（出典の場所と引用）を残す。

| 分け方 | 扱い |
|---|---|
| 資料で決まる | 入力の資料に答えがある。期待結果を書き、`[要確認]` を外す |
| 書き方で解ける | 期待結果の書き方を変えれば、決まっていない点に頼らずに判定できる。書き直して `[要確認]` を外す |
| 実装だけが示す | 資料に記載が無く、実装の動きだけが分かる。実装の動きを仮の期待結果にする |
| 質問する | 上の 3 つに当たらない。未決事項の表に載せ、`[要確認]` は残す |

- 実装だけが示すものは、oracle の種類を `derived` とし、根拠に実装の場所を書く。期待結果に「実装どおり・追認待ち」と、追認する人を書く。実装が要件や仕様と食い違うときは、この分け方にせず質問する。
- 資料どうしが食い違うときは、新しいほうの決定を仮の期待結果にしてよい。ただし `[要確認]` は残して質問する。
- 質問は、同じ決定で片付くものを 1 件にまとめる。「A にするか、B にするか」のように選べる形で書き、今わかっていることと、決まらないと止まるケースを添える。
- 追認を待つものは、質問と分けて並べる。
- 追認待ちの期待結果が P0 のケースにあるときは、未解決の critical assumption として扱う。追認が付くまで Go にしない。
- 回答が来たら、期待結果に反映して `[要確認]` を外す。回答の出典（誰が・いつ・どこで）を根拠に残す。

表と質問の下書きの形は [output-templates.md](output-templates.md) を使う。
