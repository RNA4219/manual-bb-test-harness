# Spec: 要件定義の信頼度評価

## 概要

要確認項目数・重大度・要件に対する密度・レビュー済み率から、要件定義の信頼度を根拠付きで評価する。既存のReady判定、生成結果の品質採点、リリースGateとは別の評価artifactを追加する。

## 目的

要件の不確実性と、次に確認すべき項目を可視化する。未レビューの仕様や「要確認を見つけていないだけ」の入力を高信頼としない。採点は決定的に行い、LLM・ネットワーク呼出を増やさない。点数は運用上のルール評価であり、正しさの確率ではない。

## 要件

| id | 要件 | 優先度 |
|---|---|---|
| R1 | Markdown仕様書または既存feature_specを読み、任意のphase_contractも同一featureとして評価する | P0 |
| R2 | AC・業務ルールを母集合にし、表記上同じ要件の重複で点数を水増ししない。空・取込用placeholderは母数から除き、0件では点数nullとする | P0 |
| R3 | 明示の要確認タグ、未解決assumption、phaseのopen_questions/spec_gaps、レビューで登録した曖昧さ・矛盾・oracle不足等を集計する | P0 |
| R4 | 件数・重大度別件数・重み・要件数に対する密度・レビュー済み率・点数内訳・上限理由をJSONとMarkdownに出す | P0 |
| R5 | criticalまたはblocks_readyの未解決事項があれば39点以下、highがあれば69点以下、その他の未解決事項または一部未レビューがあれば84点以下、全件未レビューは69点以下とする | P0 |
| R6 | レビューは入力hashとfeature_idで版を照合する。未知・重複ID、参照先不在、根拠のない確認済み／解決済みを拒否する | P0 |
| R7 | レビュー済み要件には評価者・評価日時・実在する引用可能なsource_ref・具体的なoracleが必要。解決には対象issue ID・判断内容・根拠を残す | P0 |
| R8 | 同文の確認項目を統合し、最も高い重大度と全ての出典・ID・要件参照を保持する。異なる文の意味的同一性は推測しない | P1 |
| R9 | 重要な確認事項と未レビュー要件を次のアクションとして示し、レビュー雛形も出力する | P0 |
| R10 | 出力は新規ディレクトリに限定し、入力・既存成果物を上書きしない。dry-runでは書き込まない | P0 |
| R11 | 評価完了は終了コード0、入力不正は1。任意の--fail-underで閾値未達・評価不能を2にできる。GateやReadyの判断権限は変更しない | P0 |
| R12 | schemaのroot/package、CLI、Skill、例、golden、配布smokeを同期し、既存の未コミット差分を保持する | P0 |

## 設計

`requirements_review`はレビュー入力、`requirements_confidence`は評価出力とする。feature_spec/phase_contract自体のschemaは変更しない。Markdownは既存ingestを再利用し、文書中の明示タグを追加収集する。タグは`[要確認]`、`【要確認】`、`TBD`、`TODO`。AC・業務ルール内では`未定`・`未確定`も候補にする。1項目中のタグ反復で件数を増やさない。未検出の曖昧さ・矛盾は意味レビューでfindingsへ登録する。

母数Nは空白・全角互換表記・AC/BRの番号を正規化した一意のAC／業務ルール数。入力hashはfeature・phase・Markdown追加確認項目を含む。要件IDは本文由来の安定IDとし、元配列の位置を残す。重複source IDやissue IDは入力不正として拒否する。

未解決の重みWはcritical=8、high=4、medium=2、low=1の合計。基礎点は`70 × max(0, 1 - W/(4N)) + 30 × (レビュー済み数/N)`で、小数1桁に丸めた後にR5の上限を適用する。85以上=high、60以上=medium、それ未満=low。N=0はscore=null、band=unknown、status=insufficient_data。未解決critical/blocks_readyはstatus=blocked、それ以外の不足はneeds_confirmation、全件レビュー済み・未解決0はreviewed。部分レビューはprovisional=true。

既存assumptionのacceptedは未確認として残す。resolvedにも解決根拠がないため、レビューのresolutionsで根拠を紐付けるまで集計する。phaseのtechnical_risksは実装リスクと要件の不明確さを区別するため採点対象にせず、件数だけ表示する。phase自身のreadinessやconfidenceを採点結果へ流用しない。

レビュー雛形の評価者・日時はnull、全要件はreviewed=false。確認済みや解決済みの事実を生成しない。引用可能な根拠は入力source_refsにあり、excerptまたはurlが非空であることを必要とする。引用先の内容やoracleの意味的正しさを自動保証しない。過去入力のレビューを新しい入力へ無条件に使い回さない。

## インターフェース

```powershell
bb-harness evaluate requirements --input goldens/order-cancel.input.md --output tmp/requirements-first
bb-harness evaluate requirements --input examples/artifacts/order-cancel.feature_spec.json --phase-contract examples/artifacts/order-cancel.phase_contract.json --output tmp/requirements-phase
bb-harness evaluate requirements --input spec.md --review reviewed.json --output tmp/requirements-reviewed --fail-under 85
```

出力は`requirements_confidence.json`、`requirements-confidence.md`、`requirements_review.template.json`。JSON内に入力hash・採点policy版・母集合・確認事項・解決根拠・次アクションを保持する。

## テスト観点

0件、要確認0件だが未レビュー、完全レビュー、重大度の各上限、同文重複、大規模仕様でcriticalを希釈できないこと、部分レビュー、解決前後、accepted/resolved既存assumption、Markdownタグ、版違い、未知ID・重複ID・不正参照、oracle不足、CLI/dry-run/既存出力保護、決定性、schemaと配布環境を確認する。

## 受入基準

- [x] AC-1: 要確認件数・重大度・密度・レビュー率と、再計算できる点数内訳を出せる。
- [x] AC-2: 空入力や未レビュー、大量の軽微要件で高信頼を誤表示しない。
- [x] AC-3: レビュー・解決を入力版と根拠へ結び付け、不正な参照を拒否する。
- [x] AC-4: JSON・Markdown・レビュー雛形・CLI・例・Skill・配布物が同じ契約で動く。
- [x] AC-5: 必要な回帰・coverage・schema・Skill検証が通り、既存の判断権限を維持する。

## 制約

重み・閾値は初期運用policyで、実案件データによる統計的な校正は未実施。仕様の網羅性や意味的正しさを自動保証しない。任意形式のMarkdownの意味解析や自然言語の自動矛盾発見は今回の対象外。対応する見出しと明示タグを使うか、feature_specとレビュー入力へ整理する。
