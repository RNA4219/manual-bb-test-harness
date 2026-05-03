# SPEC: manual-bb-test-harness 改修仕様書

## 概要

本仕様書は `manual-bb-test-harness` リポジトリの品質改善（21件）を定義・記録する。

## 改修項目 (21件)

| Severity | Count | Status |
|---|---|---|
| Critical | 1 | OK |
| High | 5 | OK |
| Medium | 9 | OK |
| Low | 6 | OK |

詳細は CHANGELOG.md を参照。

## 検証

| Phase | Verification | Status |
|---|---|---|
| 1 | `pip install -e .` | OK |
| 2 | pytest >80% coverage | OK (95%) |
| 3 | tests pass | OK |
| 4 | CI 3OS×3Python | TODO (push後) |
| 5 | Schema validation | OK |
| 6 | Agent config | OK |

## Regression Prevention

```powershell
py scripts/quick-validate-skill.py skills/manual-bb-test-harness
pwsh -File ./scripts/validate-skill.ps1
py -m pytest tests/ -v
```

## Version

0.1.1 - Keep a Changelog形式, Semantic Versioning準拠