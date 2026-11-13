---
acceptance_id: AC-20261113-skill-direct-use
task_id: 20261113-skill-direct-use
intent_id: INT-MBB-001
owner: manual-bb-test-harness
status: draft
reviewed_at: 2026-11-13
reviewed_by: null
approval_type: null
release_approval_id: null
---

# Skill を読んで直接書く使い方の補強の検収

対象は [task seed](../tasks/task-skill-direct-use-20261113.md)。この記録は下書きで、持ち主の確認を受けていない。

## Scope

- 対象変更:
  - Markdown のリスク表を式で検算する `bb-harness check risk`（コード、テスト、例、文書）。
  - `SKILL.md` の仕事ごとの並べ直し。元の本文 52 行のうち 50 行は文を変えずに移し、1 行を 2 文に分け、説明文の 1 語を変えた。
  - Skill と references の決まりの追加（実施前の Gate、対象外と blocked、ケースの優先度と昇格、自動テストと重なる観点、`[要確認]` の仕分け、出力のひな形、実施の仕分け、脆弱性の観点）。
  - `pwsh` が無い環境で、PowerShell を呼ぶテスト 10 件をローカルでは skip にする変更。CI では省かない。
  - 期限の切れた正本文書 5 本（GUARDRAILS、HUB、RUNBOOK、BLUEPRINT、EVALUATION）の見直しと、知識マップの要約 12 件の更新。
- 非対象:
  - JSON の schema と例。ケースの昇格の理由と実施の仕分けは、Markdown にだけ書く。
  - 版（4.1.1）と、README の検証済みテスト数。
  - golden の更新。

## Acceptance Criteria

- [x] 既存のテストと検査が通る。
- [x] 新しいコードにテストがあり、全体の coverage が閾値（85%）以上である。
- [x] 元の `SKILL.md` の本文が、並べ直したあとも残っている。
- [x] wheel と sdist から、新しいコマンドを実行できる。
- [ ] golden の入力での forward-test で、足した決まりが出力に現れる。

## Evidence

- 実行コマンド: `uv run ruff check src scripts tests tools`、`uv run pytest`、`scripts/quick-validate-skill.py`、`scripts/validate-artifact.py --all`（`examples/artifacts` と `examples/evidence-lifecycle`）、`scripts/validate-spec.py --all`、`scripts/validate-release-bundle.py --dry-run`、`tools/ci/check_workflow_cookbook_tier.py`、`tools/ci/check_workflow_cookbook_freshness.py --strict`、`tools/ci/package_smoke.py`。
- テスト結果（macOS、Python 3.12、`pwsh` なし、変更をコミットした状態）:
  - pytest は 1537 件が通過、10 件が skip、失敗 0 件。skip の 10 件は `tests/test_validate_skill_ps1.py` の PowerShell を呼ぶテスト。
  - 分岐を含む coverage は 90.55%。新しい検算のコードは 99%。新しいテストは 66 件。
  - ruff、Skill の検査、artifact 33 件と 9 件、spec 8 件、release bundle、tier、freshness（strict）、wheel／sdist の smoke は成功。
  - 環境変数 `CI=true` では、`pwsh` が無いと PowerShell の 10 件が失敗することを確かめた。
- 見直しで直した古い記述: RUNBOOK の依存パッケージの数（30 → 26）、Action の固定方法（major version → commit SHA）、利用者の書き方。
- 参照ドキュメント: [リスクと Gate の方針](../../skills/manual-bb-test-harness/references/risk-and-gate-policy.md)、[実施の仕分け](../../skills/manual-bb-test-harness/references/execution-routing.md)、[脆弱性の観点](../../skills/manual-bb-test-harness/references/security-pack.md)。

## Verification Result

- 判定: pending
- コメント:
  - `validate-skill.ps1` は、確かめた環境に `pwsh` が無く、実行していない。CI の結果を正とする。
  - golden の入力での forward-test は行っていない。足した決まりの確認点は [evaluation rubric](../evaluation-rubric.md) に、採点に含めない形で載せた。
  - 検算は式との一致だけを確かめる。I・L・補正の値の妥当性と、ケースの優先度は確かめない。
- フォローアップ:
  - Local Mode は点数を小数 1 桁で丸め、文書と `risk_policy.py` は整数で丸める。raw が 68 のとき、優先度が P1 と P2 に分かれる。
  - `examples/artifacts/order-cancel.risk_register.json` と `docs/release-review-20260516.md` のリスクの点数が、式と合わない。
  - Ready の Markdown のひな形が 2 か所にある。
  - コミットの日付が 2026-11-13 より後になると、変更した文書の capsule の `last_verified` が古くなり、freshness の strict で stale になる。コミットの日付にそろえる。
