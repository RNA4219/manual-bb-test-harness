# 要件定義の信頼度

要確認件数、重大度、要件数に対する密度、レビュー済み率から、要件定義の信頼度と次の確認事項を出す。正本仕様は[spec-07](../../../docs/specs/spec-07-requirements-confidence.md)。評価はホスト側の計算だけで行い、LLMもネットワークも呼ばない。

## 評価する

```powershell
bb-harness evaluate requirements --input spec.md --output tmp/requirements-first
bb-harness evaluate requirements --input examples/artifacts/order-cancel.feature_spec.json --phase-contract examples/artifacts/order-cancel.phase_contract.json --output tmp/requirements-phase
```

Markdownは`## Acceptance Criteria`／`## 受入条件`／`## 要件`と、`## Business Rules`／`## 業務ルール`の箇条書きを使う。文書中の`[要確認]`、`【要確認】`、英語の未決・作業待ちマーカーを収集する（対応語はspec-07参照）。AC・業務ルールでは「未定」「未確定」も候補にする。タグの反復や同文の要件・確認事項は統合し、元の位置を残す。見出しやコード例中のタグも候補になるため、評価対象本文を入力する。

要件はAC・業務ルールの一意な本文を母集合にする。scopeやtechnical_risksを要件数として加算しない。phase_contractのopen_questions/spec_gaps、既存assumptionsも要確認へ加える。assumptionのaccepted/resolvedだけでは解決根拠が分からないため、以下のresolutionsで根拠を残すまで要確認に含める。

出力:

- `requirements-confidence.md`: 点数、要確認件数、重大度、レビュー率、上限理由、次アクション。
- `requirements_confidence.json`: 上記の内訳、入力hash、要件ID・元位置、確認事項・統合ID・出典・解決根拠、レビュー記録。
- `requirements_review.template.json`: 評価者・日時null、全要件reviewed=falseの記入用雛形。

## レビューして再評価する

雛形を別名で保存し、実際のレビュー結果を記入する。初回評価には--reviewは不要。既存のレビューを更新する場合は、そのレビュー原本を使い、毎回出る未記入雛形で過去の結果を置き換えない。

1. `reviewer`とタイムゾーン付き`reviewed_at`を記録する。
2. 各要件の根拠・期待結果・曖昧さ・矛盾を確認する。確認した要件だけ`reviewed=true`とし、具体的な`oracle`と`source_refs`を記入する。
3. 新しく見つかった不足は`findings`に記録する。`kind`はquestion / ambiguity / contradiction / missing_oracle / missing_source、`severity`はcritical / high / medium / low。影響する`requirement_ids`、本文、根拠、任意のowner/dueを付ける。
4. 解決した確認事項は`resolutions`に対象`issue_id`、決定内容`decision`、根拠`source_refs`を記入する。自動検出の確認事項も、出力にあるIDで参照できる。

根拠IDは入力feature/phaseのsource_refsにあり、excerptまたはurlを持つものを使う。根拠が不足する場合は元の入力を更新して再評価する。異なる入力版のレビューは拒否するため、入力変更後は新しい雛形と原本を比較して再確認する。確認した事実や解決根拠を推測で埋めない。

```powershell
bb-harness evaluate requirements --input spec.md --review reviewed.json --output tmp/requirements-reviewed --fail-under 85
```

--outputは未存在のディレクトリを指定する。--dry-runは評価だけ行い、書き込まない。通常は評価を完了すれば終了コード0、入力不正は1。--fail-under指定時は閾値未達・評価不能で2にできる。点数にかかわらずReady・既存Gateは別途評価する。

## 点数を読む

N=重複除外した要件数、W=未解決の重み合計（critical 8 / high 4 / medium 2 / low 1）。

`基礎点 = 70 × max(0, 1 - W/(4N)) + 30 × レビュー済み率`

レビュー済み率は式の中では0〜1を使う。基礎点を小数1桁に丸め、次のうち最も低い上限を適用する。

| 条件 | 上限 |
|---|---:|
| criticalまたはblocks_readyが未解決 | 39 |
| highが未解決 | 69 |
| 他の要確認または一部未レビュー | 84 |
| 全件未レビュー | 69 |

85以上high、60以上medium、それ未満low。要件0件はscore=null、unknown、insufficient_data。全件レビュー済みでも未解決事項があればneeds_confirmationまたはblocked。未レビュー要件が残ればprovisional=true。

「要確認0件、未レビュー」は69点。「全件根拠付きレビュー済み、記録上の未解決0件」は100点になる。100点は記録の充足を示し、仕様の正しさを100%保証する意味ではない。未記載要件・自然言語の矛盾を自動で網羅的に発見する機能は含まない。重みと閾値の実案件データによる校正は今後の評価対象。
