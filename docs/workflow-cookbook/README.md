# Workflow Cookbook Knowledge Map

manual-bb-test-harness のドキュメント知識マップ。

## Purpose

AI エージェントが最小トークンで repo 全体を把握できるようにする。

## Files

| File | Role | Size |
|------|------|------|
| `index.json` | 全ノード (33個) とエッジ (45個) の一覧 | ~15KB |
| `hot.json` | 主要エントリポイント (6個) と quick_paths | ~3KB |
| `caps/*.json` | 各ドキュメントの要約 (33個) | ~1KB each |

## Usage

### For AI Agents

1. **README.md** の `<!-- LLM-BOOTSTRAP -->` ブロックを読む
2. **hot.json** で主要エントリポイントを確認
3. **index.json** で対象ファイル ±2 hop のノードを取得
4. **caps/*.json** で必要なノードの要約のみ読む

### Quick Paths

`hot.json` に定義された quick_paths:

- `getting_started`: README → HUB → human-readme
- `skill_execution`: SKILL → artifact-contract → case-design-policy → goldens
- `cli_operations`: RUNBOOK → spec-02 → spec-04
- `artifact_changes`: BLUEPRINT → artifact-contract → schemas → examples → goldens
- `quality_assurance`: EVALUATION → evaluation-rubric → acceptance records
- `mobile_testing`: platform-pack-mobile → mobile goldens
- `specifications`: spec-01 → spec-02 → spec-03 → spec-04

### Node Roles

| Role | Count | Examples |
|------|-------|----------|
| overview | 2 | README.md, human-readme.md |
| navigation | 2 | HUB.codex.md, workflow-cookbook/index.json |
| specification | 7 | BLUEPRINT.md, SPEC.md, spec-01~04 |
| operations | 1 | RUNBOOK.md |
| policy | 2 | GUARDRAILS.md, AGENTS.md |
| acceptance | 2 | EVALUATION.md, AC-20260516-01.md |
| skill | 1 | SKILL.md |
| reference | 10 | artifact-contract.md, case-design-policy.md, domain-pack-*, failure-modes.md |
| task | 1 | task-mobile-docs-release-readiness-20260516.md |
| golden | 4 | order-cancel.*, mobile-session-resume.* |
| history | 3 | CHANGELOG.md, improvement-notes.md, release-review-20260516.md |

## Maintenance

### When to Update

- ドキュメントを追加/削除したとき
- ドキュメント間の関係が変わったとき
- 主要な仕様変更があったとき

### Update Procedure

1. `index.json` の nodes/edges を更新
2. 影響する `caps/*.json` を更新
3. 主要エントリポイントが変われば `hot.json` を更新
4. `generated_at` を 5桁ゼロ埋め連番でインクリメント (例: "00001" → "00002")

### Validation

```bash
# JSON syntax check
node -e "JSON.parse(require('fs').readFileSync('docs/workflow-cookbook/index.json'))"
node -e "JSON.parse(require('fs').readFileSync('docs/workflow-cookbook/hot.json'))"

# Count nodes and edges
jq '.nodes | length' docs/workflow-cookbook/index.json  # 28
jq '.edges | length' docs/workflow-cookbook/index.json  # 45
```

## Schema

### index.json

```json
{
  "version": "1.0.0",
  "generated_at": "00001",
  "nodes": [
    {
      "id": "path/to/file.md",
      "path": "./path/to/file.md",
      "role": "specification",
      "title": "Document Title",
      "description": "One-line description"
    }
  ],
  "edges": [
    {
      "from": "source.md",
      "to": "target.md",
      "type": "references"
    }
  ]
}
```

### hot.json

```json
{
  "hot_nodes": [
    {
      "id": "README.md",
      "path": "./README.md",
      "role": "overview",
      "title": "Project Overview",
      "summary": "Multi-line summary (120 words max)",
      "priority": 1,
      "use_cases": ["Getting started", "Understanding structure"]
    }
  ],
  "quick_paths": {
    "getting_started": ["README.md", "HUB.codex.md"]
  }
}
```

### caps/*.json

```json
{
  "id": "path/to/file.md",
  "role": "specification",
  "title": "Document Title",
  "summary": "Concise summary (120 words max)",
  "public_api": ["function_name()", "CLI command"],
  "deps_out": ["referenced1.md", "referenced2.md"],
  "deps_in": ["referencing.md"],
  "risks": ["Risk description"],
  "tests": ["tests/test_file.py"],
  "last_verified": "2026-05-30"
}
```

## References

- `README.md` - LLM-BOOTSTRAP ブロック
- `HUB.codex.md` - Document routing
- workflow-cookbook GUARDRAILS.md - Birdseye minimal context intake guardrails
