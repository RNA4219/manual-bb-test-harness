日本語で記載する。

## Repo Purpose

このリポジトリは、手動ブラックボックス前提のテスト設計 Skill `manual-bb-test-harness` を配布・保守するための Skill リポジトリ。

## Default Workflow

1. まず `README.md` を読む。
2. Skill 本体を変更する場合は `skills/manual-bb-test-harness/SKILL.md` を読む。
3. 詳細方針は `skills/manual-bb-test-harness/references/` の該当ファイルだけ読む。
4. 背景調査が必要な場合のみ `docs/research/deep-research-report.md` を読む。
5. 出力品質を変える場合は `docs/evaluation-rubric.md`、`docs/notion-report-guide.md`、`goldens/` を確認する。
6. 変更後は validation を実行する。

## Editing Rules

- `SKILL.md` は短く保ち、長い説明は `references/` に分離する。
- Skill 本体に README や changelog などの補助文書を増やさない。
- repo の説明文書は root または `docs/` に置く。
- frontmatter は `name` と `description` のみにする。
- `description` には、何をする Skill かと、いつ使うかを含める。
- artifact contract を変えるときは `schemas/` と `examples/artifacts/` を同時に更新する。
- golden は厳密 snapshot ではなく review anchor として扱う。
- forward-test の canonical run log は Notion 側を主とし、repo 内の report template は雛形として扱う。
- 出力やコメントは日本語を基本にする。

## Validation

PowerShell:

```powershell
$env:PYTHONUTF8='1'
uv run --with pyyaml python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" ".\skills\manual-bb-test-harness"
python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness
.\scripts\validate-skill.ps1
```
