# RanD連携 受入記録

- 日付: 2026-09-12
- 判定: **機能受入pass（RI-01〜10）**
- 正本: [RanD連携仕様](../tasks/task-rand-integration-20260912.md)
- 操作: [SkillのRanD連携ガイド](../../skills/manual-bb-test-harness/references/rand-integration.md)
- 証跡: workspaceの`artifacts/manual-bb-rand-integration-20260912/`

## 結果

manual-bb側へ`bb-harness import rand`を追加した。RanDはR&D成果物の生成を担い、manual-bbが取り込み・観点展開・実行結果に基づく追加探索の入口を持つ。

要求候補、監査packet、正規化文書、downstream handoffに対応。入力snapshotとSHA256、元要求ID、原文・AC・根拠URI/証拠ID、上流のconfidence・bias・gateなどを保持する。文書diffは変更重点だけでなく未変更の回帰候補と削除要求を残し、任意の欠陥台帳は元buildと確認runを維持して次の設計へ渡す。

CLIはrand_intake、任意feature_spec、test_design_promptを生成する。Skillが観点→リスク→優先度→ケース→工数→Gate→briefへ進む。候補ACの無断確定、ACの補作、上流goの転記、case実行・欠陥closeの捏造は行わない。製品操作と修正を行う自動runnerは今回の範囲に含めない。

## 条件対応

| 条件 | 確認内容 | 証跡 | 結果 |
| --- | --- | --- | --- |
| RI-01 | 4種のRanD成果物、discovery/audit handoff | test_rand_import.py / BB-RI-01〜04 | pass |
| RI-02 | ID/原文/AC/根拠URL/上流判断の保存、候補の不確実性 | test_rand_import.py / BB-RI-01〜04 | pass |
| RI-03 | diffの整合、全体回帰と廃止確認 | test_rand_import.py / BB-RI-03 | pass |
| RI-04 | legacy/不正構造/重複/過大/hash不整合の拒否 | test_rand_import.py / BB-RI-07 | pass |
| RI-05 | empty/AC欠損、blocked/degraded、期待値未補作 | test_rand_import.py / BB-RI-08 | pass |
| RI-06 | 台帳feature/ID/確認run、未解決と履歴の保持 | test_rand_import.py / BB-RI-05〜06 | pass |
| RI-07 | dry-run、既存保護、保存失敗の後始末、公開後警告 | test_rand_import.py / BB-RI-09〜10 | pass |
| RI-08 | schema/example/Skill/知識map/配布形式の互換 | validators / package smoke / BB-RI-11の2件 | pass |
| RI-09 | 全体回帰、実成果物CLI、品質検証 | pytest-all-final.xml / blackbox-final/cases.json | pass |
| RI-10 | RanD不変、既存改修を保持した最終source確認 | before.json / source-before-final.json / provenance.json | pass |

## 実測

- 全pytest: **976 passed、失敗・skipなし**（Windows / Python 3.13.7、68.23秒）。今回の連携専用テストは63件。
- 公開CLI: **12ケース成功**。R&Dの実requirements_packet、実文書audit/handoff/diff、欠陥取り込み、拒否・dry-run・上書き保護、公開validatorを確認。
- 実文書diff: RanD要件書の**57要求**を保持し、変更FR-I01の**1件を重点**、未変更**56件を回帰候補**にした。
- Ruff: 全体pass。
- Skill: repo validator、system quick_validate、PowerShell validatorがpass。
- 公開artifact: **22 valid / 0 invalid**。知識mapは**34 nodes / 48 edges / 34 capsules**。
- wheelとsdistをrepo外の隔離環境へオフラインinstallし、既存CLIとRanD候補/文書差分のimportを確認。配布wheelのpackage source/schemaが全体テスト対象のsnapshotと一致した。
- coverage.pyの行・分岐を合わせた値: **88.54%**（基準85%以上）。行90.43%（3101/3429）、分岐83.49%（1072/1284）。
- 最終全体テストの開始・終了でsource/test/schema hashが一致。最終12ケースのCLI実行中もpackage sourceは不変。
- RanDの作業対象179ファイルは内容・集合とも開始時と一致し、変更していない。

[全体テスト](../../../../artifacts/manual-bb-rand-integration-20260912/pytest-all-final.log)、[CLIケース](../../../../artifacts/manual-bb-rand-integration-20260912/blackbox-final/cases.json)、[配布確認](../../../../artifacts/manual-bb-rand-integration-20260912/package-smoke-current.log)、[最終hash](../../../../artifacts/manual-bb-rand-integration-20260912/provenance.json)を保存した。

## 検証中の修正と既存差分

最初の差分テストではfixtureのbefore/currentとdiffが同じPython objectを共有し、diffだけを壊すつもりでcurrentも変更していた。独立copyへ修正し、期待する拒否条件を維持した。知識mapのquick pathに未登録nodeを置いた問題も修正し、登録済みSkill/referenceの経路へ揃えた。初期失敗のログは残している。

同じ作業ツリーには先行・並行したGate等の改修がある。既存差分を戻さずに連携を追記し、統合状態で上記検証を実施した。Gateのimport順についてはRuffの指摘に沿う整列だけを行った。連携の実装は最終全体テスト対象のsnapshotと一致する。検証後に別改修としてTestRail/Xrayのexport/import adapter等が更新されたため、検証対象の版と現在との差をpost-verification-changes.jsonへ記録した。今回の機能受入をこの別改修の検証済み扱いにはしない。別改修後にも連携専用63テストを再実行して成功した（pytest-rand-current.xml）。実測件数と受入リンクは検証後の文書整備として追記した。

取り込み結果のdegraded/blockedは設計入力の十分性で、取り込み処理の失敗や製品のrelease判断とは異なる。R&D候補の採用、対象環境、依存関係、既知欠陥とcaseの紐付けはSkill実行時に確認する。今回の受入は連携機能の確認であり、対象製品の手動試験実績やrelease Goを示さない。
