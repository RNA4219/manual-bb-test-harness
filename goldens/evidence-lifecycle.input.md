# 実行証跡を保持する複合シナリオ

説明用の架空データ。対象は保存操作のP0 caseで、Android/iOSの両構成を必須とする。

- Androidで失敗し、high欠陥BUG-1を報告した後、同じ構成でpassした。
- iOSは未実行。
- BUG-1はfixedで、確認・解決記録はまだない。
- 必須の自動テストsuiteは2件中1件が失敗している。

入力artifactは[examples/evidence-lifecycle](../examples/evidence-lifecycle/)を使う。
