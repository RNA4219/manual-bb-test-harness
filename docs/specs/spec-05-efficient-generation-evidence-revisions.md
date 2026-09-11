# Spec: 生成コスト管理と実行証跡の版照合

## 概要

2026-09-10の追加依頼に基づく。仕様を先に確定し、重複送信の削減、予算・消費量の可視化、実行証跡の版照合、実LLM比較を実装する。前段のISTQB拡張（835 tests）の未コミット差分を保持して追加する。

## 目的

品質に必要な根拠を保持し、送信・再生成の重複を減らす。実行結果を設計した版と結び付け、消費量と未検証状態を利用者が判断できるようにする。

## 要件一覧

| id | 要件 | 優先度 |
|---|---|---|
| R1.1 | compactモードを既定にし、fullモードを比較用に保持する | P0 |
| R1.2 | 補完には未被覆義務と関係するモデル・観点・risk・sourceを送る。同じ義務を二重に送らない | P0 |
| R1.3 | 補完後の件数下限を固定しない。必要な義務・risk・mandatory観点を満たす場合は補完を省略できる | P0 |
| R1.4 | レビューは変更するケース・charterだけ返す。IDを指定し、削除・入力・経路の変更は禁止、oracle・expected・source・priority・工数だけ修正できる | P0 |
| R1.5 | 差分適用後に全体のschema、trace、被覆を再検証し、未変更のケースと義務を保持する | P0 |
| R2.1 | 各呼び出しの入力・出力・総tokens、修復分、失敗分、全体集計をmanifestへ記録する | P0 |
| R2.2 | usage未報告・不正値を0と見なさずunknownとして表示する | P0 |
| R2.3 | 入力とschemaのUTF-8 byte数＋固定余白による推定と、providerの実測usageを区別する | P0 |
| R2.4 | token-budget指定時は、呼出前に入力推定＋出力上限を残予算と照合し、不足ならモデルを呼ばず停止する。修復も同じ予算を使う | P0 |
| R2.5 | 予算停止・通信失敗・JSON解析失敗でも途中成果物とmanifestを保存し、CLIは非ゼロ終了する | P0 |
| R2.6 | estimate-onlyはLLMを呼ばず、初段の入力推定、各段の出力上限、後段の入力は未確定であることを表示する | P1 |
| R3.1 | ケース本文・入力・期待値・oracle・sourceとモデルのhashを実行証跡へ結び付ける | P0 |
| R3.2 | 同じIDでも内容・モデルが違う証跡、版情報のない証跡を新形式のGateとcoverageで拒否する | P0 |
| R3.3 | タイトル、priority、工数、traceなど実行内容を変えないmetadata変更はケース版を変えない | P1 |
| R3.4 | 新しいLocal Mode出力は版照合を有効化する。旧ケースは読み取り互換を維持しlegacy_unverifiedを明示する | P0 |
| R3.5 | bind-casesはモデルからケース版を付けて別ファイルへ出力する。既存の実行証跡へ現在の版を遡及付与しない | P0 |
| R4.1 | 同じfixture・モデル・設定でfullとcompactを順次実行し、成功率、schema、実行時間、usage、修復、被覆を比較する | P0 |
| R4.2 | 実測値が揃わない比較は削減率をnullにし、失敗・unknownを成功や0消費としない | P0 |
| R4.3 | まず小さな仕様1件で比較し、schema/構造/被覆が成立した場合に3 fixtures × 3 runsへ進める | P1 |

## インターフェース

```powershell
bb-harness run local-design --input goldens/order-cancel.input.md --output tmp/compact --profile qwen36 --generation-mode compact --token-budget 150000
bb-harness run local-design --input goldens/order-cancel.input.md --output tmp/estimate --profile qwen36 --estimate-only
bb-harness bind-cases --input cases.json --test-model model.json --output bound-cases.json
python tools/benchmark_local_efficiency.py --input goldens/order-cancel.input.md --output tmp/efficiency --profile qwen36
```

`generation-mode=compact|full`、`token-budget`は正の整数、未指定時は上限なし。予算は1回のlocal-design実行内で共有し、比較の各runにも同じ値を適用する。max_tokensは出力上限であり使用予定量ではない。

input推定はtokenizerの実測ではなく、サーバーのchat templateやschema変換によって誤差がある。予算は呼出を許可するための保守的な推定管理であり、サーバー側の厳密な課金上限を保証しない。usageが取得できなければ予約した推定額を予算消費として扱い、実測合計はnullにする。

`run_manifest`に `generation_mode / usage_summary / call_records / stop_reason` を追加する。call_recordsはstage、repair、結果、時間、実測usage、推定入力、出力上限、予算への計上値だけを保存する。raw prompt、モデル本文、API keyは保存しない。

レビュー差分の契約は `case_review_patch.schema.json`。`case_updates[{tc_id, changes}] / charter_updates[{id, changes}]` を要求し、空配列を許す。同じIDの重複、未知ID、入力・経路・削除を含むpatchは拒否する。

## 設計: 証跡の版契約

- manual_case_setに `evidence_binding={mode: case_revision, model_hash: SHA256}` を追加し、各case/charterに `case_revision` を保存する。
- case_revisionはcanonical JSONから生成し、ID、title、priority、estimate_minutes、trace_to、techniques、technique_refs、case_revisionは除外する。steps、preconditions、expected_results、oracle、source_ref、test_data、coverage_inputs、coverage_obligation_ids、charterのscope/questions等は含める。
- execution_evidenceには `case_revision / model_hash` を実行時の定義から保存する。参照先case/charter、feature、build、モデルhash、ケースhashを照合する。
- boundケース自体を変更したら再bindする。Gate/coverageは宣言したcase_revisionと本文の再計算値の不一致も拒否する。
- coverageは指定build内の全証跡を照合し、旧版の履歴は別入力へ分離する。Gateは既存の最新選択後の証跡を照合する。
- coverageはbindingのmodel_hashと実モデルを照合する。Gateはbindingを期待値に使い、report添付時はそのmodel_hashも照合する。
- bindingなしはlegacy_unverified。古い証跡を新形式へ自動的に「検証済み」と移行しない。legacy exportでは追加情報の除去を明示する。

## テスト観点

予算の直前・一致・超過、usage欠落と不正値、解析失敗、修復予算、未知・重複patch ID、証跡の同ID別本文、モデル差、旧形式を組み合わせて確認する。

## 受入基準

- [x] AC-1: 同じ被覆義務を二重送信せず、補完の入力projectionが必要な制約・根拠を保持する。
- [x] AC-2: 修正なしのレビューは空patchで完了し、既存ケースの削除・ID変更・未知ID更新を拒否する。
- [x] AC-3: 予算不足なら呼出回数0。修復が予算を超えると追加呼出せず途中成果物とfailed manifestを残す。
- [x] AC-4: 成功・JSON不正・通信失敗・usage欠落を区別して集計し、estimate-onlyはネットワークアクセスしない。
- [x] AC-5: 同IDの入力・期待値変更やモデル変更を古い証跡で合格にできない。タイトル・工数変更は版を変えない。
- [x] AC-6: 旧artifactのschema・Gate互換を維持し、legacy_unverifiedを表示する。
- [x] AC-7: schema/example/Skill/CLI/packageを同期し、回帰・カバレッジ・構造検証が通る。
- [x] AC-8: 実LLMの小規模比較を実施し、成功・失敗と観測値を記録する。比較不成立なら9-runへ進めず原因を残す。

## 制約と判定の境界

費用削減率に事前の合格数値を置かない。実測と品質の両方が成立した場合だけ効果を述べる。既存の独立採点70点基準やGateの閾値は変えない。決定的な構造検証を自然言語の意味的品質評価と同一視しない。

検収記録: `docs/acceptance/AC-20260910-efficiency.md`。外部サービスへの投稿・commit・pushは今回の実装に含めない。
