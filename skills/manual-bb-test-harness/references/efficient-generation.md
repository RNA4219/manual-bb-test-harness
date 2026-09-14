# 生成効率・予算・実行証跡の版

Local Modeの契約は[spec-05](../../../docs/specs/spec-05-efficient-generation-evidence-revisions.md)を参照する。

`compact`を既定とし、補完には未被覆義務と関連モデル・risk・観点を送る。条件式が間接参照するparameterと元仕様は保持する。同じ義務を別のJSON項目に再掲しない。義務・risk・mandatory観点に不足がなければ補完を省略できる。`full`は比較用に従来の全件補完・全件レビューを保持する。

レビューは`case_review_patch`で対象IDと変更項目だけを返す。修正なしなら両配列を空にする。入力・手順・経路・被覆・ID・削除の変更は禁止。oracle/source/expectedの修正後も全体のschema、根拠、traceと被覆を確認する。失われた義務を成功扱いしない。

`--estimate-only`はHTTP通信せず、初段の入力推定と各段の出力上限を表示する。後段の入力と修復分は生成結果が必要なため未確定。`--token-budget`は1 runで共有し、呼出前に「入力推定＋出力上限」を予約できなければ停止する。実測usageがあれば予約額を実測値で精算し、未報告なら推定予約分を計上する。

manifestの`usage_summary`と`call_records`で成功・修復・失敗・予算停止を確認する。入力推定はUTF-8 byte数＋256であり、実測tokensと混同しない。`max_tokens`は出力上限であり使用予定量ではない。未報告・不正なusageが1回でもあれば実測総量はnullとなる。生成停止時も部分成果物とfailed manifestを残す。厳密な課金上限の保証ではない。

新しく生成したケースには`evidence_binding.model_hash`と各case/charterの`case_revision`が付く。実行前に、この2値を実行記録へ控える。実行後に別版からhashを補わない。入力・手順・期待値・oracle・source等を変更したら再bindして再実行する。タイトル・priority・工数・traceだけの変更ではケース版を変えない。

```powershell
bb-harness bind-cases --input cases.json --test-model model.json --output bound-cases.json
```

既存ファイルへの上書きは拒否する。旧ケースは`legacy_unverified`として読み取れるが、版を確認済みとは扱わない。coverageは指定buildの全入力証跡を照合するため、古い版の履歴は別入力へ分離する。Gateは最新選択後の証跡を照合する。report添付時はcase hashとmodel hashの両方も確認する。

比較は`tools/benchmark_local_efficiency.py`でfull→compactを順次実行する。両方が生成・schema・構造・有限の必須被覆100%を満たし、実測tokensも取得できた場合だけ削減率を出す。独立した意味的品質採点は別に必要。最初の比較が不成立なら9-runへ進めない。

## 分割生成と設計状態

出力上限が問題になる場合は`--generation-mode batched`を明示する。既定のcompactは維持する。概要・共有parameterを生成した後、選択した技法だけを個別に生成する。ケースは1回につき最大2件、最大24回。未被覆義務・risk・mandatory観点に進展がなければ補完を止める。レビューも最大2件ずつに分け、対象外IDの更新を拒否する。

各応答を完全JSONとして検証し、`checkpoints/`に分割結果を保存する。分割・修復にも同じrun予算と段階別profileを適用し、出力上限を自動で増やさない。checkpointからの自動resumeは未実装。続ける場合も新規出力先を使用する。

リスク生成は観点を最大4件ずつ、最大8分割で処理する。各分割の必須観点漏れと対象外の参照を拒否し、統合後も全体を検証する。低リスクの観点を分割ごとにP1へ引き上げることはしない。32観点を超えた場合はリスク生成の呼出前に停止する。

finish_reasonがlengthならoutput_truncated、stop以外の明示終了ならincomplete_response。JSONが読めても成功にはしない。未報告のfinish_reasonはnullで残す。既存の出力ディレクトリは上書きしない。

manifestのstatusは生成処理の成否、design_statusは設計の状態を示す。lintエラーはblocked、必須被覆の不足や計算不能はdegraded、構造と必須設計被覆が成立したらready。CLI終了コードは生成失敗1、degraded/blockedは2、readyは0。readyでも実行証跡なしのGateはno_goであり、独立した意味的品質採点は別に必要。

比較は`--modes compact batched`等で指定できる。実ファイルのschema/hash、risk/工数算術、lint、設計被覆の再計算、入力・設定・応答モデルの同一性を確認し、欠損や不一致があれば不成立とする。[spec-06](../../../docs/specs/spec-06-bounded-generation-readiness.md)が追加契約の正本。
