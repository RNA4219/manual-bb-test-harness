# docs/

このディレクトリは、Skill 実行時の正本ではないが、repo 運用や評価で参照する補助文書を置く。

## 入口

| file | role |
|---|---|
| `human-readme.md` | 人間向け概要、利用説明 |
| `evaluation-rubric.md` | forward-test の採点基準 |
| `local-model-guide.md` | Local Modeの設定・実行・fail closed境界 |
| `release-policy.md` | gate と release 判断の補助方針 |
| `notion-report-guide.md` | Notion への forward-test 記録手順 |
| `notion-forward-test-template.md` | Notion 記録テンプレート |
| `forward-test-report-template.md` | Markdown fallback テンプレート |
| `improvement-notes.md` | 改善履歴 |
| `release-review-20260516.md` | repo self-review の release readiness 記録 |
| `research/deep-research-report.md` | 背景調査 |

## サブディレクトリ

| dir | role |
|---|---|
| `tasks/` | 変更単位の Task Seed |
| `acceptance/` | 検収記録 |

## 使い分け

- repo 全体の読み順は root の `HUB.codex.md` を使う。
- Skill 実行時に読む詳細方針は `skills/manual-bb-test-harness/references/` を正本にする。
- forward-test の結果を採点したいときだけ、このディレクトリの rubric と report docs を読む。
