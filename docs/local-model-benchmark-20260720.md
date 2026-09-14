# Qwen3.6 27B local-design benchmark — 2026-07-20

## 結論

Qwen3.6 27Bを候補生成器とし、型検証・risk/effort算術・trace補正・self-review・既存Gateを組み合わせたパイプラインは、初期70点受入を満たした。

構造preflightの100点は正式点に使わず、Codex GPT-5.6 Solが `docs/evaluation-rubric.md` と各golden expected anchorを用いて補正後artifactを独立採点した。

| fixture | run 1 | run 2 | run 3 | median |
|---|---:|---:|---:|---:|
| order-cancel | 86 | 85 | 86 | 86 |
| admin-role-change | 78 | 82 | 83 | 82 |
| mobile-session-resume | 93 | 95 | 92 | 93 |

- 全体中央値: **86**
- 最低点: **78**
- 70点条件: **PASS**

## Machine checks

正式出力は `tmp/local-qwen-benchmark-final/<fixture>/run-{1..3}` に保存し、`scripts/verify-local-benchmark.py` で再検算した。

- 成功run: 9/9
- schema / artifact hash: 9/9
- automatic fail: 0/9
- risk score / priority: 9/9一致
- effort合計 / buffer: 9/9一致
- execution evidenceなしGate: 9/9 `no_go`
- 最大時間: 453.744秒
- 中央時間: 421.731秒
- 10分以内: 9/9
- repair合計: 5回

```powershell
uv run python scripts\verify-local-benchmark.py `
  --input tmp\local-qwen-benchmark-final `
  --scores docs\local-model-benchmark-scores-20260720.json `
  --output tmp\local-qwen-benchmark-final\acceptance-summary.json
```

## Scoring notes

### order-cancel

state/rule/role/regression、在庫・coupon・二重実行を安定して抽出した。一方、runによってP0過多または出荷済み/決済失敗riskのP3過小があり、在庫数0など仕様から弱く導いた境界caseもある。このためrisk/manual caseを満点にしなかった。

### admin-role-change

最後のowner、不正昇格、自己降格、invited、即時反映を扱えた。最弱runは78点。監査ログriskが欠けるrun、normal caseへ無関係risk traceが混ざるrun、対象外寄りのmobile charterがあり、3 fixture中もっともレビュー依存度が高い。

### mobile-session-resume

background resume、通信断retry、重複送信、1件境界、camera permission、push entry、iOS/Androidを最も安定して扱った。仕様外の強制終了はhuman oracleへ分離され、3 runとも実務投入可能な形だった。

## Rejected experiment

Qwen3.6のplanning stageでthinkingを有効にした試行は、100.5秒reasoningを続けた後にJSON contentが空で終了した。`qwen36` profileはthinking offを正式設定とし、stage分割・低temperature・局所repair・self-reviewで品質を確保する。

## Remaining risks

- riskとcaseをobservation経由で再接続しても、意味的に広いobservationでは余分なrisk traceが残る。
- adminのaudit riskとownership matrixは人間レビュー推奨。
- 7分前後/件のため緊急時には実用範囲だが、対話的な即応用途にはまだ遅い。
- 本評価はQwen3.6 27B UD-Q4_K_XL、ctx 16384、llama.cppの単一環境。別quant/runtimeでは再評価が必要。
