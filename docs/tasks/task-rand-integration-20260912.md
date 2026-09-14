# RanD成果物取り込みと追加探索への引き継ぎ

- 状態: accepted / 2026-09-12
- 受入記録: [AC-20260912-rand-integration](../acceptance/AC-20260912-rand-integration.md)
- 責務: manual-bb-test-harness側の連携機能。RanDはR&Dの収集・分析・要求候補生成と成果物契約を担う。
- 正本: 本書。操作手順はSkillのreferences/rand-integration.mdへ分離する。

## 公開CLI

`bb-harness import rand --input <RanD JSON> --output <new-directory> [--diff <requirements_diff.json>] [--feature-id <id>] [--title <title>] [--defects <defect_register.json>] [--dry-run]`

ローカルJSONを読む。対象URLへのアクセス、RanDのimport/起動、対象製品の操作は行わない。相対pathは現在の作業directory基準。UTF-8/BOM可、各入力上限16 MiB、重複JSONキー・非有限数・不正構造は拒否する。出力先は新規directoryだけ。dry-runは検証・正規化結果をJSONで返し、出力directoryを作らない。成功exit 0、入力/保存失敗exit 1、引数誤りexit 2。公開完了後のlock解放障害はstatus=degraded / exit 2で公開済み参照を保持する。成功とintakeの十分性を分離する。

## 入力互換

schema_version=2.0のrequirements_packet（R&D候補）、requirements_audit_packet、requirements_document（parser_version=1）、downstream_handoffのmanual_bb_test_harness節を受け付ける。type/idを必須にして未知・legacy型は説明付きで拒否する。bare配列やCLI結果ラッパーは対象外。候補のstatement、ID、criteria、evidence、confidence、bias、risk、gateなどの元payloadを保存する。

requirements_documentはID重複・content hash・source行範囲とURIを検証する。差分は同じnormalized documentの入力時だけ使用できる。current_ref/document_id/source hashの一致、追加/削除/変更/不変の集合、counts、変更後内容と現行要求、before/afterのhash、changed_fieldsとテスト候補の対象を検証する。差分だけから要求や仕様を復元しない。

## 正規化と十分性

- rand_intake（schema_version=2.0、adapter_version=1）を追加する。input snapshotとbyte SHA256、元のrequirement_id、原文、criteria、source_refs、元requirement、change分類を保持する。
- source_refsはmanual-bbのSourceRefへ変換する。原文URI・excerptと要求IDを残し、ACには要求ID＋AC内容に由来する安定IDを与える。参照先は開かない。
- 全現行要求を保持し、差分があればadded/modifiedを重点、unchangedを回帰確認候補、removedを廃止確認として別記する。依存関係は未確認と明示し、変更要求だけで検査完了とはしない。
- criteriaがある要求はfeature_specへ接続する。criteriaは原文のまま使い、欠損を補作しない。空文書/全件criteriaなしはblockedとしてrand_intakeと設計依頼文だけを保存し、schema不適合なfeature_specは出さない。
- 対象環境・役割・依存関係の確認が未完了のため、criteriaが揃っていてもdegradedから設計を開始する。一部criteria欠損はdegraded、欠損要求ごとに未解決のcritical assumptionをfeature_specへ付ける。役割・対象環境・状態・依存情報の補足を設計依頼に残す。
- R&D候補（requirements_packet / discovery handoff）のcriteriaは候補のまま保持し、採用/期待結果の確定が未確認であるcritical assumptionを付ける。上流Kano/go/confidenceをmanual-bbのGateや実行結果に転用しない。
- feature_idは明示値を優先し、省略時は文書系列/packet IDから安定生成する。revisionは入力byte hashに由来する。全snapshotと要求の紐付けはrand_intakeで追跡できる。

## 追加探索

出力test_design_prompt.mdから同梱Skillへ入り、観点→リスク→優先度→ケース→工数→Gate→briefの順に進む。境界値・同値クラス・条件組合せ・状態/履歴/再試行・関連機能への回帰を検討する。実際の根拠がないケースは探索charter/要確認として扱う。ケース数や優先度を取り込み時に捏造しない。

任意のdefect_registerはmanual-bb自身のschemaで検証し、feature_id一致とdefect_id一意性を要求する。build_idとconfirmation_run_idsを含む台帳をsnapshotのまま保持する。既知欠陥→確認テストと隣接条件→新しいexecution_evidence→台帳更新→Gate再評価をSkill手順にする。resolved以外をfollow_up_defect_idsに列挙し、resolvedも回帰の根拠として保持する。台帳を渡すだけではcaseと要求の関連を推測せず、未確認の紐付けを明示する。新規passや欠陥close、Gateは自動生成しない。

## 保存・配布

新規directoryへrand_intake.json、任意feature_spec.json、test_design_prompt.mdをまとめて公開する。全JSONをローカルschemaで検証してからstagingからrenameし、途中失敗では自身が作ったstagingだけを除去する。同じ出力先を使うこのimporterはlockで直列化する。既存ファイルや入力の上書きは拒否。外部プログラムによる保存先の同時変更は保証しない。

rootとpackageにrand_intake schemaを同梱し、既存validate-artifactの型推定・検証から読める。RanDへのPython依存は追加しない。Skill本文には短い入口だけを足し、reference、README、RUNBOOK、SPEC、CHANGELOG、goldenを同期する。

## 受入条件

| ID | 条件 |
| --- | --- |
| RI-01 | R&D候補・監査・文書・handoffを公開CLIで取り込める |
| RI-02 | 元要求ID・原文・AC・参照・上流評価を失わず、候補を承認済みにしない |
| RI-03 | 同じ文書のdiffを照合し、変更重点と全体回帰/廃止候補を保持する |
| RI-04 | 不正型・ID重複・未知version・hash/差分不整合・過大入力を拒否する |
| RI-05 | 空/criteria欠損をblocked/degradedにし、期待値・pass・Goを補作しない |
| RI-06 | 欠陥台帳のfeature整合とID一意性を確認し、履歴を保持して追加探索へ渡す |
| RI-07 | dry-run副作用なし・既存出力保護・保存失敗後始末を確認する |
| RI-08 | schema/example/golden/Skill/配布packageの導線と既存CLI互換が通る |
| RI-09 | 全pytest、Ruff、Skill/artifact/metadata検証とRanD実成果物のCLI試験を成功させる |
| RI-10 | RanD repoと入力が不変で、開始時のmanual-bb既存変更を保持する |