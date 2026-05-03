# schemas/

## 目的

このディレクトリには artifact の JSON Schema 定義を配置する。
機械連携が必要な場合のみ schema を使用する。Notion 運用を主とする場合は schema は補助扱い。

## ファイル一覧

| file | purpose |
|---|---|
| `feature_spec.schema.json` | feature_spec artifact の構造定義 |
| `test_model.schema.json` | test_model artifact の構造定義 |
| `manual_case_set.schema.json` | manual_case_set artifact の構造定義 |
| `gate_decision.schema.json` | gate_decision artifact の構造定義 |
| `shared_defs.schema.json` | SourceRef, Assumption などの共通型定義 |

## $id URL について

### 重要: $id は identifier（識別子）であり、resolution endpoint（解決endpoint）ではない

各 schema の `$id` field は以下の形式を取る:
```
"https://github.com/RNA4219/manual-bb-test-harness/schemas/xxx.schema.json"
```

**この URL について:**
- JSON Schema仕様では `$id` は「識別子」として定義される
- この URL は schema を一意に識別するための名前空間
- **GET request で実際に schema を取得することはできない**（404になる）
- これは正常な状態であり、仕様上問題ない

### 外部ツール連携時の参照方法

外部ツールで schema validation を行う場合:

1. **ローカル参照（推奨）**
   ```python
   # schema file をローカルから直接読み込む
   schema_path = Path("schemas/feature_spec.schema.json")
   schema = json.loads(schema_path.read_text())
   ```

2. **絶対参照（必要時）**
   - `$id` URL は識別子として使用
   - 実際の schema file は repository 内の `schemas/` から取得

### GitHub Pages hosting（optional）

将来、以下の理由で GitHub Pages hosting が必要になる可能性がある:
- 外部ツールが HTTP GET で schema を取得する必要がある
- `$ref` 句で外部 schema を参照する必要がある

必要になった時点で別途実施する。現在は不要。

## 使い方

### Validation

```python
import json
from pathlib import Path
import jsonschema

schema = json.loads(Path("schemas/feature_spec.schema.json").read_text())
artifact = json.loads(Path("examples/artifacts/order-cancel.feature_spec.json").read_text())
jsonschema.validate(artifact, schema)
```

### Schema 更新時の注意

- schema を変更する場合は `examples/artifacts/` の対応ファイルも更新する
- description field を追加/変更する場合は 日本語/英語 両方のユーザーに影響するため慎重に
- `additionalProperties: false` は維持する（意図しない field 追加を防止）