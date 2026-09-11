# Spec: HATE・QEGによるCI証跡の検証

## 概要

既存のvalidate workflowに、pytestの実行証跡をHATEで正規化し、QEGで検証・判定するジョブを追加する。対象はこのリポジトリの自動検証であり、リリース承認や実LLMによる受入完了は対象外とする。

## 目的

緑CIの根拠を、同じコミット・GitHub run・attemptのJUnit、カバレッジ、HATE出力、QEG判定まで追跡できるようにする。既存の未コミット改修を保持し、仕様更新後に実装する。

## 要件

| id | 要件 | 優先度 |
|---|---|---|
| R1 | Python 3.10〜3.13、integration、PowerShell、package smoke、全体85%・Gate90%の既存条件を維持する | P0 |
| R2 | 全体pytestのJUnit・LCOV・coverage JSON・終了コード・開始終了時刻・Gitコミット・run ID・attemptを保存する | P0 |
| R3 | HATE P0aとQEG exportを実行し、生成されたHATE/v1の出力を保存する | P0 |
| R4 | HATE/v1からQEG 0.2へ明示的に変換する。成功fixtureのコピーや未実行証跡の生成はしない | P0 |
| R5 | QEGに各testとexecution、blocking obligation、build binding、元ファイルのSHA-256を渡す。requireExecutedTests=trueで実consumerの検証・判定を実行する | P0 |
| R6 | 空・欠落・不正な結果、未知の契約、異なるコミット/run/attempt、重複test、非成功結果、カバレッジ未達、HATE拒否、QEG非goはCI失敗とする | P0 |
| R7 | 証跡を失敗時もartifactに保存する。依存先はコミットSHA固定、権限はcontents:read、秘密情報を証跡へ含めない | P0 |
| R8 | CI scopeと未評価項目をレポートに明示する。mockで外部サービスを代替する単体テストの成功を、実サービス・実LLMの成功に読み替えない | P0 |
| R9 | ローカルで正常系・欠測・改変・版不一致・失敗結果の回帰検証を行い、変更をpushしたGitHub Actionsの全必須ジョブ成功を確認する | P0 |

## 設計

coverageジョブで実行と収集を一体化し、元ファイルのhash一覧を保存する。HATE/QEGジョブは同一workflow runのartifactだけを入力とし、checkoutのHEADとGitHub run/attemptを照合する。HATEとQEGは別checkoutにSHA固定で配置し、manual-bbの通常利用者に追加runtimeを要求しない。

coverage.pyのJSONは`--show-contexts`でエクスポートし、HATEへJUnit・context・coverage JSONの原本を渡す。現行HATEが未対応の名前付きbranchを含むLCOVは、改変せずQEGのhash検証対象として保存する。HATEのcoverage.py adapterが扱う実行行と、全体branch coverage閾値の評価を区別する。個別test contextのない計測からtestと行の関連を補完しない。

HATE exporterのwire versionはHATE/v1、QEG consumerは0.2のため、CI専用adapterをtools/ciに置く。HATEのtest identity・status・provenanceを検証したうえで、QEGのnative_graph、qeg-execution/v1へ変換する。変換後の実行JSONと元JUnit、HATE正規化結果、export bundleを保存・hash参照する。coverageは集計値であり、特定testと行の関連は推測しない。

QEG policyはstandard、scopeはreal_environmentのリポジトリCIに限定する。全testをblocking obligationに選択し、実行の欠測・skipを成功にしない。全体coverage閾値はpytestと収集adapterで確認し、QEGへその判断根拠を保存する。実際に実施した終了コード・coverage閾値の検査もtest/executionとして渡す。waiverや承認証拠を自動作成しない。

## インターフェース

```bash
python tools/ci/quality_evidence.py capture --out tmp/ci-evidence
# HATEを固定revisionからインストールしたPythonで実行する。
python tools/ci/quality_evidence.py convert --out tmp/ci-evidence
node tmp/quality-tools/qeg/qeg-report-action/dist/cli.mjs record tmp/ci-evidence/qeg
```

captureはpytestの終了コード、convertは正常0・入力不正/HATE失敗1を返す。QEGはgo=0、それ以外は非0。出力先は新規作成し、同一runの成果物を暗黙に上書きしない。

## テスト観点

元ファイルの欠落・改変、run/attempt/コミット不一致、空または重複identity、HATEのstatus変更、未知version、pytest非0、coverage 85%の境界、skip、出力先の再利用を検証する。正常fixtureだけでなく、実pytest出力を両consumerへ通す。

CRLF形式のSkillを読むPowerShellテストは、Windows・Linuxの両方で実行する。必要ファイルを持つ一時Skillを入力にし、実際のvalidator終了コード0と成功出力を確認する。改行形式の検証をOS名だけでskipせず、QEGの未実行拒否も維持する。

## 受入基準

以下は受入基準の定義確認であり、実行完了の記録ではない。実行結果は検収記録と対象コミットのGitHub Actions runで確認する。

- [x] 実pytest結果からHATE正規化・export・QEG判定までの完走を受入に要求する。
- [x] 件数・identity・statusの保持と、元証跡改変・別runへの付替え拒否を受入に要求する。
- [x] 失敗test、空結果、skip、coverage未達をgreenにしないことを受入に要求する。
- [x] 既存85%/90%条件・全検証、および今回のコミットを含むGitHub Actions runのsuccessを受入に要求する。

## 制約

RanD・Code-to-gateの全producer連携、手動受入、実LLM評価、変更行と個別testの対応、統計的な信頼度校正、リリース承認は未評価とする。CIのgoは本仕様の自動検証範囲だけに適用する。
