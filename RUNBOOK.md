---
intent_id: INT-MBB-001
owner: manual-bb-test-harness
release_version: 2.0.0
test_count: 726
knowledge_map: 33 nodes, 45 edges, 33 capsules
next_review_due: 2026-10-11
status: active
last_reviewed_at: 2026-05-16
---

# Runbook

## Environments

- Local: repo 内で Skill / schema / script を編集して検証する
- CI: `.github/workflows/validate.yml` で repo 構造と Skill を検証する
- Consumer: Codex Skill として利用し、Markdown または JSON artifact を生成する

## Execute

### 1. Skill 出力を確認する

```powershell
Get-Content .\skills\manual-bb-test-harness\SKILL.md
Get-Content .\goldens\order-cancel.input.md
Get-Content .\goldens\order-cancel.expected.md
Get-Content .\docs\evaluation-rubric.md
```

mobile 対象の確認では次も読む。

```powershell
Get-Content .\skills\manual-bb-test-harness\references\platform-pack-mobile.md
Get-Content .\goldens\mobile-session-resume.input.md
Get-Content .\goldens\mobile-session-resume.expected.md
```

### 2. artifact 契約を変えたとき

1. `skills/manual-bb-test-harness/references/artifact-contract.md` を更新する。
2. 対応する `schemas/*.schema.json` を更新する。
3. `examples/artifacts/*.json` を更新する。
4. 出力品質が変わる場合は `goldens/` と `docs/evaluation-rubric.md` を更新する。

### 3. 仕様取り込みを変えたとき

```powershell
uv run pytest tests\test_spec_ingest.py
uv run python .\scripts\spec-ingest.py --source markdown --input .\goldens\order-cancel.input.md --output .\exports\order-cancel.feature_spec.json
```

### 4. repo 全体を検証する

```powershell
uv run pytest
uv run python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness
.\scripts\validate-skill.ps1
```

### 5. 変更単位を記録する

1. `docs/tasks/TASK_TEMPLATE.md` から task seed を作る。
2. 検収時に `docs/acceptance/ACCEPTANCE_TEMPLATE.md` から acceptance record を作る。
3. release readiness を残す場合は、必要に応じて `docs/release-review-YYYYMMDD.md` を追加する。

### 6. CLI で import/export/run を実行する

```powershell
# Import dry-run (token 不要)
uv run bb-harness import testrail --project 12 --run 1234 --output tmp-import --dry-run
uv run bb-harness import xray --exec TEST-1 --output tmp-import --dry-run

# Import 実行 (環境変数必須)
uv run bb-harness import testrail --project 12 --run 1234 --output execution_evidence/
uv run bb-harness import xray --exec PROJ-TE-123 --output execution_evidence/

# Export dry-run (token 不要)
uv run bb-harness --dry-run export notion --score 90 --status pass --db dummy_db

# Export 実行 (環境変数必須)
uv run bb-harness export notion --input report.json --db DATABASE_ID

# Forward-test (Skill 評価)
uv run bb-harness run forward-test --input goldens/order-cancel.input.md

# 詳細出力
uv run bb-harness --verbose validate
uv run bb-harness --verbose ingest --source markdown --input spec.md --output feature.json
uv run bb-harness --verbose gate --input artifacts --output gate.json
```

## Confirm

- `README.md`、`HUB.codex.md`、`BLUEPRINT.md`、`RUNBOOK.md`、`GUARDRAILS.md`、`EVALUATION.md` の役割が重複しすぎていない。
- task seed と acceptance record が相互参照できる。
- Skill の振る舞い変更が schema / example / golden / rubric に追随している。
- mobile 対象では `mobile_contexts` と `platform_matrix` が artifact と docs に反映されている。
- `uv run pytest` と Skill validator が通る。

## Rollback / Retry

- schema 変更で既存 example が通らない場合は、先に契約差分と example の期待値を見直す。
- golden 更新が必要な場合は、期待 anchor の意味を維持したまま更新する。
- validation が環境依存で失敗した場合は、Windows では `python` より `uv run python` を優先する。

## Failure Triage

失敗時は、先に「どの層で失敗しているか」を切り分ける。最初から全ログを追わず、下の順で最小再現コマンドを実行する。

### 1. 環境・依存関係

症状:

- `uv` が見つからない。
- import error が出る。
- `bb-harness` コマンドが見つからない。

確認:

```powershell
uv --version
uv sync
uv run python --version
uv run bb-harness --help
```

見方:

- `uv --version` が失敗する場合は、まず uv の導入問題。
- `uv sync` が失敗する場合は、`pyproject.toml` / `uv.lock` / ネットワークを確認する。
- `uv run bb-harness --help` が失敗する場合は、package entry point または editable install 周辺を見る。

### 2. CLI 引数・入力ファイル

症状:

- `Error: --input required` などの引数エラー。
- `Cannot read ...` が出る。
- 生成ファイルが見つからない。

確認:

```powershell
uv run bb-harness ingest --source markdown --input .\goldens\order-cancel.input.md --output .\tmp-triage.feature_spec.json
uv run python .\scripts\validate-artifact.py --artifact .\tmp-triage.feature_spec.json --type feature_spec --strict
```

見方:

- `--input` は既存ファイルを指定する。
- `--output` の親ディレクトリがない場合、CLI が作成できるかを確認する。
- 生成 JSON が invalid の場合は、schema と生成処理の契約差分を見る。

### 3. Schema / Artifact 契約

症状:

- `Additional properties are not allowed`。
- `required property ... missing`。
- `validate-artifact --all --strict` が失敗する。

確認:

```powershell
uv run python .\scripts\validate-artifact.py --all examples\artifacts --strict
```

見方:

- `Additional properties` は artifact に新しい field を足したが schema が追随していない可能性が高い。
- `required ... missing` は schema が期待する必須 field を example / generator が出していない。
- 契約変更時は `schemas/`、`examples/artifacts/`、`skills/manual-bb-test-harness/references/artifact-contract.md` を同時に見る。

### 4. Spec 品質

症状:

- `validate-spec --all` が FAIL。
- requirement / acceptance criteria が検出されない。

確認:

```powershell
uv run python .\scripts\validate-spec.py --all
uv run python .\scripts\validate-spec.py --input .\docs\specs\spec-02-cli-integration.md
```

見方:

- 見出し、requirements table、acceptance checklist の形式が validator の期待とずれていないかを見る。
- 仕様ファイルを変えた場合は、品質スコアだけでなく FAIL 理由を acceptance record に残す。

### 5. Skill 構造

症状:

- Skill validator が失敗する。
- frontmatter / required reference / JSON syntax のエラーが出る。

確認:

```powershell
uv run python .\scripts\quick-validate-skill.py .\skills\manual-bb-test-harness --debug
.\scripts\validate-skill.ps1 -Debug
```

見方:

- frontmatter エラーは `skills/manual-bb-test-harness/SKILL.md` の先頭 YAML を見る。
- required reference エラーは `skills/manual-bb-test-harness/references/` の欠落を確認する。
- placeholder / mojibake エラーは release 前に必ず解消する。

### 6. 外部サービス連携

症状:

- TestRail / Xray / Notion / Jira / Confluence の本実行だけ失敗する。
- dry-run は通るが API 実行が失敗する。

確認:

```powershell
uv run bb-harness import testrail --project 12 --run 1234 --output tmp-import --dry-run
uv run bb-harness import xray --exec TEST-1 --output tmp-import --dry-run
uv run bb-harness --dry-run export notion --score 90 --status pass --db dummy_db
```

見方:

- dry-run が通るなら CLI と artifact 生成は概ね正常。本実行の secret / URL / 権限を疑う。
- Secret 名はこの Runbook の「Secret 境界」を見る。
- Secret はログ、artifact、git diff に残さない。

### 7. Release / 検収

症状:

- 個別テストは通るが、release bundle dry-run が失敗する。
- README 参照、schema、golden、UTF-8 のいずれかで落ちる。

確認:

```powershell
uv run python .\scripts\validate-release-bundle.py --dry-run
uv run pytest
uv run ruff check .
```

見方:

- bundle エラーは配布物に含めるべきファイルの欠落として扱う。
- pytest / ruff が同時に落ちる場合は、release bundle より先にコード品質を戻す。
- 検収時は `docs/acceptance/` と `docs/release-review-YYYYMMDD.md` に実行コマンドと結果を残す。

## Security / Dependency

### uv.lock 再現性確認

```powershell
uv lock --check
```

結果: **Resolved 30 packages** (再現性確認 OK)

### 依存関係 Audit

現在の依存関係一覧:

| Package | Version | 用途 |
|---|---|---|
| pytest | 9.0.3 | テスト実行 |
| pytest-cov | 7.1.0 | Coverage測定 |
| ruff | 0.15.13 | Lint |
| jsonschema | 4.26.0 | Schema検証 |
| pyyaml | 6.0.3 | YAML解析 |

Audit 方法:
```powershell
# pip-audit が利用可能な場合
pip-audit

# または pyproject.toml 依存関係の確認
uv pip list
```

### GitHub Actions Action Version 方針

`.github/workflows/validate.yml` で pinned version を使用:
- `actions/checkout@v5`
- `actions/setup-python@v6`
- `codecov/codecov-action@v5`

方針: major version pinning を採用。月次で version 更新を確認。

### Secret 境界

| 命令 | Dry-run | 本実行 (Secret必須) |
|---|---|---|
| `validate` | 不要 | 不要 |
| `ingest` (markdown) | 不要 | 不要 |
| `ingest` (confluence/jira) | `--url`/--issue`のみ | `CONFLUENCE_API_KEY` / `JIRA_API_KEY` |
| `import testrail` | `--dry-run` | `TESTRAIL_URL/USER/API_KEY` |
| `import xray` | `--dry-run` | `JIRA_URL/USER/API_KEY` |
| `export notion` | `--dry-run` | `NOTION_API_KEY` |
| `gate` | 不要 | 不要 |
| `heatmap` | 不要 | 不要 |

### 本実行の手順

```powershell
# 1. 環境変数設定 (PowerShell)
$env:TESTRAIL_URL = "https://example.testrail.io"
$env:TESTRAIL_USER = "user@example.com"
$env:TESTRAIL_API_KEY = "api_key_here"

# 2. 本実行
uv run bb-harness import testrail --project 12 --run 1234 --output execution_evidence/
```

**重要**: Secret は `.env` ファイルや CI secrets に保存し、repo に commit しない。

## Gate 2.0 Operation

1. execution evidenceの`feature_id / build_id / timestamp`と、`tc_id`または`charter_id`の一方を確認する。
2. 対象buildと一致する`automation_evidence`を用意する。
3. waiverが必要なら、承認済み`waiver_set`へowner、期限、containment、rollbackを明記する。Gateはwaiverを自動生成しない。
4. `bb-harness gate --input <artifact-dir> --build-id <build>`を実行する。
5. `gate_decision`の`evidence_summary / waivers / unmet_conditions`をrelease evidenceへ保存する。

P0非pass、open blocker/critical/high defect、未解決critical assumptionはwaiverできません。同一case/buildに同時刻の証跡が複数ある場合は入力を修正し、任意に選択しないでください。 automation証跡不足/閾値未達もwaiverできず、P1/mandatory observationのwaiverは未達からtraceできるrisk IDを全て覆う必要があります。

## Release 2.0 Validation

```powershell
uv run ruff check src scripts tests tools
uv run pytest --durations=20
uv run python tools/ci/check_workflow_cookbook_freshness.py --repo . --strict
uv run python tools/ci/package_smoke.py
uv run python scripts/validate-release-bundle.py --dry-run --package-smoke
```

Actionは完全なcommit SHAへ固定し、Dependabotで更新します。version tagだけへのpinへ戻してはいけません。
