# 4.1.0追加改修の検収

対象はPyPI説明リンク、実LLM生成の再評価、PyPI公開後検証CI、要件信頼度の実案件調整準備。
[公開仕様](../release-policy.md)、[生成仕様](../specs/spec-06-bounded-generation-readiness.md)、
[要件評価仕様](../specs/spec-07-requirements-confidence.md)へ先に反映してから実装した。
既存artifact契約、採点policy、Gate条件は維持する。

## 配布と公開後検証

READMEのリポジトリ文書リンクを正本GitHubの絶対URLに変更した。相対Markdownリンクが
残っていないことと、全リンク先のファイルの存在を確認した。

公開workflowへ`verify-publication`を追加した。prepareで確認した2配布物について、
PyPIのメタデータとダウンロードしたバイト列のsize・SHA-256を照合する。新規venvへ
PyPIを明示して導入し、pip reportのhash・取得元・版、CLIのversion/help/要件評価を確認する。
限定retryと失敗記録を備え、このジョブにはOIDCの権限を付けない。

公開済み4.0.1を使った実検証は成功した。公開物を再送せず、新規インストールまで確認した。
[検証記録](evidence/followups-20260911/pypi-4.0.1-verification.json)を保存する。
4.1.0の実公開結果はGitHub Releaseとpublish workflowへ記録する。

## 実LLM生成

Qwen3.6-27B UD-Q4_K_XL、llama.cpp b9733、context 32768、qwen36 profile、thinking無効、
timeout 600秒、run予算150,000。入力は既存order-cancelと
[小規模の合成仕様](../../examples/local-benchmark/minimal-cancel.md)。同じモデルへの呼出を並列化しない。
具体的な修正後に試行し、失敗した試行を削除したり成功率の分母から隠したりしない。

最初の試行は通信障害、サーバーの応答解析時の異常終了、出力打切りで停止した。
単一slotとcontent-only設定に揃え、schemaをモデル可視の本文にも追加した。その後、
状態式の誤り、有限parametersの不足、coverage_inputsの欄名と宣言context、決定表の
action_checksの不足を順に確認した。リスクは観点単位で分割し、入力の記入例をモデルから
計算してプロンプトへ添える。記入例を実ケースへ自動注入せず、生成物の既存検証を維持した。

| 試行 | 結果 | 報告された総tokens | 秒 |
|---|---|---:|---:|
| risk-partitions | 通信中断 | 欠測 | 189.421 |
| single-slot | サーバー異常終了 | 欠測 | 125.603 |
| host-client | 接続拒否 | 欠測 | 2.115 |
| content-parser | 出力打切り | 4,434 | 95.230 |
| explicit-schema | 状態actions不正 | 8,908 | 70.374 |
| state-semantics | 式の構造不正 | 7,530 | 43.165 |
| expr-examples | ケース入力不整合 | 64,270 | 494.560 |
| declared-context | ケース入力不整合 | 82,899 | 598.185 |
| small-batched | 決定表の結果チェック不足 | 35,845 | 183.534 |
| input-examples | 宣言contextとケース不整合 | 31,202 | 191.313 |
| state-scope | 全段生成成功・degraded | 36,056 | 177.786 |

最後のbatched試行は9呼出・修復0回でケース3件とレビューまで完了した。
状態遷移3義務は3件とも設計済みだが、決定表の`minimized_rules`が元rule IDでなくAC IDを
参照したため`blocked_by_missing_information`となった。したがって設計被覆の100%という
一部の数字だけでは合格にせず、`design_status=degraded`、比較への適格性はfalseを保持した。
[全manifestと集計](evidence/followups-20260911/trials.json)、
[最後のartifact一式](evidence/followups-20260911/state-scope/run_manifest.json)、
[実ファイルの再検証](evidence/followups-20260911/state-scope.validation.json)を保存した。

11試行の報告済み消費は**274,428 local tokens**。通信失敗の未報告応答を含まない下限であり、
会話側Codexの消費や外部APIの課金額ではない。各runの予算を増額せず、根拠のない反復は行わない。
fullは76,095 tokens・665.413秒で全段生成したが、設計被覆0%かつ600秒条件超過により不合格。
compactとの比較は実行中で、完了後に失敗も含む比較記録を保存する。

生成結果を仕様と照合したところ、TC-003に仕様未確定のエラー表示の扱いが混ざり、在庫の
観測手段にも追加確認が必要だった。構造評価94点は独立rubric採点ではなく、実務投入の合格点として
扱わない。独立評価者による意味的品質採点と3 fixtures × 3 runsは未実施。

## 実案件調整

実案件データは未提供。評価時snapshotのhash、案件ID、入力hash、同じ観測期間、
不具合件数と手戻り時間を照合する分析補助ツールと[入力手順](../requirements-calibration.md)を追加した。
欠測を0件にせず、調整群で選んだ候補を保留群で確認する。候補の自動適用は行わない。
空の開始例で`insufficient_data`、`candidate=null`、`policy_changed=false`を確認した。
実案件での統計的校正は未実施であり、採点の重みと閾値は変更していない。

## 自動検証

公開後検証25件、実績分析15件、リスク分割・モデル概要と入力記入例を含む回帰を追加した。
Skill validator 3種類、artifact例29件、Workflow Cookbook freshness、ruff、actionlint、
wheel/sdistの隔離インストールsmokeが成功した。
全体**1096件成功**（107.99秒）、分岐を含むcoverage **88.37%**（閾値85%）。
Gate専用107件・91.01%（閾値90%）も成功した。
仕様書8件の検証とgit diff --checkも成功した。HATE/QEGを含むCIの結果は対象commitのrunで確認する。

hash付きartifactを保存する今回の証跡には`.gitattributes`で改行変換の除外を指定し、OS間でバイト列を保持する。
