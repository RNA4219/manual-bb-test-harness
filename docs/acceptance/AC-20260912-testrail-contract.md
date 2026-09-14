---
acceptance_id: AC-20260912-testrail-contract
task_id: 20260912-testrail-contract
intent_id: INT-TESTRAIL-EVIDENCE
owner: Codex
status: verified
reviewed_at: 2026-09-12
reviewed_by: Codex
approval_type: null
release_approval_id: null
---

# TestRail 契約修正の検収記録

## Scope

- 対象: 追加レビュー R12・R13 のステータス変換、ページ応答、全ページ取得、取得失敗時の中断。
- 変更単位: [Task Seed](../tasks/task-testrail-contract-20260912.md)。実装は `src/bb_harness/tools/import_testrail.py`。
- その他のレビュー指摘および既存の未コミット変更は、今回の検収対象に含めない。

## Acceptance Criteria

- [x] 公式の標準 ID をテストベースにし、実装の対応表から期待値を生成しない。
- [x] Failed と defect_stub が取り込み後も保持される。
- [x] tests の全ページと results の最新1件を読め、旧配列応答とも互換性がある。
- [x] 不正な次ページや循環を拒否し、取得失敗時には証跡を書き出さない。
- [x] 2ページ目で失敗しても既存ファイルのバイト内容を維持する。

## Evidence

実行環境: Windows、Python 3.13.7、repo の `.venv`。外部 TestRail への接続は行わず、HTTP 応答を Mock で与えた。

| 順序 | テスト対象・操作 | 結果 |
|---|---|---|
| 1 | 製品コード未変更。既存の `test_import_status.py`、`test_import_testrail.py` の期待値を修正し、追加18件と実行 | 21 failed / 103 passed |
| 2 | 製品コード未変更。循環ページと2ページ目失敗の2件を追加して実行 | 2 failed / 18 deselected |
| 3 | TestRail importer を修正。上記3ファイルに `test_import_xray.py`、`test_gate_v2.py` を加えて実行 | 210 passed |
| 4 | 対象の Python 4ファイルに `ruff check` | PASS |
| 5 | Skill creator の `quick_validate.py`、repo の `quick-validate-skill.py`、`validate-skill.ps1` | 3件とも PASS |

関連テストのコマンド:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -o addopts= --tb=short tests/test_import_status.py tests/test_import_testrail.py tests/test_testrail_api_contract.py tests/test_import_xray.py tests/test_gate_v2.py
```

ログ: workspace の `tmp/manual-bb-test-first-20260912/red.log`、`green.log`、`full-suite.log`。順序2は担当者の実行結果として確認し、この記録に転記した。

仕様根拠と期待値は [追加テスト](../../tests/test_testrail_api_contract.py) と [インポート仕様](../specs/spec-04-test-result-import.md) に記載。
別担当による実装の読み取りレビューでも、今回の契約範囲に追加修正が必要な問題は見つからなかった。

## Verification Result

- 判定: 今回の修正範囲は PASS。リリース全体の承認を表すものではない。
- 全体の pytest は作業前と同じ `ModuleNotFoundError: _shared.io_common` により、`test_export.py` と `test_validate_artifact.py` の収集で停止。該当する既存変更には手を加えていない。
- 知識マップの strict freshness 検証には既存の日付不整合が残る。今回変更した CHANGELOG と import 仕様の capsule は内容と検証日を同期した。
- 他の ISTQB レビュー指摘は継続課題としてレビュー文書に保持する。
