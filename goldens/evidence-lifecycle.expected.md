# 期待する確認項目

- GateはNo-Go。
- 構成別実績にはAndroidの最新passとiOSのuntestedが残る。
- caseのP0分母は1、untestedは1。必須観点の実行率は0%。
- BUG-1はfixedとして未解決一覧へ残る。
- 自動test_suitesのfailedと内訳を保持し、失敗理由へ反映する。
- Androidの成功やカバレッジ100%で上記の不足を打ち消さない。

[evidence-lifecycle.expected.json](evidence-lifecycle.expected.json)はCLI出力例。判定条件はこの確認項目と回帰テストで独立に検証する。
