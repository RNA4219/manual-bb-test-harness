# Local Mode guide

## 目的

Local Modeはprovider障害時の継続運用を主目的とする。`run local-design` で利用者が明示的に選択する実行モードであり、cloudからの自動failoverではない。LLM単体の自由生成品質をrelease権限として扱わず、通常経路と同じartifact schemaとGate engineを維持する。

## 対応API

- OpenAI互換 `GET /v1/models`
- OpenAI互換 `POST /v1/chat/completions`
- JSON Schema `response_format`
- llama.cpp / LM Studio

Ollama native APIは初期scope外。Ollamaを使う場合はOpenAI互換endpointを経由する。

## 実行

Qwen3.6 27B preset:

```powershell
uv run bb-harness run local-design `
  --input goldens/order-cancel.input.md `
  --output tmp/local-order-cancel `
  --profile qwen36
```

任意のOpenAI互換server:

```powershell
uv run bb-harness run local-design `
  --input spec.md `
  --output tmp/local-design `
  --profile generic `
  --base-url http://127.0.0.1:1234/v1 `
  --model local-model-id
```

モデルを省略した場合、`/models` がちょうど1件のときだけ自動選択する。0件または複数件ならfail closedする。

## 設定優先順位

1. CLI: `--base-url`, `--model`, `--timeout`
2. 環境変数: `BB_HARNESS_LOCAL_BASE_URL`, `BB_HARNESS_LOCAL_MODEL`, `BB_HARNESS_LOCAL_TIMEOUT`
3. `src/bb_harness/local_profiles.yaml`

API keyが必要な互換serverでは `BB_HARNESS_LOCAL_API_KEY` を使う。keyはmanifestへ保存しない。

既定ではlocalhost / loopback以外への接続を拒否する。信頼済みLAN serverへ接続するときだけ `--allow-non-loopback` を明示する。

## パイプライン

出力が長くなる場合は`--generation-mode batched`でモデル・ケース・レビューを分割する。完全JSON単位で検証し、途中成果物はcheckpointsへ保存する。実行先は未存在のディレクトリを指定する。

既定は`--generation-mode compact`。補完は未被覆項目に絞り、レビューは変更箇所だけを返す。従来の全件生成との比較には`--generation-mode full`を指定する。

1. Markdownを根拠ID付き `feature_spec` へ決定的に正規化する。
2. LLMが `test_model` を作る。
3. LLMが `observation_set` を作る。
4. LLMがrisk因子候補を作り、hostがscore / priorityを計算する。
5. LLMが `manual_case_set` を作り、同じmodelがoracle・priority・traceをセルフレビューする。
6. hostがrisk-case trace、priority、工数を正規化し、lintする。
7. 実行証跡があれば既存Gate engineを使う。なければ必ず `no_go` にする。
8. hostがrelease briefとMarkdownを生成する。

artifactごとにschema不正または重要な構造不足があればrepairを1回だけ行う。再度失敗した場合は処理を停止し、部分成果物とfailed manifestを残す。

`qwen36` profileは全stageでthinkingを無効にする。Qwen3.6 27B + llama.cppのJSON Schema出力では、thinking有効時にreasoningだけでtoken上限へ達してcontentが空になることを実測したためである。planning品質はstage分割、低temperature、self-reviewで補う。

## 成果物

- `feature_spec.json`
- `test_model.json`
- `observation_set.json`
- `risk_register.json`
- `manual_case_set.json`
- `effort_plan.json`
- `gate_decision.json`
- `release_brief.json`
- `manual-test-design.md`
- `lint_report.json`
- `quality_report.json`
- `run_manifest.json`

`quality_report.json` の点数は構造preflightであり、独立rubric採点ではない。モデル比較や70点受入では、`docs/evaluation-rubric.md` による別主体の採点を使う。

manifestにはprofile、base URL、model、secretを除くconfig hash、入力hash、stage別時間・token usage・repair回数、成果物hashを記録する。raw prompt、API key、推論本文は記録しない。

追加の`usage_summary`はrun全体の入力・出力・総tokens、修復呼出、未報告呼出、予算計上値を表示する。`call_records`は失敗した呼出も記録する。usageが不明な場合は総量をnullにし、0消費とは表示しない。

```powershell
bb-harness run local-design --input goldens/order-cancel.input.md --output tmp/estimate-unused --profile qwen36 --estimate-only
bb-harness run local-design --input goldens/order-cancel.input.md --output tmp/budgeted --profile qwen36 --token-budget 150000
python tools/benchmark_local_efficiency.py --input goldens/order-cancel.input.md --output tmp/comparison --profile qwen36
```

estimate-onlyではモデル探索も生成も行わず、初段だけ入力推定を出す。出力上限は使用予定量ではない。予算はUTF-8 byte数＋余白による入力推定と出力上限で事前予約し、実測usageで精算する。修復も同じ予算を消費する。次の予約が不足すれば非ゼロ終了し、途中成果物とmanifestを残す。

新しいケースはモデルと実行定義の版を持つ。実行前に`model_hash / case_revision`を控え、実行証跡に付ける。同じIDでも別版の証跡は拒否される。旧ケースの読取りは`legacy_unverified`と明示する。詳細は[生成効率と版照合](../skills/manual-bb-test-harness/references/efficient-generation.md)を参照する。

`design_status`はready／degraded／blocked。生成が終了しても設計の不足が残ればCLIは2で終了する。生成失敗は1、構造と必須設計被覆が成立したら0。長さ制限で打ち切られた応答は、構文上正しいJSONでも失敗として扱う。比較には`--modes compact batched`を指定できる。実ファイルを再検証し、未完了を費用削減の成功例にしない。

## 70点台の受入

対象fixture:

- `goldens/order-cancel.input.md`
- `goldens/admin-role-change.input.md`
- `goldens/mobile-session-resume.input.md`

各fixtureを3回実行し、次を満たすことを初期受入とする。

- 全9 runがschema validでautomatic failなし。
- fixtureごとの独立採点中央値70以上。
- 全体中央値70以上、最低65以上。
- 1 run 10分以内。
- risk / effort / Gateの決定的検査100%。

## 運用上の境界

技法拡張ではモデル→risk生成後にtechnique_planを固定し、ケースレビュー後にcoverage_reportを計算する。run_manifestにprompt版・入力hash・生成設定・review_statusを追加し、Markdownには具体的入力と設計／実施／合格数を表示する。型付きモデルが生成されなければlegacy_unstructuredとして計算不能を明示する。[技法被覆ガイド](../skills/manual-bb-test-harness/references/technique-coverage.md) の対応範囲を確認する。

- `local-design` の生成完了はrelease Goを意味しない。
- 実行証跡なしではGateは常に `no_go`。
- 非loopback endpointは明示許可が必要。
- model出力がschemaに通らない場合、無制限に再試行しない。
- provider障害を検知して自動的にlocalへ切り替える機能は初期版に含めない。
