# 要件定義の信頼度評価の検収

対象は[spec-07](../specs/spec-07-requirements-confidence.md)。要確認項目数等から要件定義の信頼度を評価する機能を、仕様に記載してから実装した。既存936 testsの未コミット差分を保持している。

実装:

- Markdown／feature_specと任意のphase_contractを評価する`bb-harness evaluate requirements`。
- 要確認タグ・仮定・未決事項・仕様不足・追加findingの件数、重大度、密度、レビュー済み率を決定的に集計する。
- 重大な未解決事項・未レビューに対する点数上限、要件0件の評価不能、同文重複の統合と元位置保持。
- 入力hashとIDの照合、根拠とoracleを持つレビュー、判断と根拠を持つ解決記録。確認事実を雛形で生成しない。
- JSON／Markdown／レビュー雛形の出力、新規出力限定、dry-run、任意閾値による終了コード2。

既存の注文キャンセルfeatureとphase_contractを評価すると、要件6件、要確認2件（critical 1 / high 1）、レビュー済み0件、重み12、基礎点35で**35点 / low / blocked**。結果は[サンプルレポート](../../examples/artifacts/requirements/order.requirements-confidence.md)、[JSON](../../examples/artifacts/requirements/order.requirements_confidence.json)、[未記入雛形](../../examples/artifacts/requirements/order.requirements_review.json)を参照。実際の独立レビューを行ったという記録ではない。

検証:

- 新規65テスト。空入力、未レビュー、重大度の上限、希釈防止、重複、部分レビュー、解決前後、入力版違い、不正参照、Markdown、CLI、goldenを確認した。
- 追加機能とCLI・release bundleの関連回帰107件成功。新しい評価エンジン・CLIの分岐を含むcoverageは98.14%。
- 全体1001件成功（111.40秒）、分岐を含むcoverage 88.18%（閾値85%）。
- Gate専用107件成功、分岐を含むcoverage 91.01%（閾値90%）。
- wheel／sdist smoke成功。インストール先の新しい評価コマンドで、feature＋phaseからレポートを出力した。
- schema例29件、仕様書7件、Skill validator 3種類、ruff、Workflow Cookbook freshness、git diff --checkが成功した。root/package schemaの内容一致、新schemaの構造検証も確認した。

この機能の採点・サンプル実行でLLM／ネットワークを呼び出していない。重み・閾値は初期運用policyであり、正しさの確率やReady／リリースGoを示さない。実案件データでの統計的校正、未記載要件や自然言語の矛盾の網羅的な自動発見は未実施／対象外。前回の実LLM分割生成の完走未達も、この決定的評価機能の検証では解消した扱いにしない。
