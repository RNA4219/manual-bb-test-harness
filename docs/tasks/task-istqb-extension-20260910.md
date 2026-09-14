---
task_id: 20260910-istqb
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: completed
last_reviewed_at: 2026-09-10
next_review_due: 2026-10-11
---

# ISTQB調査に基づく被覆契約の拡張

## 根拠

- [ダウンロード原本](../research/istqb-extension-requirements-20260910.md)
- 共有URL: https://chatgpt.com/share/6aa1ebbb-ab30-83ee-808c-b59dbaf90b3d
- 原本SHA256: `78694b6d646a0d6f199e1c6da0437b158a94c516843e45940865abecbd81c598`
- 調査対象: `13100ac69b03cae04d35481870d7f5e6d8f8eb5f`、改修開始: `7672257`
- 正本checkout: `Codex_dev/manual-bb-test-harness`。Agent_tools配下の旧checkoutは変更しない。

## 実施対象と完了条件

1. FR-CORE-TRACE/MERGE: 根拠のない接続とタイトル単独の削除をなくす。
2. FR-CORE-TECH/COV、FR-GENAI: 共通技法、型付きモデル、永続被覆ID、独立検証、出典・生成来歴。
3. FR-DOM/COMB/STATE/DTABLE: 精度、制約、連続遷移、決定表の完全性を検証する。
4. FR-GATE-COV: 設計済み・実施済み・合格を分離し、既存Gateにshadow指標を追加する。
5. CRUD、scenario、metamorphic、random、checklist/sessionの契約と検証、非破壊移行。
6. schema/example/golden/Skill/評価基準を同期し、回帰・package・構造検証を行う。

大規模なSAT/SMT、未指定のGate閾値、Crowd vendor接続は導入しない。有限モデルの計算上限や未対応の表現は明示的にblockedとし、網羅済みにしない。

## 検収

[AC-20260910-istqb](../acceptance/AC-20260910-istqb.md)
