# 分割生成・完了判定の検収

対象は[spec-06](../specs/spec-06-bounded-generation-readiness.md)。仕様を先に記載してから実装した。前回の未コミット差分と、作業開始時から存在した`verify_local_benchmark.py`の変更を保持している。

追加調査で確認した問題と対応:

- 大きなモデルとケース集合が出力上限に達するため、モデルを概要と技法単位、ケースとレビューを各配列最大2件に分割する`batched`を追加した。最大24ケース生成回、無進展停止、run共通予算、検証済みcheckpointを設けた。
- JSONが構文上正しくても、`finish_reason=length`などの未完了応答は拒否する。失敗のusage・応答モデル名・終了理由も記録する。
- 既存出力の上書きを防ぎ、入力読取り後に新規ディレクトリを排他的に作る。
- 生成完了と設計の不足を区別し、`design_status`とCLI終了コードで`ready / degraded / blocked`を明示する。実行証跡がない場合のGateはno_goを維持する。
- モード比較は実artifactのschema・hash・算術・lint・設計被覆を再検証し、入力・profile・モデル・共通設定も照合する。壊れたデータを成功や0消費にしない。
- 修復プロンプトへ元の分割依頼を含め、生成schemaの件数下限を後段の必須検証に合わせた。
- 生成manifestの`run_id`が手動実行証跡と誤認される不具合を修正した。ディレクトリ収集ではschemaが正しい生成ログだけ除外し、壊れたログや実行証跡は拒否する。

## 実モデル試行

入力は`goldens/order-cancel.input.md`。Qwen3.6-27B UD-Q4_K_XL、llama.cpp、context 32768、qwen36 profile、thinking無効、timeout 600秒、各runのtoken予算150,000で順次実行した。各試行は具体的な修正の後に行った。今回起動したサーバーは検証後に停止した。

| 試行 | 修正段階 | 結果 | 総tokens | 呼出／修復 | 秒 |
|---|---|---|---:|---:|---:|
| initial | 分割生成導入 | 境界の具体値が不足して停止 | 2,804 | 2／1 | 115.426 |
| repair-context | 修復へ元の根拠を追加 | 境界の具体値が不足して停止 | 3,150 | 2／1 | 27.673 |
| schema-minima | 件数下限・状態境界の指示を整合 | 必須観点2件のリスク分析漏れで停止 | 33,459 | 8／2 | 349.540 |

3試行は全て`failed / blocked`。最後の試行ではモデル概要・組合せ・決定表・状態モデルの4checkpoint、完成したtest_modelとobservation_setまで保存した。全応答のfinish_reasonはstopで、出力打切りは発生しなかった。リスク分析に`OBS-STATE-01`と`OBS-STATE-10`が含まれず、検証で拒否された。**実モデルでのケース・レビュー段階の完走は未検証**。

合計は**39,413 local tokens**。会話側Codexの使用量とは別であり、外部APIの課金額を示す値ではない。[集計](evidence/batched-20260910/trials.json)、[初回manifest](evidence/batched-20260910/initial.local_run_manifest.json)、[修復根拠追加後](evidence/batched-20260910/repair-context.local_run_manifest.json)、[schema整合後](evidence/batched-20260910/schema-minima.local_run_manifest.json)に失敗を含む生記録を保存した。

生成完了が成立していないため、削減率・独立した意味的品質採点・9-runは未判定／未実施。合成応答によるテストの完走を実モデルの合格に置き換えない。予算上限や出力上限の自動引上げも行っていない。

## 検証

- 追加38件で分割完走・最大回数・無進展・修復・共通予算・ID衝突・レビュー対象外ID・出力保護・未完了応答・設計状態・比較の実ファイル検証・Gateのログ分類を確認した。
- Gate専用107件成功、分岐を含むcoverage 91.01%（閾値90%）。
- 全体936件成功（96.57秒）、分岐を含むcoverage 87.53%（閾値85%）。最終実行前に、仕様書の必須見出しの不足を修正した。
- wheel／sdist smoke成功。インストール先のCLIでbatchedのestimate-onlyも確認した。
- schema例27件が全て妥当。root／package schemaは一致し、実測manifest3件もschema検証に成功した。
- ruff、仕様書6件、Skill validator 3種類、Workflow Cookbook freshness、git diff --checkが成功した。

## 残る改修・評価候補

必須観点とリスクの対応漏れを減らすため、リスク生成も観点単位で分割する設計が次の候補。現在のbatched対象はモデル・ケース・レビューであり、観点生成とリスク生成は全件方式を維持している。仕様化・実装後に小規模実モデル試行を行い、完走してからモード比較を拡大する。

checkpointは調査用に保存するが、自動resumeは今回の対象外。復帰を追加する場合は入力・設定・schema・既存成果物の整合確認を別途仕様化する。これらの未実装機能や実モデルの完走を、本改修の回帰検証成功と混同しない。
