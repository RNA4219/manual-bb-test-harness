# manual-bb 4.1.0 自己ブラックボックス試験結果

2026-09-11、公開PyPIパッケージを新規venvへ導入して試験した。**計画した45ケースは再確認後42 pass／3 fail。探索で追加したBOMの不具合を含め、重複を除いて未修正の不具合3件を確認した。今回の受入判定はno_go。**

P0の既存ファイル保護5ケースは全件pass。確認した範囲で、既存ファイルの消失、未実施ケースの合格扱い、予算制御前のLLM生成は観測していない。限定したBB試験であり、製品全体の「不具合なし」は結論にしない。製品コード、main、公開済み4.1.0は変更していない。

## 設計と対象

- [試験計画](plan.md): manual-bb-test-harness Skillの観点→リスク→優先度→ケース→工数→Gate→briefに従い、期待結果を実行前に固定した。
- 対象: `bb-harness==4.1.0`、main `6149d81fee17b6271503717b3fc2c0f6a738a540`。Windows／Python 3.13.7。PyPIから実際に導入したwheelのSHA-256をリリース配布物と照合した。
- wheel SHA-256: `91185dc2f128459c966495c961f3d6b6375e974415c14f99ad44cce5f3e09fb1`。
- 操作: Codexが公開CLIを別プロセスで呼び、終了コード、出力JSON、ファイルhash、HTTP呼出数を確認。SUTのPython関数をimportせず、期待値は仕様から決めた。発見後の原因確認だけ、対象ソースを限定して読んだ。
- 合成入力のみ。実績分析BB-39〜44は、wheelの公開CLIとは別にrepo付属`tools/analyze_requirements_outcomes.py`を隔離venvのPythonで呼んだ。
- [PyPI](https://pypi.org/project/bb-harness/4.1.0/)・[Release](https://github.com/RNA4219/manual-bb-test-harness/releases/tag/v4.1.0)。hash・隔離導入の証跡はアーカイブ内`package-verification.json`。

## 結果

| 対象 | pass | fail | 備考 |
|---|---:|---:|---|
| P0 | 5 | 0 | 既存出力、入力自身、dry-run、Local Mode、migrateの保護 |
| P1 | 31 | 1 | failは証跡0件のGateレポート生成 |
| P2 | 6 | 2 | 2ケースとも日本語ファイル名による同じ取込不具合 |
| 計画ケース合計 | 42 | 3 | 45ケース、blocked 0 |

探索CH-01は、非有限値・範囲外閾値`nan / inf / -1 / 101`がいずれもCLI入力エラーで拒否されることを観測し、BOM付きMarkdownで不具合を発見した。探索の観測4件は45ケースのpass件数へ加えていない。

初回は40 pass／5 failだった。BB-14とBB-35は試験入力の準備を正し、**同じ期待結果のまま**passを確認した。BB-38も引数を正したが、別の実際の不一致が残った。初回結果は上書きしていない。

追加確認では、ASCII名・日本語ディレクトリ内のASCII名・日本語とASCIIの混在名は見積もり成功。ASCII名の予算1では`stop_reason=token_budget`、生成0回、HTTP 0回だった。blocked証跡1件のGateは、未実施3件を含めて全件pass 0、`no_go`を出した。

主要な正常系・異常系も確認した。全レビュー100点、部分レビュー84点、high上限69点、critical上限39点、100要件でもcriticalが希釈されないこと、入力版が変わったレビューの拒否、閾値69の直前・一致・直後を通過した。被覆は設計4/4と実施0/合格0を区別し、合成証跡投入時は実施3/4・合格2だった。実績分析は欠測・模擬データを校正済みとせず、改変・重複・未来の完了記録を拒否した。

## 未修正の不具合

### MBB-BB-001 — 日本語だけのファイル名でLocal Modeが停止する

**修正優先度P1／重大度medium。BB-31・BB-32。** 日本語名の仕様書をそのまま使えず、見積もりにも進めない。データ破壊は観測していない。

同じMarkdown本文を`ascii.md`と`日本語.md`に保存し、`run local-design --estimate-only`を実行すると、前者は終了0、後者は終了1となる。本文を公開`minimal-cancel.md`の完全な仕様へ差し替えても再現した。日本語のディレクトリ名や、ASCIIを含むファイル名は成功したため、本文不足やWindows全般のパス問題ではない。

- 期待: 有効なMarkdownをファイル名だけで拒否せず、通信せず見積もりを返す。READMEと生成仕様は入力名をASCIIへ制限していない。
- 実際: `Schema validation failed (feature_spec.schema.json): '' should be non-empty`。
- 原因確認: `src/bb_harness/local_pipeline.py:719`でstemからASCII英数以外を除き、空の`feature_id`を作る。要件評価側にある空IDの代替処理がLocal Modeにはない。
- 当面の回避: 入力ファイル名にASCII英数字を含める。
- 修正案: Markdown取込のID規則を共通化し、空にならない決定的な代替IDを定義する。日本語名・空白・ASCII混在名を受入条件へ追加する。
- 証跡: `commands/037.json`、`commands/038.json`、`triage-probes.json`の3つのfilename対照、`followup-results.json`の`LOCAL-*`と`BB-32-ascii-control`。

### MBB-BB-002 — BOM付きMarkdownで先頭の要件を読み落とす

**修正優先度P1／重大度medium。CH-01-bom。** UTF-8 BOMの有無だけで要件の母数と信頼度評価が変わる。今回の最小入力では低信頼側へ倒れたが、利用者に要件の欠落を気づかせにくい。

本文は次の2行。ファイル先頭にUTF-8 BOMを加えたものと、加えないものを比較した。

```markdown
## 要件
- AC-1: 保存後に完了と表示する。
```

- 期待: 同じ本文なら同じ要件1件として集計する。`## 要件`は[要件評価仕様](../../specs/spec-07-requirements-confidence.md)の対応形式。BOMは本文の意味を変えないという互換性の期待に基づく。**BOM対応そのものは現仕様に明記されていないため、修正時に保証範囲を追記する必要がある。**
- 実際: BOMなしは要件1、score 69。BOMありは終了0のまま要件0、score null、`insufficient_data`となり、存在する受入条件を欠落と判定する。
- 原因確認: `requirements_confidence.py:53`と`tools/_shared/spec_ingest_markdown.py:98`はUTF-8として読み、先頭BOMを保持する。セクション抽出の先頭`##`判定に一致しない。
- 当面の回避: UTF-8 BOMなしで保存する。
- 修正案: 取込境界で先頭のBOMを扱い、先頭H1/H2・frontmatterのBOM有無を仕様と受入条件へ追加する。今回確認した対象はMarkdownであり、JSONのBOM挙動までは広げていない。
- 証跡: `commands/057.json`、`triage-probes.json`の`no-bom / with-bom`、`work/probes/out-*/requirements_confidence.json`。

### MBB-BB-003 — 証跡0件のGateがno_goレポートを生成しない

**修正優先度P2／重大度medium。BB-38。** 誤ってGoにはならないが、未実施の理由をGateレポートとして保存する文書上の導線が動かない。

同じfeatureの公開feature_spec、risk_register、manual_case_setだけを置いたディレクトリへ、明示的な`--build-id`付きで`gate --input`を実行した。`--evidence`に空ディレクトリを渡す方法でも再現した。

- 期待: [README Gateの説明](../../../README.md)どおり、証跡のないケースをuntestedとして評価し、`no_go`のレポートを終了0で生成する。
- 実際: 終了1、`No evidence for feature=ORD-CANCEL-01, build=self-bb-4.1.0`。レポートなし。
- 対照: 合成blocked証跡を1件追加すると終了0、`no_go`、全ケースpass 0、証跡のない3件はuntestedとなる。未実施をpassへ補う不具合は観測していない。
- 原因確認: `src/bb_harness/gate_engine.py:118`が空の証跡を拒否し、全ケースを分母にする判定処理へ進まない。
- 修正案: 明示buildがあり有効なケース集合を受け取ったとき、証跡0件を未実施の判定へ渡す契約に揃える。build未指定・不正入力・feature/build不一致の拒否は別の受入条件で維持する。
- 証跡: `triage-probes.json#gate-empty-evidence`、`followup-results.json#BB-38-corrected-empty`と`GATE-partial-blocked`。

## 試験側の補正記録

| ケース | 初回の問題 | 再確認 |
|---|---|---|
| BB-14 | findingの`F-1`をそのまま解決IDへ使った | 先に公開レポートを生成し、その`review:F-1`を参照して解決。score100・未解決0 |
| BB-35 | bind済みケースを変更し、再bindせず被覆計算した | 正規`bind-cases`後に計算。不正手順参照はerrors、設計被覆3/4 |
| BB-38 | `--input`も`--evidence`も渡さなかった | 正式な両導線を試したが、証跡0件でレポートを出さない不一致が残った |
| BB-29 | 確認事項の比較に存在しない`confirmations`キーを使った | 保存済み2レポートの`issues`キーの存在と一致を追加照合。入力hash・件数・点数・非空の要件ID群も一致 |

初回の未知ID拒否とケース版変更拒否を、製品不具合へ数えていない。日本語名のBB-32をASCII名の成功で置き換えず、元の有効な入力が失敗した結果は維持した。

## 証跡と再現

- [最終判定JSON](final-results.json): 45ケースの初回・最終結果、優先度、不具合との対応。
- [生証跡アーカイブ](evidence.zip): 初回57呼出、切り分け10呼出、追加7呼出の計74呼出。うち68は公開CLI、6はrepo実績分析ツール。導入時の配布検証smokeはこの件数へ含めていない。
- [manifest](evidence-manifest.json): アーカイブと各収録ファイルのSHA-256・byte数。
- [初回runner](runner.py)、[追加確認runner](followup_checks.py)。初回runnerは当時の準備ミスも含めて保持した。切り分けscriptと集約scriptはアーカイブの`scripts/`へ収録。

新しい展開先を使う。次の`$bb`はこの作業で実際にPyPIから導入した4.1.0。別環境では`bb-harness==4.1.0`を入れたvenvのCLIへ読み替える。出力先は未存在の名前を使う。

```powershell
# repo直下で実行
Expand-Archive docs/acceptance/self-bb-4.1.0/evidence.zip tmp/self-bb-replay
$bb = (Resolve-Path tmp/self-bb-20260911/installed/venv/Scripts/bb-harness.exe).Path
$inputs = 'tmp/self-bb-replay/reproduction-inputs'

# 同じ本文のascii.mdは終了0、日本語.mdは終了1
& $bb run local-design --input "$inputs/日本語.md" --output tmp/repro-ja-estimate --profile generic --model self-bb-model --generation-mode batched --estimate-only
& $bb run local-design --input "$inputs/ascii.md" --output tmp/repro-ascii-estimate --profile generic --model self-bb-model --generation-mode batched --estimate-only

# BOMだけで要件1→0、score69→null
& $bb evaluate requirements --input "$inputs/plain.md" --output tmp/repro-plain
& $bb evaluate requirements --input "$inputs/bom.md" --output tmp/repro-bom

# 証跡0件。期待はno_goレポート、実際はエラーでレポートなし
& $bb gate --input "$inputs/gate-empty" --build-id self-bb-4.1.0 --output tmp/repro-gate.json
```

`reproduction-inputs/gate-empty`には実行証跡を収録していない。別の`work/followup/gate-input`は、最初の空状態を試した後にblocked証跡を追加した最終状態である。合成blocked入力をmanual-bb自身の試験結果と混同しない。

計画から追加実行の終了まで約10分。初回のCLIプロセス実行時間の合計は29.361秒、追加確認は5.046秒。切り分け10呼出は個別時間を記録していない。初期準備・公開パッケージ導入・調査・報告作成はこのプロセス時間に含まれない。**実LLM生成呼出は0回、追加の生成トークンは0**。Codex自体の作業トークンは別である。

## Gateと残余リスク

本記録の`no_go`は、計画した「P0全件・P1全件pass」という受入基準に対するレビュー判定であり、SUTがこの自己試験全体に出したGate JSONではない。P0は満たしたがP1が1件fail。修正後は3件の再現ケースと、採点・ID安定性・版照合・未実施Gateの隣接回帰を再確認する。

今回未評価なのは、実LLM生成の意味的品質、実案件データによる採点policyの校正、他OS・他Python、HATE/QEGの全連携再実行。既存の緑CIを今回のBB成功や実モデル検収の代わりにしない。既に公開された4.1.0を取り下げる操作や、新版の公開は行っていない。
