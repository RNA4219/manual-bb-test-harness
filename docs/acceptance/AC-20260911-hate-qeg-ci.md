# HATE・QEG CI連携の検収

対象仕様: [spec-08](../specs/spec-08-hate-qeg-ci.md)。実装は`tools/ci/quality_evidence.py`、workflowは`.github/workflows/validate.yml`。

## ローカル確認

- CI境界の回帰25件、既存仕様validator 32件の計57件が成功。ruff、diff check、Workflow Cookbook freshnessも成功。
- 実pytest 1026件の出力をHATEで正規化・exportし、eligible、export success、partial=false、missing_executions=0を確認。
- 上記実pytest試行は1024 passed・仕様チェック2 failedだった。未完了の受入結果と仕様書の基準定義を区別し、仕様書の必須形式を整えた後、該当validator 32件が成功した。失敗試行の原本は変更していない。
- この実pytest試行のHATE出力をQEGへ渡し、schema/hash検証に成功したうえで`no_go`・終了コード2となることを確認した。
- QEGの実CLIによる小さな契約検証で正常入力go、失敗testとcoverage 84.99%はno_go、skipとhash改変はdisqualified。いずれも非goの終了コードは2。これはconsumer契約検証用データであり実プロダクト受入ではない。
- HATE固定版: `f76f1b90772bc609094ca568cd44ca161593349f`。QEG固定版: `d957fc25907e1b678add65eb47f92853dd093d32`。

## CI確認

GitHub Actionsによる今回の変更の確認は実施中。全体85%・Gate90%、既存のPython matrix／integration／PowerShell／package smokeを保持し、新しいHATE/QEGジョブも成功を必須とする。

原本は`ci-raw-evidence-<attempt>`、HATE・QEG出力は`hate-qeg-evidence-<attempt>`として、失敗時も14日間保存する。

## 評価範囲

repository CIの自動検証を対象とする。実LLM・外部サービスの受入、手動受入、変更行と各testの対応、RanD・Code-to-gate全producer連携、リリース承認は未評価。以前のLocal Modeベンチマーク未達を今回のCI成功で合格にしない。今回の収集・変換・判定処理のLLM呼出は0回。
