---
task_id: 20260912-testrail-contract
intent_id: INT-TESTRAIL-EVIDENCE
owner: Codex
status: completed
last_reviewed_at: 2026-09-12
next_review_due: 2026-10-12
---

# Task Seed: TestRail の誤ったテスト仕様を先に修正する

## 背景

追加レビュー R12・R13 で、TestRail 標準ステータスの番号逆転、ページ応答未対応、結果取得失敗の握りつぶしを確認した。利用者の指示に従い、テストの期待値を一次仕様から定めて失敗を確認した後に実装を修正する。

## ゴール

Failed の証跡と欠陥を保持し、run の全ページ取得に対応する。必要な取得が途中で失敗した場合に不完全な証跡を出力しない。

## 実施対象

1. 既存テストの標準 ID と取得失敗時の期待値を修正。
2. ページ応答、旧配列、循環リンク、結果取得失敗、既存出力の保持を検証する20件を追加。
3. 失敗の確認後、package 内の TestRail importer と仕様文書を修正。

## 完了条件

- [x] 製品コードの変更前に、修正・追加したテストの失敗を確認。
- [x] 標準 ID `4=Retest / 5=Failed` が内部の `skip / fail` に変換される。
- [x] tests の全ページを取得し、results から最新1件を取り出せる。
- [x] 取得途中の失敗で中断し、既存の証跡を変更しない。
- [x] 関連210テスト、対象ファイルの lint、Skill 検証を通過。
- [x] 全体検証を妨げる既存問題を検収記録に分けて記載。

## 参照

- [追加レビュー](../istqb-review-round2-20260912.md)
- [インポート仕様](../specs/spec-04-test-result-import.md)
- [検収記録](../acceptance/AC-20260912-testrail-contract.md)
