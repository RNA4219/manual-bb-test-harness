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

- 
## 15分 Quick Start (人間向け)

初めて触る利用者は、まずこの順で動かす。目的は「環境が作れる」「代表コマンドが通る」「失敗時の入口が分かる」を 15 分以内に確認すること。

### 0-3分: セットアップ

```powershell
uv sync
uv run bb-harness --help
```

期待結果:

- `uv sync` が依存関係を解決する。
- `bb-harness --help` に `validate / ingest / gate / export / import / run` が表示される。

### 3-8分: 最小検証

```powershell
uv run pytest tests\test_cli_unit.py tests\test_spec_ingest.py
uv run ruff check .
uv run python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness
```

期待結果:

- pytest が pass する。
- ruff が `All checks passed!` を返す。
- Skill validator が pass する。

### 8-12分: サンプル入出力を確認

```powershell
uv run bb-harness ingest --source markdown --input .\goldens\order-cancel.input.md --output .\tmp-onboarding.feature_spec.json
uv run python .\scripts\validate-artifact.py --artifact .\tmp-onboarding.feature_spec.json --type feature_spec --strict
uv run bb-harness run forward-test --input .\goldens\order-cancel.input.md
```

期待結果:

- `tmp-onboarding.feature_spec.json` が生成される。
- 生成 artifact が `feature_spec` として valid になる。
- forward-test が Skill 評価用プロンプトを出力する。

### 12-15分: 全体検証に進む

```powershell
uv run pytest
uv run python .\scripts\validate-artifact.py --all examples\artifacts --strict
uv run python .\scripts\validate-spec.py --all
uv run python .\scripts\validate-release-bundle.py --dry-run
```

期待結果:

- 全テストが pass する。
- artifact / spec / release bundle の検証が pass する。

失敗した場合は [RUNBOOK.md](RUNBOOK.md) の「Failure Triage」を見る。

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
