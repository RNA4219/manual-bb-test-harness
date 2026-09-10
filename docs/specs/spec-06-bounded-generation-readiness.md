# Spec: 分割生成と完了判定の厳密化

## 概要

前回の実LLM評価は、test_modelとmanual_case_setの出力上限で失敗した。追加調査でfinish_reason未確認、既存出力への上書き、生成完了と設計妥当性の混同、比較サマリの自己申告への依存も確認した。これらを仕様に反映してから実装する。

## 目的

出力上限内の完全JSON単位で生成を進め、予算・進展・設計被覆に基づく停止と完了を区別する。生成記録と実artifactを照合できるようにし、未達を成功やトークン削減に読み替えない。

## 要件

| id | 要件 | 優先度 |
|---|---|---|
| R1 | batchedモードを追加し、モデルを概要・共有parameterと選択した技法単位に分け、ケースは未被覆義務／risk／mandatory観点を小さな単位で生成する | P0 |
| R2 | 各応答を独立した完全JSONとして検証する。途中JSONの連結・切捨てで成功扱いしない | P0 |
| R3 | 分割結果を保存し、全体を再検証してから次段へ進む。分割数は有限、進展のないケース補完は停止する | P0 |
| R4 | reviewもケース・charterの小分けで行い、対象外ID更新・削除・入力変更を拒否する | P0 |
| R5 | 分割と修復は同じrun予算を共有し、段階別profileの出力上限を継承する。自動で上限を増やさない | P0 |
| R6 | finish_reasonがlengthならoutput_truncated、stop以外の明示終了ならincomplete_responseとして拒否する。JSONが読めても未完了応答は拒否しusageを残す | P0 |
| R7 | 既存出力ディレクトリ・入力を上書きしない。実行開始前に入力を読み、新規出力を排他的に作る | P0 |
| R8 | generationのstatusとdesign_statusを区別し、設計にlintエラーならblocked、必須被覆不足／計算不能ならdegraded、構造と必須設計被覆が成立したらreadyとする | P0 |
| R9 | CLIはdegraded/blockedで終了コード2、生成停止で1、readyで0とする。実行証跡なしのGateはno_goを維持する | P0 |
| R10 | 比較はmanifestだけを信じず、実artifactのschema・hash・決定的算術・lint・再計算した設計被覆を検証する。不足ファイルや不正JSONは比較不成立として記録する | P0 |
| R11 | 比較対象モードを選べるようにし、入力hash・profile・実モデル名が一致した場合だけ比較を成立させる | P1 |
| R12 | batchedの修復には元の分割依頼と根拠も渡す。エラーと不正値だけで不足内容を推測させない | P0 |
| R13 | 生成用schemaの件数下限を後段の必須検証と揃える。境界には仕様に実在する状態境界も含め、空配列を許してから拒否する不一致を除く | P0 |
| R14 | 証跡ディレクトリの正しいlocal_run_manifestを実行証跡から区別する。壊れた生成ログや実行証跡を黙って除外しない | P0 |

## 設計

新モードは`batched`。既定compactと比較用fullを維持する。batchedのモデル概要応答では、従来の表面分解・共有parameter・対象技法を返す。技法は有限の既知enumから選び、選択された技法だけ個別に生成する。各技法は根拠と共有parameterを保持する。技法間でIDが衝突した場合は全体検証で拒否する。

ケースは1回につき最大2件、チャーターも最大2件、review対象は各配列の最大2件。義務／risk／mandatory観点から未完了の先頭項目を優先する。モデル側のunknownやblockedをケース追加で解決したふりをしない。ケース補完は最大24回、前後で対象義務・risk・観点が一つも減らなければ停止しdegradedを残す。分割ごとの出力は`checkpoints/`へ保存する。自動resumeは今回の対象外。

分割段階名は`test_model__core`、`test_model__<technique>`、`manual_case_set__N`、`manual_case_review__N`。profileと出力上限は`__`前の段階名を使う。修復は各分割につき最大1回、打ち切られた応答は同じサイズで自動再試行しない。

`run_manifest.design_status`は`ready / degraded / blocked`。生成失敗時はblocked。readyも独立した意味的品質採点やリリースGoを保証しない。旧manifestのdesign_status未記録は互換読取りを許し、検証時に実artifactから確認する。

finish_reason未報告は互換APIのためJSON検証を続けるが、値をnullで記録する。明示のlengthやcontent_filter等は失敗。通信・JSON解析・正規化・schema失敗の記録を区別する。

## インターフェース

```powershell
bb-harness run local-design --input goldens/order-cancel.input.md --output tmp/batched --profile qwen36 --generation-mode batched --token-budget 150000
python tools/benchmark_local_efficiency.py --input goldens/order-cancel.input.md --output tmp/compare-batched --modes compact batched
```

## テスト観点

length付きで構文上正常なJSON、フィルタ終了、finish_reason欠落、既存ディレクトリ保護、正規化例外、分割profile・予算継承、ID衝突、進展なし、分割途中失敗とcheckpoint、review対象外ID、ready/degraded/blocked、比較のファイル欠落・hash不一致・被覆再計算を確認する。

## 受入基準

- [x] AC-1: モデル・ケース・レビューの分割が完全JSON単位で動き、上限・無進展・予算で有限に停止する。
- [x] AC-2: 打切りや未完了の応答を正常JSONでも拒否し、消費量と終了理由を残す。
- [x] AC-3: 既存ファイルは変化せず、設計の不足をCLIとmanifestで明示する。
- [x] AC-4: 実ファイルを再検証し、壊れた／欠落した比較データを成功・0消費にしない。
- [x] AC-5: schema・例・CLI・Skill・配布パッケージを同期し、回帰・カバレッジ検証が通る。
- [x] AC-6: 実モデルの小規模batched実行を行い、成功・不足・停止と消費量を記録する。意味的品質や未実施の9-runを合格としない。

## 制約

未コミットの前回改修と他の既存変更を保持する。実LLMの完走を事前保証せず、未完了の場合は原因を記録する。検収は`docs/acceptance/AC-20260910-batched.md`に残す。
