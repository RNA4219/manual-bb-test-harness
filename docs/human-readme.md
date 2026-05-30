# manual-bb-test-harness 人間向け概要

`manual-bb-test-harness` は、手動ブラックボックス前提のテスト設計を、根拠付き観点、リスク、手動ケース、工数、品質ゲート、Go/No-Go brief まで一気通貫で作る Codex Skill リポジトリです。

## 何をするものか

仕様、受入条件、変更点、不具合履歴、自動テスト証跡を入力にして、いきなり「それっぽいテストケース」を量産するのではなく、先に確認対象の広がりを整理します。そのうえで、根拠付き観点、リスク、手動ケース、探索チャーター、Gate 判定へ段階的につなぎます。

主な利用場面:

- QA / 開発者が手動ブラックボックスのテスト観点を洗い出す。
- リリース前に P0/P1 の手動確認範囲と残余リスクを整理する。
- 仕様不足、期待結果の根拠不足、権限や状態遷移の抜けを早めに見つける。
- Web に加えて iOS / Android アプリの中断復帰、権限、通知入口、ネットワーク差分を含む手動設計を行う。
- forward-test の結果を記録し、Skill の出力品質を継続的に改善する。

## クイックスタート

1. Skill の入口を読む。

```powershell
Get-Content .\skills\manual-bb-test-harness\SKILL.md
```

2. 仕様または golden input を渡して Skill を使う。

```text
Use $manual-bb-test-harness at ./skills/manual-bb-test-harness to create a manual black-box test design for ./goldens/order-cancel.input.md.
```

3. 出力を golden expected と rubric で確認する。

```powershell
Get-Content .\goldens\order-cancel.expected.md
Get-Content .\docs\evaluation-rubric.md
```

4. repo 側の構造を検証する。

```powershell
.\scripts\validate-skill.ps1
python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness
```

## 入力と出力

入力例:

- 仕様メモ
- Acceptance Criteria
- 業務ルール
- 変更箇所
- 既存の自動テスト証跡
- 既知不具合
- 対象環境

出力:

1. 根拠付き観点
2. リスク
3. 優先度
4. 手動テストケース
5. 工数
6. Gate 判定
7. Go/No-Go brief

## 用語

- coverage model: 何を確認すべきかを、フロー、状態、ルール、データ、権限、回帰影響に分けたもの。
- oracle: expected result の根拠。仕様、受入条件、業務ルールなど。
- artifact: Skill が段階ごとに作る構造化された成果物。
- Gate: リリースしてよいかを、テスト結果、欠陥状態、残余リスクから判断すること。
- golden: 出力品質を確認するための例。完全一致 snapshot ではなく review anchor として扱う。

## 入口

- AI 向け README: `README.md`
- Agent 向けハブ: `HUB.codex.md`
- 設計正本: `BLUEPRINT.md`
- 実行手順: `RUNBOOK.md`
- 運用原則: `GUARDRAILS.md`
- 検収基準: `EVALUATION.md`
- Skill 本体: `skills/manual-bb-test-harness/SKILL.md`
- 詳細参照: `skills/manual-bb-test-harness/references/`
- Golden examples: `goldens/`
- JSON Schema: `schemas/`
- Export examples: `exports/`

## 評価資材

`goldens/` は完全一致 snapshot ではなく、出力品質を見るための review anchors です。

- `goldens/order-cancel.input.md`
- `goldens/order-cancel.expected.md`
- `goldens/admin-role-change.input.md`
- `goldens/admin-role-change.expected.md`
- `goldens/mobile-session-resume.input.md`
- `goldens/mobile-session-resume.expected.md`
- `docs/release-review-20260516.md`

Forward test の投げ方は `skills/manual-bb-test-harness/references/forward-test.md` を参照してください。出力品質の採点は `docs/evaluation-rubric.md` を使います。
