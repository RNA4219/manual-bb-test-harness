manual-bb-test-harness ISTQB 観点レビュー（2026-09-12）

対応状況（2026-09-12）: R1〜R10はすべて修正済み。R1・R2は実行構成と欠陥台帳、R3・R4はID付きcoverage母集団と3値境界値、R5・R6はtestware identityとP0非該当、R7・R8はチェックリスト／探索記録とmulti-run統合、R9・R10はtest planと品質特性feedbackを契約化した。回帰テストは`test_gate_evidence_lifecycle.py`、`test_istqb_coverage_contract.py`、`test_istqb_second_wave_contract.py`に固定した。以下は改修前の調査記録。

改修後にroot/package schema 21組の一致、example strict validation 31件、実Gate CLI、全pytest 1002件、coverage 88.22%、Ruffを確認した。最終実行結果は第2回レビュー冒頭へ集約した。

追加調査は [第2回レビュー](istqb-review-round2-20260912.md) を参照。

対象は HEAD `1d8619b` と、レビュー開始時から存在する未コミット変更を含む作業ツリー。Skill、設計方針、schema、golden、CLI の Gate 実装を確認した。製品コード・既存ドキュメントは変更していない。

骨格は良い。同値分割・境界値分析・デシジョンテーブル・状態遷移を軸に、根拠、リスク、手動ケース、工数、実行証跡、判断材料まで接続している。無効遷移、権限の所有者文脈、回帰影響、モバイルの中断復帰、オラクル不足への対応も明記されている。

改修の中心は、技法名を増やすことに加え、網羅対象を検証可能にし、失敗・未解決欠陥・環境差を Gate で失わないこと。公式 [ISTQB CTFL v4.0.1 シラバス](https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf) を比較基準とした。以下の優先度と改修案は本レビューの判断であり、シラバス全体の機能化や資格教材としての適合を要求するものではない。

| ID | 優先度 | 改修点 | 確認方法 |
|---|---|---|---|
| R1 | 高 | 環境別の失敗が後続の成功で消える | 動作確認済み |
| R2 | 高 | 未解決欠陥が再実行の成功で判定から消える | 動作確認済み |
| R3 | 高 | 技法別の網羅母集団と参照整合性を検証できない | schema・Gate 動作確認済み |
| R4 | 高 | 3値境界値分析の適用対象と例が不十分 | 公式定義と照合 |
| R5 | 中 | 実行証跡とテストウェアの版の結び付きが弱い | schema・Gate 動作確認済み |
| R6 | 中 | P0 が存在しない低リスク変更を必ず No-Go にする | 動作確認済み |
| R7 | 中 | チェックリストベーステストと経験ベース技法の区分が弱い | Skill・schema 確認 |
| R8 | 中 | multi-run の少数観点を重要性によらず optional にする | Skill 方針確認 |
| R9 | 中 | テスト計画・開始基準・見積根拠の契約が不足 | 方針・schema 確認 |
| R10 | 中 | 非機能の適用判断とテスト改善の記録が弱い | 方針・rubric 確認 |

1. **R1：実行結果はケースと実行構成の組で集計する。**

   `src/bb_harness/gate_engine.py:115` 以降の `latest` は `tc_id` または `charter_id` だけをキーにしている。`env`、`device`、`network_profile` は集計キーに入らない。同一 feature/build/case で Android の fail の後に iOS の pass を渡すと、採用証跡は iOS の1件となり、他条件を満たした Gate は `go` になった。同時刻なら異なる環境でも重複エラーになる。

   `configuration_id` と計画した実行単位を導入し、case × configuration の各組で再実行を選ぶ。必須構成の未実施・失敗を残したまま全体を成功にしない。端末名などの自由記述だけで構成を同定せず、対象 OS・端末・ネットワーク等を構成定義へ結び付ける。関連：CTFL 5.4（構成管理）。

   追加検証：同一 build の異なる2構成、同時刻の別構成、必須構成の未実施、同一構成だけの再実行。

2. **R2：欠陥の状態を最新のテスト結果から独立させる。**

   `src/bb_harness/gate_engine.py:712` で最新証跡を選んだ後、717行で選択済み証跡だけから欠陥を抽出する。high/open の欠陥を伴う fail の後に、欠陥情報のない pass を渡すと `open_defects=0`、`go` になった。欠陥をクローズしたという情報は入力していない。

   欠陥 ID による台帳または外部 tracker の状態 snapshot を受け取り、修正、確認テスト、クローズを追跡する。再実行の pass だけで欠陥を閉じない。現状の `defect_stub` は title/severity/status のみで、欠陥 ID、修正優先度、修正対象 build、確認結果への参照も保持できない。関連：CTFL 2.2.3、5.5（確認テスト・欠陥管理）。

   追加検証：未解決のまま再現しなくなった欠陥、修正確認待ち、再オープン、複数ケースが参照する同一欠陥。

3. **R3：網羅対象を ID 付き構造にし、設計・実行・成功の指標を分ける。**

   `schemas/test_model.schema.json:7` の必須配列は空でも通り、boundaries と valid/invalid_transitions は省略できる。各項目は自由文字列で、`rule_columns` の例も実際の条件・動作の列ではなく `order_state x coupon_used x actor` という軸の説明になっている。`schemas/observation_set.schema.json:42` の coverage_item_id は任意で、参照先の実在確認がない。架空の coverage_item_id も schema を通り、Gate は `go` になった。

   `src/bb_harness/gate_engine.py:299` の網羅率は mandatory な観点 ID の実行率である。同値パーティション、境界点、実行可能な決定表の列、有効／無効遷移の網羅率とは別の指標。Gate は test_model を入力としていないため、この不足を検知できない。

   項目に ID、適用／対象外と理由、mandatory、source refs を持たせ、observation → coverage item → source と case → observation/risk の参照を検査する。技法ごとに母集団・網羅基準・未網羅項目を保持する。状態網羅／有効遷移網羅／全遷移網羅を明示的に選ぶ。決定表には条件、動作、実現不能、結果に無関係な条件を記録する。pairwise を使う場合も、業務ルールの未実施列と残余リスクを残す。全件を常に実行することを要求する案ではない。関連：CTFL 1.4.4、4.2。

   追加検証：未定義 ID、孤立した必須項目、状態だけ網羅して遷移が欠落、決定表の実現不能列、空配列を明示的な対象外と区別するケース。

4. **R4：3値境界値分析を「各パーティションの境界と両隣」として定義する。**

   `skills/manual-bb-test-harness/references/case-design-policy.md:46` は高リスクの順序付きパーティションに3値分析を指定するが、74行のデータ層は `min-1, min, min+1 / max-1, max, max+1` のみ。この min/max を有効範囲の端だけと解釈すると、無効側パーティションの境界に隣接する点を落とす。

   例として、整数の有効範囲が 1〜100、同値パーティションが「0以下」「1〜100」「101以上」なら、境界値は 0、1、100、101。公式定義をこの例に適用すると3値の対象は `-1, 0, 1, 2, 99, 100, 101, 102`。現行の式を有効範囲だけに適用すると -1 と102を落とす。この具体例はレビューで作成したもの。比較根拠：[CTFL 4.2.2（40ページ）](https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf#page=40)。

   2値／3値の選択理由、各パーティションの境界、包含／非包含、値の最小刻みを持たせる。日付や小数に機械的な ±1 を適用しない。数値範囲、隣接する有効クラス、単一値クラス、非整数刻みを golden に追加する。

5. **R5：証跡の再現性と有効期限の根拠を強める。**

   `schemas/execution_evidence.schema.json:6` では識別子、日時、result が中心で、env、tester、oracle、expected、actual は任意。これらを省略した pass だけでも Gate は `go` になった。build の一致確認は実装されているが、ケース・仕様・オラクルが同じ版だったかは判別できない。

   case/spec の revision または content hash、configuration ID、実行者、観測内容または元の証跡への参照を結び付ける。期待値を毎回複製する必要はなく、版が固定されたケースへの参照でもよい。外部ツールからの最小 import を許す場合は、元証跡を取得できる参照と、判定に使える証跡の充足基準を定義する。関連：CTFL 1.4.4、5.4、5.5。

6. **R6：P0 の非該当と、計画した P0 の未実施を区別する。**

   `src/bb_harness/gate_engine.py:500` は P0 total=0 を常に失敗条件にしている。全リスク・ケースを P2 とし、全件 pass、mandatory 観点100%、自動証跡充足でも `P0 evidence is missing` により `no_go` になった。軽微変更を通すために P0 を作る運用は、リスク評価の意味を崩す。

   承認されたリスク分析・計画に P0 がない場合を明示し、P0 非該当を許す。一方、計画した P0 の証跡がない場合は引き続き No-Go。閾値、優先度区分、自動カバレッジ補正はこのツールの運用方針として根拠を残す。追加の小修正として、risk-and-gate-policy.md:17 の式は I=L=1、A=3、他補正0で負値になるため、schema の0〜100と整合する下限を設ける。

7. **R7：経験ベース技法を個別に扱う。**

   `skills/manual-bb-test-harness/SKILL.md:50` は経験ベース技法を探索チャーターにまとめている。`schemas/observation_set.schema.json:53` に error_guessing と exploratory はあるが checklist_based はない。domain/platform pack にチェックリスト自体は存在するため、観点が皆無という指摘ではない。

   チェックリストの版・項目 ID・項目ごとの確認結果を表現できるようにする。エラー推測には不具合履歴などから作る欠陥仮説を持たせ、妥当なオラクルがあるものは scripted case 化できると明記する。探索は目的・時間枠に加え、実施メモ、発見、振り返りを保持する。現在は estimate_minutes も任意。関連：CTFL 4.4。

8. **R8：複数回生成の一致数で重要度を下げない。**

   `skills/manual-bb-test-harness/SKILL.md:40` は support_count が低い観点を optional に落とす。仕様上必須の観点や重大なリスクが1回だけ見つかった場合の例外がない。

   support_count は生成の安定性・レビュー順の補助にとどめる。mandatory とリスクは根拠、影響、発生可能性で判断し、重大な少数観点はレビュー対象として保持する。追加検証は「3回中1回だけ抽出された、明示的な受入条件に基づく重大観点」。

9. **R9：計画と見積の判断根拠を artifact に残す。**

   `ready-phase-contract.md` に開発着手前の Ready 判定はある。一方、実際のテスト活動について、目的、テストレベル、開始基準、停止・再開条件、必要なデータ・環境の準備状況をまとめて検査する契約は弱い。`schemas/effort_plan.schema.json` はフェーズ別時間、buffer、依存、担当を表せるが、見積方法、根拠データ、前提、不確実性、実績との差分を保持できない。

   軽量な test_plan／readiness 情報を既存 chain に追加する。工数は過去実績や試行実行による補正を使い、必要な箇所だけ幅を持たせる。全案件へ全見積技法を要求しない。関連：CTFL 5.1.1、5.1.3、5.1.4。

10. **R10：非機能の選定と改善フィードバックを明示する。**

    usability、compatibility、recovery、security 等は既に quality_lenses／domain pack で扱える。ただし、それぞれを今回評価するか、対象外か、外部証跡を使うかと、その理由・判定基準を要求していない。性能やアクセシビリティなどに明示要件があっても、探索へ寄せすぎる可能性がある。

    品質特性ごとに適用判断とオラクルを記録し、手動で測定できないものは担当する検証や外部証跡へ結び付ける。実行後の不具合傾向、見逃し、実績工数を checklist・risk・golden の更新へつなぐ。既存の forward-test は Skill 出力品質の評価として活かし、対象製品のテスト改善も記録する。これは対象範囲を広げる場合の改善案。

検証結果と現在の作業ツリーの不整合：

| 検証 | 結果 |
|---|---|
| 全 pytest | 収集段階で2 errors。全件成功は確認できなかった |
| test_gate_v2.py、test_import_status.py、test_state_diagram.py | 122 passed |
| R1、R2、R5、R6 の Gate 確認 | schema を満たすローカルの合成入力で、上記の結果を確認 |
| R3 の確認 | 空の model と架空 coverage_item_id が受理されることを確認 |
| 現行 example 3種の runtime schema 検証 | 全て status 等が未許可で失敗 |

全 pytest の2 errors は、`tests/test_export.py` と `tests/test_validate_artifact.py` が読み込む変更済み script の `from _shared.io_common import load_json` によるもの。`scripts/_shared/io_common.py` は存在しない。共通実装は `src/bb_harness/tools/_shared/` にある。

また、CLI の Gate は `src/bb_harness/commands/gate.py:9` から `bb_harness.gate_engine` を使い、schema は `src/bb_harness/schema_validation.py:39` に従って package 内を優先する。既存の未コミット変更にある retired 対応は主に root schema と scripts に入り、package 内 manual_case_set schema は status を受け付けない。order-cancel、admin-role-change、mobile-session-resume の現行 example でエラーを確認した。これは現在の作業ツリーの整合性問題として扱い、リリース済み2.0.0全体の不具合とは断定しない。

実行コマンドは、既存 `.venv/Scripts/python.exe` による `-m pytest -q -o addopts= --tb=short` と、同じコマンドで上記3ファイルを指定したもの。動作確認は入力をメモリ上で作り、package の schema validator と Gate 関数へ渡した。外部サービスへの書き込みは行っていない。リポジトリの726件成功という過去記録は、今回の作業ツリーの検証結果として流用していない。

推奨する着手順は、既存変更の script/package/schema 整合性回復 → R1/R2 の誤った Go 防止 → R3/R4 の技法と網羅性 → R5/R6/R8 の判断の安定化 → R7/R9/R10 の運用拡張。最初の改修単位には、数値境界の golden と、環境差・未解決欠陥・未定義参照・P0非該当の回帰テストを含めるとよい。
