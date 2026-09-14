# 割引後金額の被覆サンプル

4つのケースと3件の合成実行証跡により、設計100%、実施75%、合格2件を区別する。すべて説明用データで、実サービスの検収証跡ではない。 2026-09-14 に現行の仕様版・定義版へ合わせて合成サンプルを再生成した。

- `discount.feature_spec.json`: 金額と送料の仕様根拠
- `discount.test_model.json`: P-Dの線形境界、D=2000、1円刻み、reliable基準
- `discount.technique_plan.json`: 決定的に生成した4つの被覆義務
- `discount.manual_case_set.json`: 同じタイトル・異なる4入力を保持したケース
- `examples/coverage-evidence/discount-domain/`: pass / fail / passの例。4件目は未実施。既存Gate例の証跡と混ざらない独立した入力ディレクトリ
- `discount.coverage_report.json`: 設計4/4、実施3/4、合格2/4の計算結果

再生成手順は [技法被覆ガイド](../../../../skills/manual-bb-test-harness/references/technique-coverage.md) を参照。

## 分割生成・完了判定（2026-09-10）

`discount.local_run_manifest.json`は、batchedを予算1で停止させたモデル呼出0の例を、固定ID・時刻・空artifact一覧に整えた契約サンプル。実LLMの品質評価や実行証跡には利用しない。design_status=blocked、finish_reason/model=null、usage_summary.calls=0を示す。
