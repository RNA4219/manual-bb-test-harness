# artifacts/

## 目的

このディレクトリには JSON artifact の最小例を配置する。
schema 定義に対応する concrete example を提供する。

## ファイル一覧

### order-cancel (注文キャンセル機能)

| file | description |
|---|---|
| `order-cancel.feature_spec.json` | feature_spec: 正規化された仕様 |
| `order-cancel.test_model.json` | test_model: coverage model |
| `order-cancel.manual_case_set.json` | manual_case_set: 手動テストケース |
| `order-cancel.gate_decision.json` | gate_decision: 品質ゲート判定 |

### admin-role-change (権限変更機能)

| file | description |
|---|---|
| `admin-role-change.feature_spec.json` | feature_spec: 正規化された仕様 |
| `admin-role-change.test_model.json` | test_model: coverage model |

## Schema 対応

各 JSON file は対応する schema に従う:

| artifact | schema |
|---|---|
| `*.feature_spec.json` | `schemas/feature_spec.schema.json` |
| `*.test_model.json` | `schemas/test_model.schema.json` |
| `*.manual_case_set.json` | `schemas/manual_case_set.schema.json` |
| `*.gate_decision.json` | `schemas/gate_decision.schema.json` |

## 使い方

Example を読んで、自分の feature の artifact 作成時の reference にする。

```powershell
Get-Content examples\artifacts\order-cancel.feature_spec.json | ConvertFrom-Json
```

## Example 追加時のルール

1. 対応する schema に従うこと
2. `feature_id` は uppercase + hyphen 形式（例: `ORD-CANCEL-01`）
3. `source_refs`, `trace_to` などの traceability field を含める
4. 「最小」であり「完全」でなくてもよい