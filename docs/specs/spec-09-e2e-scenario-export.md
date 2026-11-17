# Spec: 承認済みE2Eシナリオ出力

## 概要

手動設計ケースの原文・期待値・根拠・改訂を維持したまま、レビュー済みbindingからLakda replay入力を決定的に生成する。出力は新規ディレクトリのみ。

## 目的

生成物を元AC/ケース/レビューに追跡できるようにし、LLMによる期待値推測やpass/fail判定を排除する。

## 要件

| ID | 要件 | 優先度 |
|---|---|---|
| MBB-E2E-R01 | feature_specのACとsource refs、およびcase版とoracle refsを要求する | P0 |
| MBB-E2E-R02 | 手順と期待値の一対一bindingを要求し、未知oracleを拒否する | P0 |
| MBB-E2E-R03 | 許可済みActionPlanと最終obligations、reviewableなPlaywright codeを生成する | P0 |
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

既存manual_case_setの指定期待結果を変更しない。oracle.type=specified
のみ対応。URLとvisibleの最終状態をLakdaの既存obligationsに変換する。
中間assertion、金額・件数・任意テキスト、visual、未知predicate、
未承認derived/human/implicitは対応外として拒否する。

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

## 未検証事項（現段階では受入の対象外）

- 実target上のLakda replayと独立したreal evidenceの検証。
- 利用製品2件での共通workflow導入およびバージョン更新検証。

## 制約

K-01〜K-07のcharter、Gate、定期実行とスターターセットを扱わない。
Lakdaの外部process起動/外部送信の禁止は緩めない。
この変換処理はブラウザ・ネットワーク・LLMを呼び出さない。
