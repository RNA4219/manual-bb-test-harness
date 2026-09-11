# 技法計画と被覆の検証

型付きモデルを根拠に、必要な入力点・条件・経路を列挙し、ケースの具体的入力から被覆を独立に検証する。出典があることと、その解釈が正しいことは別にレビューする。

## 成果物と手順

`feature_spec → test_model → observation_set → risk_register → technique_plan → manual_case_set → coverage_report → gate_decision`

1. 各モデルに `id / source_refs / coverage_criterion` を与える。関連する `observation_ids / risk_ids` と技法選択の `rationale` を記録する。出典ID・抜粋が入力と一致することを確認する。
2. `technique_plan` のselectionには技法名、標準、学習目標、基準、理由、参照モデルを残す。計算不能は `blocked_by_missing_information` と理由を残す。
3. ケースの `coverage_inputs` に `model_ref` と具体的入力を入れ、`step_refs / expected_result_refs` を1始まりで指定する。対応する手順本文と期待結果にも同じ値・条件を書く。
4. 被覆IDはモデルIDとselectorのハッシュから安定的に作る。自己申告の `coverage_obligation_ids` だけで加算しない。圧縮で義務を失う場合はケースを分けて保持する。
5. `coverage_report` をモデルから再計算する。古いmodel/plan、別feature、架空の被覆ID、存在しない手順番号は検証エラーになる。

`TechniqueRef.key` は共通語彙。旧 `boundary_value / state_transition / decision_table / exploratory` 等は読み込み可能だが、技法ラベルだけでは正式な被覆を証明しない。

## 実装しているモデル

| test_modelのフィールド | 基準と検証 |
|---|---|
| `domain_models` | simplified / reliable Domain。精度・線形border・anchor・制約・他境界による遮蔽 |
| `combination_models` | base_choice / pairwise / n_wise / all。制約付きの有限完全割当からtupleを導出 |
| `state_models` | all_states / valid_transitions / all_transitions / n_switch / round_trip。連続性、guard、action更新を検証 |
| `decision_tables` | feasible_rules。欠落、重複、相反するaction、制約上不可能なルール、最小化前後の対応を検証 |
| `crud_models` | completeness / consistency。操作、未作成状態の読取、作成→更新→各読取経路、作成→削除→読取 |
| `scenario_models` | 基本・代替・例外の宣言済み経路、ループ0/1/2/上限 |
| `checklist_models` | 版付き項目、適用可否と理由。異なる版の実施を同じ被覆に数えない |
| `random_models` | seed、uniform分布、重複方針、sample_budget、oracle。生成したsample_idと実測入力を照合 |
| `metamorphic_relations` | source_data、変換、関係式、trial_budget。元・変換後の実行証跡と関係評価を結合 |

`parameters` に型、値域、単位、精度、stepを置く。数値stepは正、格子の原点は0。日時のカレンダー演算、非線形border、無限値域の探索は未対応。日時は有限の文字列値として組み合わせに利用できる。

式は `{ "var": "amount" }`、`{ "const": 1000 }`、`{ "op": "gte", "args": [...] }` という制限ASTを使う。and/or/not、比較、四則演算のみ。任意のPython式や関数呼出しは評価しない。

### Domainの入力点

- `< / <= / > / >=` はONとOFFを各1点。`=` はONと両側OFF、`!=` はOFFと両側ON。
- reliableは不等号4種にINとOUTを追加する。今回の決定的な実装はON/OFFから内外へ2step離れた候補を使う。`= / !=` はsimplifiedと同じ3点。
- 金額が `P-D >= 10000` なら、Dをanchorで固定しPを動かして境界を求める。小数はDecimalで扱い、整数専用の±1に固定しない。
- 他のborderが同時に不成立になる、境界が交差する、入力可能な範囲を外れる場合は `unknown` とする。そのanchorで選べないことを、すべての入力で不可能と断定しない。
- 被覆は生成した具体的witnessとの一致で計数する。別anchorも設計対象なら別モデルとして明示する。

### 状態・決定表

- n-switchはn+1本の連続遷移。各遷移を別々のケースで実施しても連続経路の被覆にはならない。
- round_tripは始点と終点が一致し、それ以外の状態が重複しない経路。宣言した状態を初期状態として準備できる前提で評価する。
- contextsはguard評価の有限な入力集合。actionの値更新を次のguardへ伝搬する。invalid遷移は試行経路の末尾に置く。
- 決定表は全実行可能割当が元ルールにちょうど1つ対応することを要求する。minimized_rulesは `represented_rule_ids`、条件集合、actionsが元ルールと一致して初めて有効になる。

## 設計・実施・合格を混ぜない

`design.rate = 設計済みrequired義務 / feasibleなrequired義務`。
`execution.rate = 実施済みrequired義務 / 同じ分母`。failも実施済み、skip/blockedは未実施。同一ケースの最新結果を採用し、重複run IDや同時刻の曖昧な結果は拒否する。合格数は `execution.passed` で別に示す。

分母0はnull。unknown、infeasible、blocked、未設計・未実施IDを別に出す。「有限モデルの範囲で100%」を仕様全体の100%と書かない。入力モデルの妥当性、sourceの解釈、coverage_inputsと自然言語手順の意味的一致は人のレビューが必要。

randomは試行予算、metamorphicはjoint_trialsを `exit_criteria` で評価し、架空の網羅率を作らない。randomの `time_budget_seconds` は計画情報であり、現在の判定はsample_budgetのみ。metamorphicはsource/follow-upの個別passだけでは完了せず、観測出力から関係式を評価した証跡が必要。試行間で同じrunを再利用しない。

Gateには設計率、実施率、未解決数、終了条件、report IDをshadowとして添える。新指標の閾値は導入せず、既存のP0/P1・defect・自動証跡・waiver判断を維持する。Gateはfeature/build/case hashを照合するが、渡されたreport単独でモデルや実行ログの真正性を証明できない。モデルや証跡を変更したらcoverageコマンドから再生成する。

## CLI

repoの `examples/artifacts/techniques/discount-domain/` に、1円刻みの割引境界、4つのケース、実行例、計画・被覆レポートがある。実行例は説明用の合成証跡。

```powershell
$example = 'examples/artifacts/techniques/discount-domain'
uv run bb-harness coverage `
  --feature "$example/discount.feature_spec.json" `
  --test-model "$example/discount.test_model.json" `
  --observations "$example/discount.observation_set.json" `
  --risk "$example/discount.risk_register.json" `
  --cases "$example/discount.manual_case_set.json" `
  --evidence examples/coverage-evidence/discount-domain --build-id demo-1 `
  --output tmp/discount-coverage
```

outputは未存在のディレクトリを指定する。不足があってもレポート生成自体は終了コード0になるので、利用側はerrors、blocked_selections、unknown_ids、uncovered_ids、exit_criteriaを確認する。

Local Modeの `run local-design` は同じ計算を自動で行い、technique_plan.json、coverage_report.json、Markdownの入力対応を保存する。run_manifestのgenerationにモデル、prompt版、入力hash、temperature、時刻、review_status=pendingを記録する。モデル固有の版とseedが取得できないときはnullで残す。

## 非破壊移行

```powershell
uv run bb-harness migrate --input old.manual_case_set.json `
  --output enhanced.manual_case_set.json --type manual_case_set
uv run bb-harness migrate --input enhanced.manual_case_set.json `
  --output legacy.manual_case_set.json --type manual_case_set --artifact-version legacy
```

追加契約のschema_versionは1.1.0で、packageの3.0.0とは別。既存artifactにversionは必須化しない。移行はID・本文を保持し、旧casesはunmapped、文字列test_modelはneeds_reviewとする。精度、条件式、正式被覆を推測で補完しない。

legacy出力は追加metadata・型付きモデル・被覆対応を除去する明示的な互換用export。被覆情報は失われるので原本を保管する。新しい被覆artifactや旧enumで表せない観点技法の変換は拒否する。出力済みファイルと入力ファイルを上書きしない。

## 上限と追加実装が必要な範囲

有限完全割当・状態探索・1モデルの義務数は10,000件まで、状態経路長は6まで。上限超過や未対応はblockedと理由を記録し、部分列挙を100%としない。SAT/SMT、汎用covering-array最適化は未導入。

探索charterのmission/resources/entry・exit/environment/limitations/history_refsと、execution_evidenceのsession_logを保存できる。セッション内容の意味的採点や自動終了判断は未実装。
integration_pathsは将来連携用の契約のみ。service間経路の自動被覆、Crowd vendor接続、Agile Example Mapping、toursの自動展開は未実装。

技法定義の参照: [ISTQB CTAL-TA v4.0公式シラバス](https://istqb.org/wp-content/uploads/sdm-uploads/ISTQB-CTAL-TA-Syllabus-v4.0-EN-4.pdf)。採用判断と調査原本はrepoの `docs/research/`、検証記録は `docs/acceptance/AC-20260910-istqb.md` に保存する。
