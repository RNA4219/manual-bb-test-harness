# Changelog

## Unreleased

### Added

- RanD の要求候補・監査・文書・handoff を取り込む `import rand` を追加。差分・原文・上流判断・任意の欠陥台帳を保存し、feature spec と設計依頼文を生成する。
- 実行構成の計画と欠陥台帳を追加。ケースと構成の組で再実行を選び、未実行の必須構成・別環境の失敗・未解決欠陥の履歴を保持する。
- ID 付きの網羅対象、3 値境界値、test plan、チェックリスト、探索記録、multi-run 統合、品質特性のフィードバックを契約化。

### Changed

- 定義・実行証跡の case/spec/oracle revision と内容 hash を必須化し、照合する。旧入力は [artifact 契約](skills/manual-bb-test-harness/references/artifact-contract.md)に沿って移行する。
- 自動証跡に `test_suites` を必須化。失敗・中断・未実行・skip・0 件実行は No-Go とし、カバレッジだけの入力には実際の suite 結果の補完を求める。
- waiver に独立した承認者・承認日時・承認根拠を要求。自己承認・未来の承認・期限切れを拒否し、`accepted` の重大欠陥を未解決として扱う。
- README を概要・始め方・文書案内に整理。CLI の詳細と移行手順は RUNBOOK、変更内容は CHANGELOG、検証結果はレビュー・検収記録に集約。

### Fixed

- TestRail の標準 status ID `4=Retest` / `5=Failed` を修正。ページ応答と旧配列応答、全ページ取得、最新結果の抽出に対応し、取得失敗・不正応答・循環ページから不完全な証跡を出力しないようにした。
- TestRail/Xray で元ケース・feature ID と版・hash・oracle 参照を保持。Xray の最終期待結果と探索チャーターの往復を修正し、複数欠陥 ID も維持する。
- Gate の必須入力不足、空の受入条件、ID 重複、非有限数値を判定前に拒否。実績区分の二重集計を修正し、black-box 受入境界と P0 非該当の扱いを統一した。
- retired ケース対応を package と script の共通実装へ統合。欠陥の確認 run と解決時刻を照合し、履歴上の未解決欠陥が消える問題を修正した。
- Markdown の子見出し・繰り返し節・水平線前後・環境を保持し、受入条件なしの架空 AC 生成を廃止。単一トリガーの negative case、golden と Ready 契約の整合も修正した。

### 検証記録

- ISTQB 改修: 全 pytest 1002 件、coverage 88.22%、strict artifact 31 件、root/package schema 21 組を確認。実施条件と外部サービス未接続などの制約は [第2回レビュー](docs/istqb-review-round2-20260912.md)を参照。
- 2026-09-12 の RanD 連携検証: 全 pytest 976 件、連携専用 63 件、公開 CLI 12 ケース、wheel/sdist 隔離 smoke が成功。[受入記録](docs/acceptance/AC-20260912-rand-integration.md)に条件別証跡を保存。

## [4.1.1] - 2026-09-12

- CIとHATE/QEGへのcoverage判定を、行・分岐の合算値から実測分岐率へ訂正。全体85%・Gate専用90%を分岐の件数で検証し、行率・分岐率・合算値を別記する。旧合算値の収集証跡は分岐合格へ流用しない。
- Gateの入力欠落・feature不一致、生成時の根拠・工数・モバイル観点不足、API応答不正・通信設定の回帰テストを追加。
- 日本語だけのファイル名でLocal Modeの機能IDが空になる不具合を修正。既存IDを維持し、空の場合は安定した代替IDを使う。
- UTF-8 BOM付きMarkdownの先頭見出し・frontmatterを認識し、BOMだけで要件数や信頼度評価が変わる不具合を修正。
- buildを明示した証跡0件のGate入力を全件未実施として評価し、`no_go`レポートを生成。入力不正や別feature/buildの証跡は引き続き拒否する。

## [4.1.0] - 2026-09-11

- PyPI READMEの相対リンクを正本GitHubへの絶対URLに修正。
- batchedのリスク生成を観点単位に分割し、必須観点漏れ・対象外ID・件数上限を検証。JSON Schemaをモデルへの指示にも含め、状態式・有限パラメータ・被覆入力の説明を改善。
- 小規模の実LLMでケース・レビューまで生成完了。ただし決定表に不整合が残りdegraded。品質受入と削減率の立証は未達として実測を保存。
- PyPI公開後にAPIメタデータ・実ファイル・新規インストールとCLIを確認するread-only CIジョブを追加。限定retryと失敗証跡を保存。
- 要件信頼度と不具合・手戻りの分析用データ形式、snapshot hash検証、欠測除外、調整群と保留群の分離を追加。実案件データによる校正は未実施、既存policyとGateは維持。

## [4.0.1] - 2026-09-11

- PyPIが拒否する未登録classifierを除去。PyPAの分類辞書によるbuild・公開前検証を追加。
- mainの緑CIとGitHub ReleaseのSHA-256・メタデータ・ライセンス・隔離CLI smokeを確認し、Trusted Publishingで同じ配布物をPyPIへ公開する手順を追加。
- READMEにPyPIの導入方法を追加し、CLI・PowerShell validator・現行文書の版を同期。4.0.0のGitHub Releaseと既存のartifact契約・動作を保持。

## [4.0.0] - 2026-09-11

- artifact契約拡張をmajorとするrelease policyに従い、package・CLI・PowerShell validator・現行ドキュメントを4.0.0へ更新。
- 要確認件数・重大度・密度・レビュー済み率による要件定義信頼度評価とJSON／Markdownレポートを追加。入力hashと解決根拠を照合し、LLM呼出なしで再評価できる。
- compact生成を既定にし、通信しない見積もり、run単位のトークン予算、batched分割生成、出力上書き防止、設計状態、ケース・モデルと実行証跡の版照合を追加。
- 実LLMによるトークン削減率の比較とbatched全段完走は未達。制約と実測結果はspec-05／06の検収記録に保存。
- 実pytestの証跡を固定版HATEで正規化し、QEGのhash検証・実行対象照合・Gate判定へ渡すCIジョブを追加。全体85%・Gate90%を維持し、失敗時も証跡を保存する。CI範囲のgoと実LLM・手動受入・リリース承認を区別する。

- Deep Researchの拡張要件から、型付き技法モデル、technique_plan、独立したcoverage_report、非破壊migrateコマンドを追加。追加artifact契約は1.1.0、既存入力は互換維持。
- Domain/組み合わせ/状態経路/決定表/CRUD/scenario/checklistと、random・metamorphicの実施予算を検証。設計・実施・合格を分離し、Gateへshadow指標を追加。
- Local Modeの同名ケース削除、riskへの機械的接続、review時のケース消失を修正。生成来歴と入力・手順対応を保存し、必要なschema定義のみモデルへ送信。

- OpenAI互換のllama.cpp / LM Studioを明示的に選択するLocal Modeとして、`run local-design` と `generic` / `qwen36` profileを追加。
- LLMをcoverage・observation・risk候補・case候補の生成に限定し、schema repair、risk/effort算術、lint、Gateをhost側でfail closed化。
- Qwen向けセルフレビュー、loopback既定、secret/raw promptを残さないrun manifest、70点台受入計画を追加。
- Qwen3.6のthinking有効時にJSON contentが空になる実測結果を受け、qwen36 profileをthinking offへ固定し、段階生成とself-reviewで補強。

## [3.0.0] - タグ未発行

以下はmainへ反映済みの3.0.0準備履歴で、4.0.0にも含まれる。

- ライセンスをRNA Third-Party Service Attribution License 1.0へ変更し、第三者向け有償サービス利用を顧客向け帰属表示付きで許可。
- 帰属表示なしのホワイトラベル利用向けに、別途書面による商用ライセンス導線を追加。
- 過去のMIT版の権利を維持し、v2.0.0 / 2ee85a0e8a62fc423feed1a23e0fdc8f4fa69631を最後のMIT tag付きrelease、1d8619b2067421938d2474485dd36abcf86af634を最後にMITで公開されたcommitとして記録。
- wheel、sdist、release bundleへ必須ライセンス文書を同梱して検証するようpackaging checksを更新。
- package/release検証で、商用問い合わせ先プレースホルダーの残存とREADME・pyproject・package version定数の不一致を拒否。

## [2.0.0] - 2026-07-11

- Gate 2.0の入力artifactをpackage resource schemaで事前検証し、不正入力を終了コード1で拒否。
- P0非pass、automation不足、重大open defect、critical assumptionをwaiver不可の`no_go`へ固定。
- P1/mandatory observation/残余riskのwaiverをrisk traceability付きに限定し、適用waiverだけをgate decisionへ保存。
- wheel/sdist隔離smoke、全726テスト、coverage 86.40%、Workflow Cookbook 33 nodes / 45 edges / 33 capsulesを現状へ同期。


## [1.0.0] - 2026-05-30

- README を AI-first 入口へ再構成し、人間向け概要を `docs/human-readme.md` に分離。
- artifact 検証で `jsonschema` を標準依存にし、`examples/artifacts/` の全 JSON example が `validate-artifact --all --strict` で通るように整理。
- 検証記録を現状の `654 passed` に更新。
- mobile 対象向けに `mobile_contexts` と `platform_matrix` を追加し、iOS / Android の中断復帰、権限、通知入口、ネットワーク差分を扱う platform pack と golden を追加。
- workflow-cookbook 準拠の正本ドキュメントとして `HUB.codex.md`、`BLUEPRINT.md`、`RUNBOOK.md`、`GUARDRAILS.md`、`EVALUATION.md` を追加。
- `docs/tasks/` と `docs/acceptance/` を追加し、repo self-review と release readiness 記録を残せるようにした。
- 既存の spec-ingest / state-diagram / export 生成例と `uv.lock` を repo の追跡対象として整理し、README 群へ反映した。
- `spec-ingest.py` を Markdown / Confluence / Jira helper に分割し、大型モジュール指摘を解消。
- code-to-gate strict policy の findings を 0 件まで解消。
- release bundle dry-run validator を追加し、配布対象の schema / examples / goldens / README 参照を検証可能にした。
- README に 15分 Quick Start、RUNBOOK に Failure Triage を追加し、初回利用と失敗時切り分けを強化。
- 公開リポジトリ向けに `IPO` / `社内` / `company.*` などの非公開文脈に見える表現を除去。

### Added (PLAN 完了分)
- **F6: TestRail/Xray Import** (`scripts/import-testrail.py`, `scripts/import-xray.py`)
  - `--dry-run` で API token 未設定でも preview モードで成功。
  - `bb-harness import testrail/xray` CLI wrapper 経由で動作。
  - status/priority 変換テスト (`tests/test_import_status.py`, 50 tests)。
  - import 出力が `execution_evidence.schema.json` で検証可能。
- **F7: Forward Test CLI** (`src/bb_harness/commands/run.py`)
  - `bb-harness run forward-test --skill ... --input ...` で Skill 評価プロンプト出力。
- **Workflow Cookbook Tier 3 達成** (`docs/workflow-cookbook/`)
  - `index.json`: 28 nodes, 45 edges (知識マップ)
  - `hot.json`: 6 hot nodes, 7 quick paths
  - `caps/*.json`: 28 capsule files (全ドキュメント要約)
  - `README.md`: Workflow Cookbook 使用手順とスキーマ定義
  - `adoption-tiers.md`: Tier 0-3 の段階的導入フレームワーク
  - `README.md` に LLM-BOOTSTRAP ブロック追加 (AI エージェント向け効率的ナビゲーション)
  - Core Files テーブルに `docs/workflow-cookbook/` を追加
  - `tools/ci/check_workflow_cookbook_tier.py`: Tier チェックツール
  - `templates/tier1/`, `templates/tier2/`, `templates/tier3/`: テンプレート集
  - `docs/workflow-cookbook/` → `docs/workflow-cookbook/` にリネーム（workflow-cookbook 標準準拠）
  - `check_adoption_tier.py` → `check_workflow_cookbook_tier.py` にリネーム
- `--verbose` を全 subcommand (validate/ingest/gate/export/import/run/heatmap/state-diagram/regression-graph) に伝播。
- `execution_evidence.schema.json` に `timestamp` フィールド追加。
- `RUNBOOK.md` に import/export/run CLI の実行手順を追記。
- `tests/test_cli_dryrun.py` に import/export/run の CLI wrapper テストを追加。

Keep a Changelog形式, Semantic Versioning準拠。

## [0.2.0] - 2026-05-03

### Added (HIGH Impact Features)
- **F1: Spec Ingest Engine** (`scripts/spec-ingest.py`)
  - Markdown仕様からfeature_spec.json自動生成
  - YAML frontmatter + 構造化セクション解析
  - Confluence/Jira ingestion stub (API連携準備)
- **F2: Regression Graph Visualization** (`scripts/regression-graph.py`)
  - feature_spec間の依存関係可視化
  - GraphViz DOT出力 + D3.js HTML出力
  - changed_areas共有による影響範囲分析
- **F3: State Transition Diagram Generator** (`scripts/state-diagram.py`)
  - test_model.jsonからMermaid stateDiagram自動生成
  - valid/invalid transitions可視化
- **F4: TestRail/Xray Export**
  - `scripts/export-testrail.py`: CSV/JSON export (TestRail import対応)
  - `scripts/export-xray.py`: JSON export (Jira Xray import対応)
  - manual_case_set → TestRail/Xray形式変換

### Added (Schemas)
- `schemas/spec-source.schema.json`: 仕様入力schema
- `schemas/testrail-export.schema.json`: TestRail出力schema
- `schemas/xray-export.schema.json`: Xray出力schema

### Added (Examples)
- `docs/features/order-cancel-partial.md`: Markdown仕様例
- `examples/artifacts/order-cancel-partial.feature_spec.json`: Ingest出力例
- `examples/artifacts/*.states.mmd`: Mermaid diagram出力例
- `examples/regression-graph.dot/html`: 依存グラフ出力例
- `exports/testrail-order-cancel.csv`: TestRail export例
- `exports/xray-order-cancel.json`: Xray export例

### Tests
- Unit tests: 129 tests (from 67)[^1]
- Coverage: ~98%[^1]

## [0.1.1] - 2026-05-03 (Quality Improvement)

### Added
- SPEC.md: 改修仕様書
- Unit tests (tests/) - カバレッジ98%[^1]
- pyproject.toml: 依存関係設定
- Multi-platform CI (windows/ubuntu/macos, Python 3.10/3.11/3.12)
- Subdirectory README (schemas/, examples/, goldens/)
- Provider-agnostic agent config (agents/generic.yaml)
- `--version`, `--debug` flags
- `-SkillName` parameter (PowerShell)
- JSON golden examples
- Additional artifacts (manual_case_set, gate_decision)
- Schema descriptions

### Fixed
- Bare `Exception` catch → specific exceptions
- `$Matches` null check (PowerShell)
- Hardcoded skill name → configurable
- Error messages with path context
- Dynamic repo root detection
- TODO pattern explanation comments

## [0.1.0] - Initial Release

- Manual black-box test design skill
- JSON schemas, golden examples
- Validation scripts (Python/PowerShell)
- CI workflow, evaluation rubric
- Domain packs (EC, SaaS-RBAC)

[^1]: 当時の記録。現在のテスト数・カバレッジは異なる可能性がある。最新値は `uv run pytest` 実行で確認。

## 生成効率・証跡版（2026-09-10）

未被覆補完と差分レビューのcompactモードを既定化。事前見積もり・token予算・失敗を含むusage集計、ケース/モデルの版照合、非破壊bind-cases、実モデルのfull/compact比較を追加。仕様は[spec-05](docs/specs/spec-05-efficient-generation-evidence-revisions.md)。

## 分割生成・完了判定（2026-09-10）

batchedモードでモデル・ケース・レビューを分割。finish_reasonを確認し、未完了JSON応答を拒否する。出力先を新規ディレクトリに限定し、design_statusと終了コード2を追加。比較を実ファイルと被覆の再計算で検証し、--modesで対象を選択できるようにした。
# 要件定義の信頼度評価（2026-09-11）

`evaluate requirements`を追加。要確認の件数・重大度・密度・レビュー済み率を決定的に採点し、JSON／Markdownと未記入のレビュー雛形を出す。入力hash、引用可能な根拠、oracle、解決記録を検証し、重大未解決や未レビューで高信頼を誤表示しない。Ready／Gateは独立。[spec-07](docs/specs/spec-07-requirements-confidence.md)を参照。
