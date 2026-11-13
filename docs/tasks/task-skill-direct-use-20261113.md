---
task_id: 20261113-skill-direct-use
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: completed
last_reviewed_at: 2026-11-13
next_review_due: 2027-02-12
---

# Skill を読んで直接書く使い方の補強

- 受入記録: [AC-20261113-skill-direct-use](../acceptance/AC-20261113-skill-direct-use.md)

## 背景

- Skill を読んで設計書を直接書く使い方では、Local Mode が行う検算や完了判定が働かない。点数の手計算、実施前の Gate、自動テストとの重なり、優先度の上げ下げなどを、書き手がその都度補っていた。
- `SKILL.md` は、CLI と組で使う仕事と、直接書く仕事が同じ並びにあり、依頼に当たる節を探しにくかった。

## ゴール

- 直接書く使い方で要る決まりを、Skill と references に入れる。特定の組織・製品に固有の運用は入れない。
- リスクの点数を、書いたあとに機械で確かめられるようにする。
- `SKILL.md` を仕事ごとに並べ直す。元の指示の文は変えない。

## 実施対象

1. Markdown のリスク表を式で検算する `bb-harness check risk`。
2. `SKILL.md` の並べ直しと、仕事の入口の表。
3. 実施前の Gate、対象外と blocked の書き方、ケースの優先度と昇格。
4. 自動テストと重なる観点の外し方、`[要確認]` の仕分け。
5. 出力のひな形（優先度、未決事項、変更の記録、質問の下書き、レビューの形、表計算への展開、日本語の見出し、軽い版）。
6. 実施の仕分け（LLM と手動）と、脆弱性の観点の pack。
7. `pwsh` が無い環境でのテストの扱いと、期限の切れた正本文書の見直し。

## 完了条件

- [x] 既存のテストと検査が通る。
- [x] 新しいコードにテストがある。
- [x] 元の `SKILL.md` の本文が、並べ直したあとも残っている。
- [x] JSON の schema と例を変えていない。

## 参照

- [リスクと Gate の方針](../../skills/manual-bb-test-harness/references/risk-and-gate-policy.md)
- [実施の仕分け](../../skills/manual-bb-test-harness/references/execution-routing.md)
- [脆弱性の観点](../../skills/manual-bb-test-harness/references/security-pack.md)
