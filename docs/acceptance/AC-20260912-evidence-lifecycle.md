---
acceptance_id: AC-20260912-evidence-lifecycle
task_id: 20260912-evidence-lifecycle
intent_id: INT-EVIDENCE-LIFECYCLE
owner: Codex
status: verified
reviewed_at: 2026-09-12
reviewed_by: Codex
approval_type: null
release_approval_id: null
---

# 実行構成・欠陥状態・suite成否の検収記録

## 対象と結果

[Task Seed](../tasks/task-evidence-lifecycle-20260912.md)に基づき、R1・R2・R18の残りを修正した。今回の3項目はPASS。既知23項目中8項目を対応済み、15項目を継続課題として[レビュー](../istqb-review-round2-20260912.md)へ記録した。

- R1: case/charterと実行構成の組で再実行を選択する。計画した未実行構成を残し、全対象構成でpassしたcaseだけを成功扱いにする。ケース数を分母に保ちながら、構成別実績も出力する。
- R2: 最新case結果へ絞る前の全入力履歴と欠陥台帳を使い、IDごとの未解決状態を保持する。resolvedは解決時点の一意な確認run、時刻、報告対象case/構成と照合する。後続の成功で有効な解決を無効化せず、再オープンは保持する。
- R18: 自動証跡に必須test_suitesを追加。失敗・error・中断・未実行・skip・実行0件は全profileでNo-Go。件数の不整合や欠落は入力エラーとする。先行したNaN/Infinity拒否と合わせて対応済み。
- TestRail/Xrayでは受領した複数の欠陥IDを個別に残し、1件の解決が他の欠陥を消さないようにした。

実装の中心は[Gate](../../src/bb_harness/gate_engine.py)と[実行証跡の方針](../../src/bb_harness/evidence_policy.py)。root/packageのschema、公開CLI、validator、例、golden、運用文書を揃えた。

## 回帰テストと再現確認

テスト追加から着手した。初回の50テストは45 failed / 5 passedだったが、一部のテスト入力に観点IDの形式違反があり、追加したTestRailテストの呼び出しにも誤りがあった。これらを訂正し、初回の失敗件数をそのまま不具合の再現数として採用していない。

訂正後のテストを、改修前commit `1d8619b`のsrcを展開した隔離コピーでも実行した。対象26件はすべて意図した失敗。通常の自動証跡fixtureだけは、旧契約に合わせて新設test_suitesを省いている。baseline側のpackageが読み込まれたことを検査し、作業ツリーを巻き戻していない。

| 検証単位 | 結果 |
|---|---|
| 訂正版を改修前コードへ適用: 環境差、再実行後の未解決欠陥、suite失敗・実績不足 | 26 failed / 27 deselected |
| 呼び出し訂正後、importer変更前の欠陥ID保持 | 2 failed / 51 deselected |
| 解決履歴の追加回帰: 後続passとrun ID再利用 | 2 failed / 61 deselected |
| 改修後のGate・入力契約・import関連の中間検証 | 244 passed |
| 解決履歴修正後の新規契約とpackage整合性 | 84 passed |
| 最終の全体pytest | **876 passed**、62.31秒、exit 0 |

新規回帰は[63ケース](../../tests/test_gate_evidence_lifecycle.py)。既存のpackage整合性テストを3ケース拡張し、前回810件から合計66件増えた。正常系と不正入力を対にし、出力の上書き防止、構成参照、欠陥の時刻・確認範囲、重複・再オープン、waiverでsuite失敗を覆せないことを検証した。

ログは`Codex_dev/tmp/`内に保存した。

- `manual-bb-evidence-baseline-red.log`: 訂正版と改修前srcの比較。隔離コピーの場所も記載。
- `manual-bb-defect-import-red-corrected.log`: 正しい引数での欠陥ID欠落。
- `manual-bb-resolution-history-red.log`: 解決履歴の追加回帰。
- `manual-bb-evidence-lifecycle-green.log`: 関連244件。
- `manual-bb-evidence-contracts-final.log`: 新規契約とpackage整合性84件。
- `manual-bb-evidence-full-suite.log`: 最終876件。

初回の入力不備を含むログも保存したが、上記の訂正版による確認を検収根拠とする。

## その他の検証

Windows、Python 3.13.7、repoの`.venv`で実施。

| 検証 | 結果 |
|---|---|
| ruff全体 | PASS |
| examples/artifactsのstrict検証 | 20 valid / 0 invalid |
| 複合シナリオのstrict検証 | 8 valid / 0 invalid |
| Skill creator / repo Python / PowerShellのSkill検証 | 3件ともPASS |
| 仕様文書の構造検証 | 4 PASS / 0 FAIL |
| Workflow Cookbook | Tier 3、strict freshness PASS、欠落・古いcapsuleなし |
| wheel/sdistの隔離installとCLI smoke | 両配布形式でPASS |

配布smokeはネットワークを使わず既存uvキャッシュを使用した。外部SaaSへの書き込みは行っていない。配布ログは`manual-bb-evidence-package-smoke.log`、artifactログは`manual-bb-evidence-artifacts.log`と`manual-bb-lifecycle-example-validation.log`。

```powershell
.\.venv\Scripts\python.exe -m pytest -q -o addopts= --tb=short
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m bb_harness gate --input examples/evidence-lifecycle --output tmp/lifecycle.gate_decision.json
```

## 使用時の移行条件

- 複数構成の未実行まで判定する場合はexecution_configurationsを宣言する。旧入力では環境情報の組を保持するが、未提供の構成は推定しない。
- 旧automation_evidenceには実際のtest_suitesと出典を追加する。サンプルの架空suiteを実行証跡として転用しない。
- 欠陥履歴、解決台帳、確認証跡を保存して入力する。IDなしの旧stubはタイトルで台帳へ自動結合しないため、移行時に安定した欠陥IDを補う。
- importerは受領した実行結果を変換する。外部tracker全体の未解決欠陥や、提供されなかった過去の履歴を自動復元する機能は今回追加していない。

詳細は[artifact契約](../../skills/manual-bb-test-harness/references/artifact-contract.md#実行構成と欠陥履歴)を正本とする。[複合シナリオの確認項目](../../goldens/evidence-lifecycle.expected.md)では、Android再実行pass、iOS未実行、fixedのhigh欠陥、suite失敗が同時に保持されることを確認した。
