# examples/

## 目的

このディレクトリには schema 化した artifact の最小例を配置する。
新規 artifact 作成時の reference として使用する。

## 構造

```
examples/
└── artifacts/       # JSON artifact example files
```

## artifacts/ の内容

| file | artifact type |
|---|---|
| `order-cancel.feature_spec.json` | feature_spec の最小例 |
| `order-cancel.test_model.json` | test_model の最小例 |
| `order-cancel.manual_case_set.json` | manual_case_set の最小例 |
| `order-cancel.gate_decision.json` | gate_decision の最小例 |
| `admin-role-change.feature_spec.json` | feature_spec (権限系) の最小例 |
| `admin-role-change.test_model.json` | test_model (権限系) の最小例 |

## 使い方

### Example を参考に新規 artifact 作成

1. 該当する schema を `schemas/` から確認
2. `examples/artifacts/` の同名 example を読む
3. 自分の feature の内容に合わせて値を変更
4. schema validation を実行して確認

### Validation 実行

```powershell
python scripts/quick-validate-skill.py skills/manual-bb-test-harness
```

## 注意事項

- example は「最小」であり「完全」ではない
- 実運用ではより多くの field を含むことが多い
- `source_refs`, `trace_to` などの traceability field は example でも必須