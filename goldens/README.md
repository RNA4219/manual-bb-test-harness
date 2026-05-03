# goldens/

## 目要

このディレクトリには Skill の forward-test で使用する golden input/expected を配置する。
出力品質を見るための review anchors であり、厳密 snapshot ではない。

## ファイル一覧

### Markdown形式

| file | purpose |
|---|---|
| `order-cancel.input.md` | 注文キャンセル機能の入力仕様 |
| `order-cancel.expected.md` | 期待される出力の anchor |
| `admin-role-change.input.md` | 権限変更機能の入力仕様 |
| `admin-role-change.expected.md` | 期待される出力の anchor |

### JSON形式

| file | purpose |
|---|---|
| `order-cancel.input.json` | feature_spec 形式の入力 |
| `order-cancel.expected.json` | 各 artifact の期待値 anchor |

## 使い方

### Forward-test 実行

1. Skill に input を渡す:
   ```
   Use $manual-bb-test-harness at ./skills/manual-bb-test-harness
   to create a manual black-box test design for ./goldens/order-cancel.input.md.
   ```

2. 出力を `expected.md` の anchor と比較
3. `docs/evaluation-rubric.md` で採点
4. Notion に結果を記録

### Golden 追加時のルール

1. input.md: 仕様、AC、業務ルール、変更点、環境を含める
2. expected.md: 期待する観点、リスク、ケース、gate 判断の anchor を含める
3. 厳密一致ではなく「含むべき内容」を定義する
4. JSON 形式は optional（機械連携が必要な場合のみ）

## 注意事項

- golden は「正解」ではなく「review anchor」
- 出力が golden と完全一致しなくても、rubric で高得点なら pass
- Skill 改善後に golden を更新することもある