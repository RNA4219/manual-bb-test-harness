# Spec: Schema拡充

## 概要

artifact-contract.mdに定義されている未schema化artifactのJSON Schema追加。機械検証可能な契約体系を完成。

## 目的

- 全artifactの機械検証可能化
- LLM生成artifactの品質Gate自動化
- 外部システム連携時の型安全性
- documentation自動生成基盤

## 要件

### R1: 新規schema作成

| id | artifact | 優先度 | 状況 |
|---|---|---|---|
| R1.1 | observation_set.schema.json | P0 | 未作成 |
| R1.2 | effort_plan.schema.json | P0 | 未作成 |
| R1.3 | release_brief.schema.json | P0 | 未作成 |
| R1.4 | forward_test_report.schema.json | P1 | 未作成 |

### R2: 既存schema修正

| id | 修正内容 | 優先度 |
|---|---|---|
| R2.1 | shared_defs.schema.jsonにSourceRef/Assumption型追加 | P0 |
| R2.2 | 各schemaで$ref参照統一 | P0 |
| R2.3 | description/enumerationの双语化 | P1 |

### R3: schema検証tool

| id | 要件 | 優先度 |
|---|---|---|
| R3.1 | validate-artifact.py作成（ajv-cli相当） | P0 |
| R3.2 | 全artifact一括検証機能 | P0 |
| R3.3 | 詳細エラー出力（path、message） | P0 |

## 設計

### Schema依存関係

```
shared_defs.schema.json  ← 全schema参照
├── SourceRef
├── Assumption
├── Oracle
└── ConfidenceLevel

feature_spec.schema.json
├── $ref: shared_defs#/definitions/SourceRef
├── $ref: shared_defs#/definitions/Assumption

test_model.schema.json
├── flows[]
├── states[]
├── valid_transitions[]
├── invalid_transitions[]
├── role_matrix[]
├── regression_edges[]
└── quality_lenses[]

observation_set.schema.json
├── observations[]
│   ├── id
│   ├── title
│   ├── view (black/gray/white)
│   ├── coverage_item_id
│   ├── mandatory (boolean)
│   ├── techniques[]
│   ├── rationale
│   └── source_refs[]
│   └── assumptions[]

risk_register.schema.json  ← 既存
├── risks[]
│   ├── id
│   ├── scenario
│   ├── impact (1-5)
│   ├── likelihood (1-5)
│   ├── modifiers[]
│   ├── score (0-100)
│   ├── priority (P0-P3)
│   ├── rationale
│   └── trace_to[]

manual_case_set.schema.json  ← 既存
├── manual_cases[]
├── exploratory_charters[]

effort_plan.schema.json
├── feature_id
├── phases[]
│   ├── phase_name
│   ├── activities[]
│   ├── estimate_hours
│   ├── owner
│   └── dependencies[]
├── total_estimate_hours
├── retry_buffer_percent
├── execution_order[]

gate_decision.schema.json  ← 既存

release_brief.schema.json
├── feature_id
├── title
├── decision (go/conditional_go/no_go)
├── summary
├── evidence[]
├── residual_risks[]
├── waivers[]
├── required_follow_up[]
├── sign_off[]
│   ├── approver
│   ├── date
│   └── comment

execution_evidence.schema.json  ← 既存

forward_test_report.schema.json
├── feature_id
├── skill_name
├── input_file
├── output_file
├── score (0-100)
├── pass_status (pass/conditional_pass/fail)
├── rubric_breakdown{}
│   ├── category
│   ├── weight
│   ├── score
│   └── checks[]
├── findings[]
│   ├── type
│   ├── text
│   ├── priority
│   └── source_ref
├── notes
├── timestamp
```

### validate-artifact.py設計

```python
"""Validate artifact JSON against schema.

Usage:
    python scripts/validate-artifact.py --artifact <file.json> --type <artifact_type>
    python scripts/validate-artifact.py --all <directory>
    
Example:
    python scripts/validate-artifact.py \
        --artifact examples/artifacts/order-cancel.feature_spec.json \
        --type feature_spec
"""

def validate_artifact(artifact_path: Path, schema_type: str) -> list[str]:
    """Validate artifact against schema, return errors."""
    # Load artifact
    artifact = load_json(artifact_path)
    
    # Load schema
    schema_path = SCHEMA_DIR / f"{schema_type}.schema.json"
    schema = load_json(schema_path)
    
    # Resolve $ref references
    schema = resolve_refs(schema, SCHEMA_DIR)
    
    # Validate
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(artifact))
    
    return [format_error(e) for e in errors]
```

## インターフェース

### CLI

```bash
# 単一artifact検証
python scripts/validate-artifact.py \
    --artifact examples/artifacts/order-cancel.feature_spec.json \
    --type feature_spec

# 一括検証
python scripts/validate-artifact.py --all examples/artifacts/

# CI統合
python scripts/validate-artifact.py --all examples/artifacts/ --strict
```

### 出力

```json
{
  "valid": false,
  "artifact": "order-cancel.feature_spec.json",
  "errors": [
    {
      "path": "/acceptance_criteria/0",
      "message": "Expected array, got string",
      "schema_path": "#/properties/acceptance_criteria/items/type"
    }
  ]
}
```

## 制約

- JSON Schema Draft 2020-12使用
- $ref参照は同schema内のshared_defs
- 循環参照禁止
- descriptionは英語必須（日本語optional）

## テスト観点

| 观点 | ケース |
|---|---|
| 正常系 | 正しいartifact → valid=true |
| 異常系 | required欠損 → valid=false、詳細path |
| 異常系 | type不一致 → valid=false |
| 正常系 | $ref解決成功 |
| 正常系 | 一括検証で全artifact pass |

## 受入基準

- [ ] observation_set.schema.json作成
- [ ] effort_plan.schema.json作成
- [ ] release_brief.schema.json作成
- [ ] shared_defs.schema.jsonにSourceRef/Assumption型追加
- [ ] validate-artifact.py作成
- [ ] examples/artifacts/*.json全検証pass
- [ ] CI validate.ymlに統合