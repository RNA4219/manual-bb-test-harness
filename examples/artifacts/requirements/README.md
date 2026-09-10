# 要件定義の信頼度の例

既存の`../order-cancel.feature_spec.json`と`../order-cancel.phase_contract.json`を入力にした、決定的な評価例。`order.requirements_review.json`は未記入のレビュー雛形であり、人間がレビューした事実を表さない。

要件6件、要確認2件（critical 1 / high 1）、未レビュー6件。重み12、基礎点35、criticalの上限39を適用して**35点 / low / blocked**。技術リスク1件は要件の不確実性へ加算しない。

```powershell
bb-harness evaluate requirements --input examples/artifacts/order-cancel.feature_spec.json --phase-contract examples/artifacts/order-cancel.phase_contract.json --output tmp/requirements-demo
```

`order.requirements_confidence.json`に点数内訳と根拠を保存する。[利用手順](../../../skills/manual-bb-test-harness/references/requirements-confidence.md)を参照。
