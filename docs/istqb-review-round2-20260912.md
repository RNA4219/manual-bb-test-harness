manual-bb-test-harness 追加レビュー（2026-09-12・第2回）

対応状況（2026-09-12）:

- R12・R13: 誤った期待値を先に修正して失敗を確認した後、実装修正と関連210テストで検証した。[TestRail検収記録](acceptance/AC-20260912-testrail-contract.md)を参照。
- R11・R16・R20: 必須入力、Markdown取り込み、ID重複と排他集計をテスト先行で修正した。既存のretired対応とpackage/schemaの不整合も統合した。[Gate・取り込み検収記録](acceptance/AC-20260912-gate-intake-contract.md)を参照。
- R1・R2・R18: 構成別実績、欠陥ID付き台帳と確認証跡、必須suiteの成否を追加して修正した。先行したNaN/Infinity拒否と合わせてR18を対応済みとする。[実行証跡の検収記録](acceptance/AC-20260912-evidence-lifecycle.md)を参照。
- R14・R15・R17・R19・R21〜R23と第1回レビューR3〜R10もテスト先行で修正した。元ケースIDの往復、Xrayの最終期待結果、black-box受入境界、承認付きwaiver、単一トリガーnegative、golden整合、Ready契約、coverage母集団、3値境界値、testware identity、P0非該当、経験ベース技法、multi-run、test plan、品質特性feedbackを契約化した。
- R1〜R23はすべて対応済み。外部連携では元ケース／feature IDに加え、case・spec・oracleの版、case内容hash、oracle参照まで往復させ、実行statusに依存しないhashを採用した。Lunaが反例テストと最終レビューを監督し、DGXの独立チェックリストでID、境界値、black/white、waiver、状態矛盾を再確認した。
- 最終確認は全pytest 1002件、coverage 88.22%（基準85%）、Ruff、strict artifact 31件、root/package schema 21組、実Gate CLIと生成Gateのstrict検証がすべて成功した。実Gateの結果は、承認済みwaiverを保持する例どおりconditional_go。

以下は改修前の調査記録。記載の行番号と再現結果は調査時点のもの。

[第1回レビュー](istqb-review-20260912.md)のR1〜R10を踏まえ、Gate、外部ツール連携、仕様取り込み、goldenと評価記録を確認した。2つの独立レビューと、親担当によるGateの動作確認を実施。対象は同じHEAD `1d8619b` と既存の未コミット変更を含む作業ツリー。製品コードは変更していない。

追加で見つかった問題は、テストベースの欠落、証跡変換の誤り、情報不足を成功と扱う判定、評価用ケースの欠陥マスキングに集中している。比較基準は [ISTQB CTFL v4.0.1](https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf)。特にテストベースとテストウェアの追跡（1.4.4）、技法の適用（4.2）、テスト管理・構成管理・欠陥管理（5章）に関わる。具体的な優先度と改修案は本レビューの判断。

| ID | 優先度 | 追加確認した問題 | 確度 |
|---|---|---|---|
| R11 | 高 | 仕様・観点なし、観点実行率0%でもGo | CLI本体で確認 |
| R12 | 高 | TestRailのFailedをskipへ誤変換し欠陥を落とす | 公式定義・変換・Gate結合で確認 |
| R13 | 高 | TestRailの応答形式・ページング未対応と例外の握りつぶし | 公式定義・HTTP Mockで確認 |
| R14 | 高 | export/importで元のケースIDを失う | 往復変換で確認 |
| R15 | 中 | Xray出力で最終期待結果を最初の操作へ誤配置 | schema適合入力の変換で確認 |
| R16 | 高 | Markdown取り込みで例外・ルール・環境が消える | 複数入力で確認 |
| R17 | 高 | whiteの証跡だけで手動受入Go。分類にも混同がある | CLI本体・方針確認 |
| R18 | 高 | 自動テストの成否を表せず、非数値のcoverageも通る | schema・CLI本体で確認 |
| R19 | 中〜高 | リスク受容の承認根拠を保持・検証できない | schema・CLI本体で確認 |
| R20 | 高 | ケースID重複で別ケースが集計から消える | CLI本体で確認 |
| R21 | 高 | 拒否条件を重ねたケースが別ルールの欠陥を隠す | 仕様・ケースの論理確認 |
| R22 | 中〜高 | 異なる仕様・誤ったAC参照の評価資産がPASS扱い | 静的確認。第1回R3の具体的実害 |
| R23 | 中 | Ready契約の矛盾と重大未決事項を検証しない | validatorで確認 |

1. **R11：必須の判断材料が欠けた場合はGoを出さない。**

   `src/bb_harness/gate_engine.py:638`、691行以降ではfeatureとobservationsが任意。featureなしは263行以降で「critical assumptionなし」、observationsなしは299行以降で実行率0%となる。しかし346行以降で不足観点は空集合、403行以降でも不合格条件が作られず、他条件が充足すると `go` になる。

   CLI本体の `main` で `--feature` と `--observations` を省略し、exit=0、status=go、mandatory_observation_rate=0.0を確認した。第1回R3の参照整合性に加え、必要なartifact自体の欠落が判定を止めない問題。

   改修案：プロファイルごとに必要なartifactを宣言し、必須入力の欠落を入力エラーまたはNo-Goとして扱う。未提供・対象外・空集合を区別する。観点を提供した正常系と、省略・空・全optional・取得失敗を対にして検証する。

2. **R12：TestRailの標準ステータスIDが逆。**

   `src/bb_harness/tools/import_testrail.py:42` は4をfail、5をskipとする。標準は4がRetest、5がFailed。[TestRail公式Statuses](https://support.testrail.com/hc/en-us/articles/7077935129364-Statuses)

   status_id=5、defects=[BUG-1]を変換するとskipになり、fail時だけ生成するdefect_stubも落ちる。P0成功＋P2のこの失敗、leanプロファイル、他証跡充足という同じ入力で、現行対応では `go`、メモリ内で対応だけを訂正すると重大欠陥1件を検出して `no_go` となった。外部サービスでは実行していない。

   改修案：対応表と、それを逆のまま固定している仕様・テストを同時訂正する。カスタムステータスはget_statusesの定義に対応付ける。第1回R2と違い、再実行で消える前に最初の取り込み時点で失敗を失っている。

3. **R13：TestRailの現行応答形式を扱えず、結果取得失敗も隠す。**

   `import_testrail.py:78`、89行以降は応答を配列として扱う。公式のtests/resultsを包む応答形式でHTTP Mockを構成すると、get_tests側は文字列に対するget呼び出しでAttributeError、get_results側は `results[0]` でKeyErrorになった。ページングの次ページも取得しない。[TestRail公式Tests](https://support.testrail.com/hc/en-us/articles/7077990441108-Tests)、[公式Results](https://support.testrail.com/hc/en-us/articles/7077819312404-Results)

   さらに243行付近の結果取得は全例外を無視して空辞書を採用する。テスト一覧を取得できた状態で詳細取得だけを失敗させると、一覧上のpassを使った証跡とimported_count=1が返り、詳細の取得失敗が結果に残らない。

   改修案：対応バージョンの応答を正規化し、ページングと件数照合を行う。詳細取得失敗はunknown／部分取込として記録するか、完了扱いを拒否する。API仕様と同形のfixtureを使用する。

4. **R14：双方向連携のケースIDが安定していない。**

   `src/bb_harness/tools/export_testrail.py:49` 以降で元のtc_idを出力せず、idを列挙順の1、2、3…に置き換える。`import_testrail.py:112` は外部case_idからTC形式を新規合成する。TC-042の1件をexportすると元IDが消え、id=1を再importするとTC-001になる。元のTC-042へ結果を戻すと未実施のまま。

   Xrayも元のtc_id／charter IDをexportせず、import時にはJira test keyをtc_idとする。CLIにID対応表の指定経路がない。実際のサービスでの採番を再現した主張ではなく、外部採番と元IDを結ぶ契約がないことを確認したもの。

   改修案：feature＋case/charter IDと外部IDの対応を永続化する。不明・曖昧なIDは結果を割り当てない。並べ替え・別run・複数feature・charterを含む往復検証を追加する。oracle/source refsもexportで落ちるため、対応表から元の版を辿れるようにする。

5. **R15：ケース全体の期待結果をステップ別と決めつけている。**

   `src/bb_harness/tools/export_xray.py:64` 以降はstepsとexpected_resultsを配列位置で対応付ける。現行schemaは「各操作後または最後」の期待値を許しており、配列位置の対応は保証していない。

   schemaに適合する「詳細を開く→キャンセルを選ぶ→取消確定」の3手順と「注文が取消済みになる」という最終期待値1件を渡すと、詳細を開く操作に取消済みを要求し、取消確定の期待値は空になる。

   改修案：ステップ単位の期待値と全体の事後条件を分離する。対応指定がない場合は最終期待値を最後に確認するなど、変換規則を明示する。

6. **R16：仕様取り込みの段階で、網羅すべきテストベースを失う。**

   対象は `src/bb_harness/tools/_shared/spec_ingest_markdown.py:34` 以降、58行以降、73行以降、103行以降、141行以降。

   - Acceptance Criteria配下の小見出しExceptionsにあるACが、別セクションとして出力から消える。
   - 同名のBusiness Rulesセクションを複数置くと、前のルールが後のルールで上書きされる。
   - frontmatterのない本文に水平線 `---` が2本あると、2本目以前をfrontmatterとして捨てる。
   - 実在するmobile goldenのEnvironments節がdevicesへ正規化されず、対象のiOS/Android情報が消える。

   例外AC、同名BR、mobile環境の欠落には、それを示すassumptionも出なかった。これは後段の網羅率計算以前の情報欠損。

   ACが全く見つからない場合は、129行以降で `[NO ACCEPTANCE CRITERIA FOUND]` をACの代わりに入れ、highのassumptionを付ける。schemaはこれを受理する。この取り込み結果を、既に存在する同一featureのケースと成功証跡に組み合わせると、CLI本体で `go` になった。テストベース不足を承知した状態でも、critical以外のassumptionが判定を止めない。

   改修案：Markdownの階層を保持し、同じ意味の節を追記統合する。frontmatterは先頭だけに限定する。未採用節と取り込み件数をレポートし、AC/BR/環境の損失を確認する。AC未発見を正常なACとして数えず、テストベース不足として後段へ伝える。

7. **R17：手動black-box受入の境界と、技法の分類が一致していない。**

   `src/bb_harness/gate_engine.py:127` 以降はprimary_viewを結果集計に保持せず、whiteのケースもP0/P1実行率やblackの観点実行率に算入する。P0ケースをwhiteへ変えた入力でも、blackの受入観点が100%となり `go`。Skillの「gray/whiteは補助」という方針をGateは検査しない。

   一方、`schemas/manual_case_set.schema.json:56` 以降はblackをexternal UIと説明し、domain packとgoldenでは監査ログをgrayの補助に寄せる。しかし利用者向け監査ログ画面や公開APIの仕様確認は、仕様に基づくblack-box受入対象になり得る。テストをどう導出したかと、画面／API／内部ログのどこを観測するかは別に扱う必要がある。[CTFL 2.2.2](https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf#page=30)

   改修案：テスト導出方式、実行が手動か自動か、観測面、受入の主証跡か補助かを整理する。公開された監査機能を受入から除外せず、内部構造の補助検証だけで外部受入を完了扱いにしない。

8. **R18：自動証跡の成功判定と数値の妥当性が不足。**

   `schemas/automation_evidence.schema.json:6` 以降と `gate_engine.py:273` 以降は、coverage、blocker/critical件数、hotspotを扱うが、テストsuiteの成功／失敗、実行・失敗・未実行件数を表す欄がない。source_refsの説明文にテスト1件失敗と書いても、型付きの成否情報にはならず、coverage100%なら `go`。実CIの失敗を接続した試験ではなく、契約にsuiteの成否を表現できないことを確認したもの。

   加えて、PythonのJSON読み込みは非標準値NaNを許し、schemaの最小／最大比較とGateの閾値比較がNaNを拒否しない。coverageとhotspotをNaNにしたstrict入力がexit=0、`go`になった。NaNは正常なJSON数値ではない。

   改修案：自動テストの成否・完了状態・対象suiteを明示する。coverageは実行成功と別に評価する。JSONの非標準数値を拒否し、数値欄は有限値を必須にする。strictの「new issues 0」も、現在はblocker/critical以外を表現できないため、方針との対応を整理する。

9. **R19：受容状態と承認の根拠を対応付ける。**

   `schemas/waiver_set.schema.json:15` はownerと期限等を必須とするが、承認者、承認日時、承認済みの根拠への参照を表せない。`gate_engine.py:318` 以降もfeature/build/期限を確認するだけ。ドラフトを示すreason、対応担当owner、期限等を持つwaiverが、CLI本体でconditional_goに使用された。

   critical assumptionはresolution_statusをacceptedとするだけでGo、high defectもstatus=acceptedならwaiverなしでGoになった。これは外部の承認が実際になかったことを証明する試験ではなく、受領したartifactから承認の有無を区別・追跡できない問題。

   また、leanでは未解消P2リスクをwaiver条件に入れず、blockedなP2があっても明示受容なしでGoになった。方針の「medium can be waived」と、無条件許容の実装は揃っていない。

   改修案：承認の正本が外部ならその参照を保持する。対応担当と受容判断者を区別し、acceptedとresolvedの意味を整理する。プロファイルが許容する残余リスクと、明示受容が必要なものを定義する。

10. **R20：ケースIDの一意性を検証する。**

    manual_casesは同じtc_idを持つ複数ケースを許し、`gate_engine.py:130` 以降の辞書代入で後のケースが前のケースを上書きする。異なる手順のP0ケース2件に同じIDを与え、証跡1件を渡すと、P0 total=1、pass=1、Goになった。第1回R1の環境別集約とは異なり、ケース定義そのものが消える。

    改修案：ケース・チャーターを合わせてIDを一意にする。observation/risk等のIDも同様に検査する。重複した定義は後勝ちで受理しない。

    集計に関連する小さな問題として、`gate_engine.py:176` はblocked/unknown/untestedをskipにも加算する。今回のblocked1件はtotal=1、blocked=1、skip=1。合計可能な排他的分類と、未成功の集約指標を別名にする。

11. **R21：否定条件を重ねると、別ルールの欠陥を見逃す。**

    `goldens/admin-role-change.input.md:12` の最後owner降格禁止と、17行の自己owner降格禁止に対し、`examples/artifacts/admin-role-change.manual_case_set.json:68` 以降のTC-ADMIN-004は「ownerが1人の状態で自己降格」を確認する。

    自己降格禁止だけが未実装でも、最後owner制約が拒否すればケースは成功する。複数owner時の自己降格を確認する独立ケースがなく、goldenの必須観点にも入っていない。これは製品実装で不具合を発生させた試験ではなく、テスト条件の論理から確認した見逃し。

    改修案：否定ケースごとに今回発火させる拒否条件と、他の拒否条件を避ける前提を明示する。複数ownerでの自己降格ケースを追加する。最後owner制約を単独で発火できる操作が仕様上存在するかは別途整理し、不可能な操作を発明しない。無効遷移を分離して欠陥マスキングを避ける考え方は [CTFL 4.2.4](https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf#page=42) にあり、今回の業務条件への適用は本レビューの改善判断。

12. **R22：評価用サンプルが、誤った参照を正しい手本として扱う。**

    admin-role-changeのfeature_spec/test_modelはRBAC-01・admin/super_admin体系、manual_case_setはADMIN-ROLE-CHANGE-01・owner/editor/viewer体系。さらにTC-ADMIN-005は招待更新のオラクルをAC-5とするが、goldenのAC-5は権限即時反映で、招待更新はBR-2。TC-ADMIN-006が参照するAC-6はgoldenに存在せず、監査ログの根拠はBR-3。

    `docs/acceptance/AC-20260530-02.md:90` 以降はこのケース群をsource_ref/oracle/trace_to明示済みとしてPASSにしている。参照欄の有無だけでは意味の正しさを検証できない。ケース側の今回の未コミット差分はstatus追加が中心であり、この不整合を全て現在の作業途中のせいにはできない。

    改修案：golden、feature/model、caseの仕様を揃える。参照が実在するだけでなく、参照先が期待結果を裏付けることをレビューする。第1回R3の補強証拠として扱う。

13. **R23：Ready判定の意味検証が必要。**

    `schemas/phase_contract.schema.json:31` 以降はstatusとdecisionを別々のenumとして検証するため、blocked＋readyが通る。criticalかつblocks_ready=trueの未決事項、空ownerを含むok＋readyもpackage validatorを通った。

    `ready-phase-contract.md:34` 以降は重大未決事項をblockedとし、例外に明示waiverを求めるが、schemaは判定の整合やwaiverへの参照を担保しない。第1回R9の新たな開始基準の提案とは別に、既に存在する開発着手前契約の問題。

    改修案：status/decision対応、重大未解決事項、担当・期限、例外の参照を意味検証する。

検証の記録：

- 既存のTestRail/Xray取り込みテスト87件、statusテスト60件、計147件は成功。ただし、誤ったステータス対応と実APIと異なる応答をテストが前提としており、成功は上記不具合がない証明にならない。
- Gateは実際のCLIから呼ばれる `bb_harness.gate_engine.main` に、実ファイルを指定して11例（正常例1、追加例10）を実行した。入力・生成Gateと最初の10例のsummaryは `C:\Users\ryo-n\Codex_dev\tmp\manual-bb-review-round2-20260912\` に保存した。ACなし取り込みの追試は同directoryの `no_ac_ingest_gate/`。
- CLI確認例は、入力省略、critical assumption受容、whiteのみ、NaN、自動失敗の表現不足、ID重複、high defect受容、waiver、lean残余リスク、AC未発見。
- APIは公式資料とHTTP Mock、変換は純粋関数で確認。実サービスへの接続・書き込みは行っていない。
- 全pytestは第1回で収集エラーを確認済み。今回の147件を全suiteの成功とは扱わない。

改修順は、まずR11/R12/R13/R16/R18の「欠落・誤変換・不正な値が判定へ入る経路」、次にR14/R17/R19/R20の「証跡の同一性と判断条件」、続いてR15/R21/R22/R23の「ケース・評価資産・Readyの意味検証」を推奨する。第1回の環境別集計と未解決欠陥の保持も同時に優先する。

テスト追加では、コードと同じ対応表を期待値にする方法を避け、公式のAPI例、元仕様の各ルール、反例を使う。テストベース→ケース→外部ツール→実行結果→Gateを小さなfixtureで往復させる検証が、このツールには特に有効。
