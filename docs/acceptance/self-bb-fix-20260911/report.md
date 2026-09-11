# 自己BBで見つかった3件の修正・再検証

2026-09-11。仕様を先に更新してMBB-BB-001〜003を修正した。**修正版wheelの計画BBケースは45/45 pass、探索で見つかったBOM欠落も解消。全体テスト1,117件pass、coverage 88.48%。Gate専用116件pass、coverage 92.32%。** 今回の3件の修正受入はpassとする。

対象はmain `6149d81fee17b6271503717b3fc2c0f6a738a540`にローカル変更を加えた未公開版。packageのversion文字列は4.1.0のままであり、PyPIで公開済みの4.1.0とは別の配布物である。公開版の修正・mainへのマージ・新版公開はこの記録に含めない。

## 変更と結果

| 不具合 | 仕様・実装 | 修正後の実測 |
|---|---|---|
| MBB-BB-001 日本語名のLocal Mode停止 | 空の機能IDだけに安定した代替IDを付与。既存の日本語名の要件評価IDとASCII名のID規則を保持 | BB-31見積もりは終了0・HTTP0・出力なし。BB-32予算1は終了1・`token_budget`・生成0回 |
| MBB-BB-002 BOMで先頭要件を欠落 | 共通Markdown読込で先頭のUTF-8 BOMだけを扱う。H1/H2/frontmatter、要件評価、Local Modeへ適用 | CH-01-bomは要件1・score69。回帰テストで同じパス・本文のBOM有無のartifact／入力hash一致と本文変更時のレビュー失効を確認 |
| MBB-BB-003 証跡0件のGateレポートなし | 明示buildの空証跡を未実施評価へ渡す。build欠落・空白や不正証跡の拒否を維持 | BB-38は終了0・`no_go`・全4件untested・pass0。回帰テストで両CLI導線×3profileを確認 |

仕様は[CLI共通契約](../../specs/spec-02-cli-integration.md)、[生成予算](../../specs/spec-05-efficient-generation-evidence-revisions.md)、[要件評価](../../specs/spec-07-requirements-confidence.md)へ反映した。型やschemaの変更はない。

## 検証

| 検証 | 結果 |
|---|---|
| 関連テスト | 299 pass |
| 全体pytest | 1,117 pass、123.92秒、coverage 88.48%（下限85%） |
| Gate専用pytest | 116 pass、10.10秒、coverage 92.32%（下限90%） |
| 修正版wheelの外部CLI BB | 計画45/45 pass、P0 5/5 pass、探索5件を別記録 |
| ruff | pass |
| Skill検証3種 | pass |
| artifact schema | 29 valid、0 invalid |
| 仕様検証 | 8 pass、0 fail |
| Workflow Cookbook freshness | strict pass |
| build | wheel／sdistをオフライン作成。wheelを新規venvへ導入 |

BBは[初回計画](../self-bb-4.1.0/plan.md)の期待値を変えずに再実行した。[初回の失敗・切り分け記録](../self-bb-4.1.0/report.md)は保持している。再試験runnerでは、既に切り分け済みの試験側の前提だけを補正した。

- BB-14: 公開レポートの確認事項ID形式`review:F-1`を使う。
- BB-35: 変更後のケースを正規コマンドでrebindしてから被覆を評価する。
- BB-38: 空の証跡ディレクトリを明示する。
- BB-29: 存在しない`confirmations`ではなく、出力の`issues`キーの存在と値を比較する。

今回追加した回帰は21件。新しい機能IDが別ディレクトリで変わらないこと、異なる日本語名を区別すること、従来の具体的なID値を保持すること、日本語名・絵文字名の見積もり、本文中のBOM文字を消さないことも確認した。

実LLM生成呼出は0回。BBではローカルHTTPテストダブルで通信を観測し、pytestのモデル応答もテストダブルである。HATE/QEGの外部ジョブやGitHub Actions全体は今回再実行しておらず、「CI全ジョブが緑」とは判定していない。

## 配布物と証跡

新規venvの導入先は`tmp/self-bb-fix-20260911/installed/venv`。wheel中の修正4モジュールが、作業ツリーと導入先のbyte列に一致することを確認した。editable導入ではない。

- wheel: 188,950 bytes、SHA-256 `6f5a595fc9978989ebf4c704cbf190955c17b65b0587496d5bbc8302f270c43d`
- sdist: 252,187 bytes、SHA-256 `a33225c85161a65609e6f0817d045244513eb63e6951d581c3949c3761edad06`
- [最終結果](final-results.json)、[BB再試験runner](runner.py)
- [証跡アーカイブ](evidence.zip)、[SHA-256 manifest](evidence-manifest.json)

アーカイブには初回の期待値から作った再試験runner、58 CLI呼出のログ、合成入力と出力、pytestログ／JUnit／coverage、配布物照合、修正パッチと新規テストを保存した。実績分析の6呼出はrepo付属補助ツールであり、公開CLIの呼出52件と区別する。

試験本体45件と探索5件はすべて終了したが、runner末尾の配布物照合JSONの収録は、先行した読取権限の制限により準備が遅れて一度失敗した。権限を通した読取照合に成功後、その収録処理だけを完了し、全ケース・全ログの存在と成功を再確認した。`bb.log`の終了1を消さず、復旧内容を`finalization.json`に保存している。製品CLIの失敗や、試験結果の書き換えではない。

## 判定の範囲

今回の3件は修正・再現確認済み。修正受入のpassと、実際の案件のGateで証跡0件を`no_go`にすることを区別する。実LLM生成の意味的品質、実案件での採点policy校正、他OS／他Pythonの未評価は従来どおり残る。公開済み4.1.0へは自動反映されない。
