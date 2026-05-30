# Workflow Cookbook

このディレクトリには、プロジェクトの知識マップを格納します。

## Files

- `index.json`: すべてのノードとエッジのリスト
- `hot.json`: 主要エントリポイントと quick paths
- `caps/*.json`: 各ノードの詳細カプセル

## Update Procedure

1. ドキュメントを追加・削除・変更したら、`index.json` を更新
2. 主要エントリポイントが変わったら、`hot.json` を更新
3. 新しいノードの詳細は `caps/` に追加
4. `generated_at` をインクリメント（例: "00001" → "00002"）

## Validation

```bash
# JSON 構文チェック
node -e "JSON.parse(require('fs').readFileSync('docs/workflow-cookbook/index.json'))"
node -e "JSON.parse(require('fs').readFileSync('docs/workflow-cookbook/hot.json'))"

# ノード数とエッジ数を確認
node -e "const d = JSON.parse(require('fs').readFileSync('docs/workflow-cookbook/index.json')); console.log('Nodes:', d.metadata.total_nodes, 'Edges:', d.metadata.total_edges)"
```

## Schema

### index.json

```json
{
  "version": "1.0.0",
  "generated_at": "00002",
  "nodes": [...],
  "edges": [...],
  "metadata": {
    "repo": "repo-name",
    "tier": 3,
    "last_updated": "2026-05-30",
    "total_nodes": 28,
    "total_edges": 45,
    "total_capsules": 28
  }
}
```

### hot.json

```json
{
  "version": "1.0.0",
  "generated_at": "00002",
  "hot_nodes": [...],
  "quick_paths": {...},
  "project_status": {
    "tier": 3,
    "last_updated": "2026-05-30"
  }
}
```

### caps/*.json

```json
{
  "id": "path/to/file.md",
  "role": "specification | operations | acceptance | ...",
  "title": "File Title",
  "summary": "One-line summary of the file's purpose and content",
  "deps_out": ["other/file.md"],
  "deps_in": ["another/file.md"],
  "risks": ["Potential risk"],
  "tests": ["test_file.py"],
  "last_verified": "2026-05-30"
}
```
