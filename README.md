# manual-bb-test-harness

手動ブラックボックス前提のテスト設計を、根拠付き観点、リスク、手動ケース、工数、品質ゲート、Go/No-Go brief まで一気通貫で作る Codex Skill リポジトリです。

## 目的

このリポジトリの目的は、仕様や受入条件から「それっぽいテストケース」を直接作るのではなく、先に coverage model を作り、根拠付き観点、リスク、手動ケース、探索チャーター、Gate 判定へ段階的につなぐ Skill を育てることです。

主な利用場面:

- QA / 開発者が手動ブラックボックスのテスト観点を洗い出す。
- リリース前に P0/P1 の手動確認範囲と残余リスクを整理する。
- 仕様不足、oracle 不足、権限や状態遷移の抜けを早めに見つける。
- forward-test の結果を Notion に記録し、Skill の出力品質を継続的に改善する。

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

4. Notion に forward-test 結果を記録する。

```powershell
Get-Content .\docs\notion-report-guide.md
Get-Content .\docs\notion-forward-test-template.md
```

5. repo 側の構造を検証する。

```powershell
.\scripts\validate-skill.ps1
python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness
```

## 入口

- Skill 本体: `skills/manual-bb-test-harness/SKILL.md`
- 詳細参照: `skills/manual-bb-test-harness/references/`
- Golden examples: `goldens/`
- JSON Schema: `schemas/`
- Evaluation docs: `docs/evaluation-rubric.md`
- Improvement notes: `docs/improvement-notes.md`
- 原典調査: `docs/research/deep-research-report.md`

## 何をする Skill か

仕様、受入条件、変更点、不具合履歴、自動テスト証跡を入力にして、次の順で出力します。

1. 根拠付き観点
2. リスク
3. 優先度
4. 手動テストケース
5. 工数
6. Gate 判定
7. Go/No-Go brief

設計方針は、巨大な一枚岩エージェントではなく、短い責務と型付き artifact を JSON 契約でつなぐことです。手動 black-box を主軸にしつつ、gray/white 情報は補助証跡として扱います。

## インストール

Codex の skill installer から GitHub repo path を指定してインストールします。

```powershell
python scripts/install-skill-from-github.py --repo RNA4219/manual-bb-test-harness --path skills/manual-bb-test-harness
```

ローカルで試す場合は、`skills/manual-bb-test-harness` を `$CODEX_HOME/skills/manual-bb-test-harness` にコピーします。

## 検証

Skill Creator の validator を使います。

```powershell
$env:PYTHONUTF8='1'
uv run --with pyyaml python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" ".\skills\manual-bb-test-harness"
```

補助チェック:

```powershell
.\scripts\validate-skill.ps1
python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness
```

## 評価資材

`goldens/` は完全一致 snapshot ではなく、出力品質を見るための review anchors です。

- `goldens/order-cancel.input.md`
- `goldens/order-cancel.expected.md`
- `goldens/admin-role-change.input.md`
- `goldens/admin-role-change.expected.md`

Forward test の投げ方は `skills/manual-bb-test-harness/references/forward-test.md` を参照してください。

出力品質の採点は `docs/evaluation-rubric.md` を使います。forward-test の記録は Notion を主に使う想定で、`docs/notion-report-guide.md` と `docs/notion-forward-test-template.md` を参照します。`docs/forward-test-report-template.md` は Markdown fallback です。

## スキーマ

`schemas/` には artifact を機械検証したいときの JSON Schema を置いています。

- `feature_spec.schema.json`
- `test_model.schema.json`
- `manual_case_set.schema.json`
- `gate_decision.schema.json`
- `shared_defs.schema.json`

`examples/artifacts/` には schema 化した artifact の最小例を置いています。

## CI

`.github/workflows/validate.yml` は次を実行します。

- `python scripts/quick-validate-skill.py skills/manual-bb-test-harness`
- `pwsh ./scripts/validate-skill.ps1`

## 育て方

- `SKILL.md` は短い運用手順に保つ。
- 詳細な契約、方針、テンプレートは `references/` に置く。
- 失敗モードや domain pack は `references/` に追加し、必要なときだけ読めるようにする。
- 原典調査や長文メモは `docs/research/` に置き、Skill 本体へ直接詰め込まない。
- artifact contract を変える場合は `schemas/` と `examples/artifacts/` も一緒に更新する。
- 振る舞いが変わる場合は golden、Notion の forward-test 記録、必要なら repo 側テンプレートを更新する。
- 変更時は validator と `scripts/validate-skill.ps1` を通す。
