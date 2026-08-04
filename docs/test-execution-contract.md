# Test Execution Contract

## 目的

生成済みの手動テストケースを、作業チェックリストではなく、リスクとoracleに紐づくリリース証拠として扱う。

## 実行担当者が記録してよいもの

- actual result
- `pass / fail / blocked / unknown`
- evidence、attachments
- findings、anomaly notes、defect
- 実行環境、端末、network profile

## 事前承認なしで変更してはならないもの

- expected result
- oracle / oracle refs
- test steps、preconditions、test data
- priority、primary view
- platform、device、viewportの対象範囲
- traceability、risk、mandatory observation
- ケースの削除、統合、代替、SKIP

実行困難、重複疑い、仕様不明、期待結果への疑義がある場合は、内容を書き換えず `blocked` または `unknown` として設計者へ返却する。

## `[要確認]` の扱い

`[要確認]` は実行担当者が期待結果を決めるための空欄ではない。

1. 実装または実行前に質問する。
2. oracle ownerが期待結果を確定する。
3. 承認済みケースを再発行する。
4. 再発行版で実行する。

未確定のまま実装挙動へ期待結果を合わせてはならない。

## SKIP契約

`skip` は未実施の別名ではなく、承認済みのscope変更である。次をすべて満たす。

- 実行前に申請されている
- 申請者と承認者が記録されている
- 承認時刻と追跡可能な承認IDがある
- 影響するrisk IDが列挙されている
- reason codeと理由が残る
- 代替証跡がある場合、その参照が残る

承認済みSKIPでも `pass` にはならない。P0、mandatory observation、profile閾値、残余riskは通常どおりGate評価する。

### reason code

- `not_applicable`
- `duplicate_coverage`
- `environment_constraint`
- `approved_scope_reduction`

### `duplicate_coverage` の追加条件

「同じ機能を見た」だけでは代替にならない。

- 同一のcoverage claimを証明している
- failure modeが同一または包含される
- platform固有、UI固有、内部状態固有の観測を失わない
- 代替証跡を一意に参照できる

PCのwhite/gray-box確認とSPのblack-box挙動確認は、既定では相互代替不可とする。

## 構造化SKIP例

```json
{
  "result": "skip",
  "skip_approval": {
    "approval_id": "SKIP-APPROVAL-20260804-001",
    "approval_mode": "pre_execution",
    "reason_code": "duplicate_coverage",
    "reason": "同一coverage claimを別ケースの証跡が包含するため",
    "requested_by": "executor-a",
    "approved_by": "qa-owner",
    "approved_at": "2026-08-04T10:00:00+09:00",
    "risk_ids": ["RISK-SP-001"],
    "replacement_evidence_refs": ["RUN-20260804-TC-PC-001"]
  }
}
```

## Gateのfail-closed条件

次はartifact不正として拒否する。

- `result=skip` なのに `skip_approval` がない
- 承認ID、承認者、承認時刻、risk IDがない
- `duplicate_coverage` なのに代替証跡がない
- `skip_approval` があるのに `result=skip` ではない

事後承認、自己承認、承認時刻と実行時刻の前後関係は、承認システムまたはGate拡張で追加検証する。schema記録だけで正当化されたとはみなさない。
