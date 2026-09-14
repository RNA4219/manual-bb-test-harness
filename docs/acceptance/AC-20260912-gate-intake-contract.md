---
acceptance_id: AC-20260912-gate-intake-contract
task_id: 20260912-gate-intake-contract
intent_id: INT-GATE-TEST-BASIS
owner: Codex
status: verified
reviewed_at: 2026-09-12
reviewed_by: Codex
approval_type: null
release_approval_id: null
---

# Gate・仕様取り込みの契約修正の検収記録

## 対象

[第2回レビュー](../istqb-review-round2-20260912.md)の R11・R16・R20、R18の非有限数値と、既存のretired変更のscript/package/schema不整合を修正した。変更単位は[Task Seed](../tasks/task-gate-intake-contract-20260912.md)。誤った期待値を先に直し、追加テストでも修正前の失敗を確認してから実装を変更した。

## 受入条件

- [x] feature/observationsの未提供、空の受入条件・観点を入力エラーとし、既存のGate出力を維持する。非空の全optional観点とは区別する。
- [x] manual case/charter間を含むID重複を拒否し、辞書への格納でケースを失わない。
- [x] NaN/Infinityをartifact検証・Gate入力で拒否する。基本検証へのフォールバックでも同じ制約を保つ。
- [x] pass/fail/skip/blocked/unknown/untestedを排他的に集計する。
- [x] retiredを手動実績の分母とP1失敗のwaiver対象から除外し、理由・移管先を出力する。active失敗の承認要求、自動証跡・欠陥・必須観点の確認は維持する。
- [x] MarkdownのAC配下の小見出し、繰り返し節、本文の水平線以降、Environmentsを保持する。ACなしでは取り込みを中断し、既存出力を上書きしない。
- [x] package側のexport/validatorへretiredの契約を統合し、scriptsをwrapperへ揃える。Gate 2.0のbuild/evidence/structured waiverの契約を保持する。
- [x] root/packageのschemaと、order-cancelの観点・Gate・goldenを整合させる。

## テスト先行の証跡

Windows、Python 3.13.7、repoの`.venv`で実行。以下の各redは、対象の製品実装を変える前の結果。件数は各実行単位であり、合算値ではない。

| 対象 | 期待値・テストを先に変更した結果 |
|---|---|
| 既存Gateテストの空観点を100%とする誤った期待値 | 1 failed / 43 passed |
| 必須入力・ID重複・排他集計・非有限数値の新規契約 | 24 failed / 16 passed |
| Markdown取り込みの誤ったplaceholder期待値と欠落の回帰 | 12 failed / 49 passed |
| retiredの既存テストをnative package側へ適用 | 対象10件が失敗 |
| package/artifact整合性の契約 | 14 failed / 3 passed |
| order-cancelの観点artifact | 対象1件が失敗 |
| 最終レビューで追加したretired/P1 waiverの分離 | 2 failed / 40 deselected |

retired/P1の回帰では、承認なしで不足riskにretiredのriskまで混入することと、active失敗だけを承認してもNo-Goになることを確認した。条件を1か所修正後、両方の期待値が通った。

## 修正後の検証

| 検証 | 結果 |
|---|---|
| Gate・入力契約の初回検証 | 84 passed |
| 仕様取り込み関連 | 61 passed |
| package/export/validator関連 | 94 passed |
| 追加waiver修正後のGate関連4ファイル | 149 passed |
| 最終の全体pytest | **810 passed**、61.60秒、exit 0 |
| ruff全体、追加waiver修正の対象ruff | PASS |
| example artifact strict検証 | 19 valid / 0 invalid |
| 仕様文書の構造検証 | 4 PASS / 0 FAIL |
| Skill creator・repo Python・PowerShellのSkill検証 | 3件ともPASS |
| Workflow Cookbook Tier・strict freshness | Tier 3、欠落・古いcapsuleなし |
| wheel/sdistをrepo外へ隔離installしたCLI smoke | 両配布形式でPASS |

配布smokeの後、最終レビューでwaiverの1条件を追加修正し、Gate149件と全体810件で確認した。実サービスへの書き込みは行っていない。

最終全体テスト:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -o addopts= --tb=short
```

ログはworkspaceの`tmp/manual-bb-gate-fix-20260912/`に保存した。

- `existing-tests-red.log`、`gate-core-green.log`
- `full-suite.log`: 修正途中の807 passed / 1 failed。残る失敗は知識マップの古い確認日。
- `full-suite-final.log`: 知識マップ修正後の808 passed。
- `retired-waiver-red.log`、`retired-waiver-green.log`
- `full-suite-retired-waiver-final.log`: 最終810 passed。
- `package-smoke.log`: wheel/sdistの成功結果。

新規Gate契約のredは`tmp/manual-bb-gate-review-red-20260912.log`。取り込み・packageのred/greenは担当者の実行結果を照合して本記録へ転記した。

## 整合性と残課題

以前の全体テスト収集エラー2件は、native packageへの統合とwrapper復元で解消した。知識マップは参照元と要約を照合し、今回確認した内容と確認日を同期した。README/hotの検証件数も最終結果へ揃えた。過去のリリース記録や[TestRail検収記録](AC-20260912-testrail-contract.md)の実行当時の結果は保持した。

order-cancelのgoldenは明示したfeature/observations/automationを入力し、waiverを渡さない条件でNo-Goになる。`--input`では既存waiverも自動検出するため、同じ実行条件として扱わない。retiredの移管先参照だけで必須観点を実施済みとは判定しない。

判定は今回の修正範囲でPASS。R18の自動テストsuite成否の契約、R14・R15・R17・R19・R21〜R23、第1回レビューの指摘は継続課題としてレビュー文書に保持する。
