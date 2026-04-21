# Improvement Notes

このメモは、`manual-bb-test-harness` の初版運用後に検討する強化余地を残すためのもの。

この Skill は Notion に forward-test 結果を残し、人間が rubric で評価する運用を主軸にする。JSON Schema は運用の正本ではなく、artifact の最低限の形を保つ補助として扱う。

## Current Completion Stance

- Skill 本体、参照方針、golden、rubric、Notion テンプレートは初版として実質完成。
- 品質保証の中心は `docs/evaluation-rubric.md`、`goldens/`、Notion forward-test 記録。
- `schemas/` は機械連携が必要になったときの契約であり、Notion 運用を置き換えるものではない。

## Near-Term Improvements

1. インストール済み Skill と repo 内 Skill を同期する。
2. Notion で golden forward-test を 1-2 件実行し、rubric 採点を残す。
3. forward-test で見つかった不足を `references/`、`goldens/`、domain pack に反映する。
4. `docs/notion-report-guide.md` の properties が実運用に合うか見直す。

## Optional Improvements

- Domain pack を追加する。候補は auth、payment、notification、mobile/offline。
- Golden を増やす。候補は権限、決済、外部連携失敗、モバイル中断復帰。
- `failure-modes.md` に forward-test で実際に起きた失敗を追加する。
- Markdown fallback report を、Notion に転記しやすい形へ寄せる。

## Schema Boundary

Schema 強化は優先度を低めに置く。

やる場合も、次の範囲に留める。

- JSON が壊れていないことを検出する。
- artifact の大まかな構造が変わっていないことを確認する。
- 外部ツール連携が必要になった artifact だけ schema を強くする。

次のような強化は、Notion 運用の摩擦になる場合は行わない。

- Notion 評価で十分な項目を厳密 schema に重複定義する。
- rubric 判断を schema で代替しようとする。
- forward-test の自由記述を過度に構造化する。

## Release Readiness

初版リリースの判定は `go`。

ただし、リリース後の改善判断は Notion の forward-test 記録を正本とし、repo 側では再利用可能な方針、テンプレート、golden anchor の更新に集中する。
