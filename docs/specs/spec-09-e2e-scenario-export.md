# Spec: 承認済みE2Eシナリオ出力

## 概要

手動設計ケースの原文・期待値・根拠・改訂を維持したまま、レビュー済みbindingからLakda replay入力を決定的に生成する。出力は新規ディレクトリのみ。

## 目的

`bb-harness export-e2e --approved-binding-sha256 <承認時のSHA-256>` は、固定した binding を Rust で変換する。実行には `bb-export-e2e` または Cargo を使用する。従来の引数での v1 出力も利用できる。

操作直後の判定（`afterActionId`）、受入条件との対応（`acceptanceRef`）、金額・件数の判定を含むケースは、Lakda 設定に `reviewedOracleVersion: 2` を書き込む。設定と生成される Playwright シナリオには同じ版の判定規則を適用する。

生成物を元AC/ケース/レビューに追跡できるようにし、LLMによる期待値推測やpass/fail判定を排除する。

## 要件

| ID | 要件 | 優先度 |
|---|---|---|
| MBB-E2E-R01 | feature_specのACとsource refs、およびcase版とoracle refsを要求する | P0 |
| MBB-E2E-R02 | 手順と期待値の一対一bindingを要求し、未知oracleを拒否する | P0 |
| MBB-E2E-R03 | 承認済みの操作列と、指定した時点での判定条件を Lakda 設定と Playwright コードへ出力する | P0 |
| MBB-E2E-R04 | 入力hash、レビュー、ケースとoracleの版を照合する | P0 |
| MBB-E2E-R05 | 保存済み証跡を変更しない | P0 |

## 設計

入力はfeature_spec JSON、manual_case_set JSON、reviewer binding JSON。
bindingのschemaVersionはmanual-bb/e2e-binding/v1であり、
featureId、specRevision、featureSha256、caseSetSha256、
baseUrl、seedとcases配列を持つ。各caseはcaseId、revision、
contentHash、oracleRevision、reviewedBy、reviewRef、
全手順に対応するactions配列と全文一致するchecks配列を持つ。
hashはUTF-8、キーsortのcanonical JSONでSHA-256を計算する。

ケースに記載した期待結果をそのまま使い、`oracle.type=specified` のケースを出力する。
従来の v1 では、操作後の URL と要素の表示状態（`visible`）を判定できる。
Rust で出力する v2 では、`kind: "hidden"` に対象の `locator` とケースが参照する
受入条件 `acceptanceRef` を指定すると、要素の非表示を確認できる。
`afterActionId` を指定するとその操作の直後に、省略すると最後の操作の後に判定する。
Lakda の `obligations` には `hidden` と対象を、Playwright には `toBeHidden()` を出力する。

出力はcaseごとにscenario.md、scenario.json、action-sequence.json、
lakda.config.json、scenario.spec.ts、manifest.json。後者は各生成物の
SHA-256を持つ。入力値やsecretは生成しない。Playwrightコードは
人がレビューする補助形式でありLakdaに任意コードとして渡さない。

## インターフェース

    bb-harness export-e2e --feature-spec feature.json --manual-case-set cases.json --binding binding.json --out new-output
    lakda replay --input new-output/TC-001/action-sequence.json --config new-output/TC-001/lakda.config.json --base-url https://app.example.test/

## テスト観点

正常、再生成同一hash、出力先再利用、改竄/古いcase revision、
未知oracle、秘匿値、危険action、retired case、step/check不足、
旧artifact読み込み互換性を確認する。

## 受入基準

- [x] AC-1: 人手指定bindingからreview IDと期待値・手順を紐づけて新規出力する。
- [x] AC-2: unknown oracle、改訂/入力hash不一致、未承認caseを拒否する。
- [x] AC-3: 同一入力の生成byteは決定的で出力manifestと一致する。

契約schema: `schemas/e2e_binding.schema.json`、`schemas/e2e_scenario.schema.json`、`schemas/e2e_export.schema.json`。
承認済みサンプル: `examples/artifacts/e2e-sample.*.json`。WindowsでもUTF-8原バイト列を直接保存し、manifestのSHA-256と一致させる。

配送サンプルの固定入力は [examples/artifacts/shipping-details](../../examples/artifacts/shipping-details/) にある。
`TC-SHIPPING-CLOSE` は Lakda 同梱の配送ページで質問を開き、回答の表示を確認する。同じ質問をもう一度押し、同じ回答が非表示になることを確認する。

## 未検証事項（現段階では受入の対象外）

- 実target上のLakda replayと独立したreal evidenceの検証。
- 利用製品2件での共通workflow導入およびバージョン更新検証。

## 制約

K-01〜K-07のcharter、Gate、定期実行とスターターセットを扱わない。
Lakdaの外部process起動/外部送信の禁止は緩めない。
この変換処理はブラウザ・ネットワーク・LLMを呼び出さない。
