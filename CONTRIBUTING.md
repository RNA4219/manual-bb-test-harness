# Contributing

IssueまたはPull Requestを歓迎します。変更前に対象仕様とartifact schemaを確認し、破壊的変更はissueで合意してください。

## 開発

```powershell
uv sync --extra dev
uv run ruff check src scripts tests tools
uv run pytest --durations=20
uv run python scripts/validate-artifact.py --all examples/artifacts --strict
uv run python scripts/validate-spec.py --all
```

package変更時は`uv run python tools/ci/package_smoke.py`も実行します。新しい挙動にはテストと文書を追加し、旧artifact互換を変更する場合はCHANGELOGへ明記してください。

commitやPull Requestには変更理由、検証コマンド、結果、残余riskを記載してください。
