# Deep Researchの取得と採用状況

- ユーザー指定の[共有ページ](https://chatgpt.com/share/6aa1ebbb-ab30-83ee-808c-b59dbaf90b3d)から、2026-09-10にMarkdownエクスポートした。
- [原本](istqb-extension-requirements-20260910.md): 58,822 bytes、SHA256 `78694b6d646a0d6f199e1c6da0437b158a94c516843e45940865abecbd81c598`。本文は改変せず保存した。
- 調査対象SHAは `13100ac69b03cae04d35481870d7f5e6d8f8eb5f`。今回の改修開始HEADは `7672257`。差分を確認して現行Local Modeへ適用した。
- 正本checkoutは `Codex_dev/manual-bb-test-harness`。Agent_tools配下の旧checkoutは変更していない。

## 採用範囲

| 要件群 | 今回の実装 | 制約・残作業 |
|---|---|---|
| A: trace / merge | タイトル単独削除を廃止。明示的risk接続のみ。review後も異なる入力を保持 | 自然言語の意味的一致はレビュー対象 |
| B: TECH / COV / GenAI | 共通技法参照、型付きモデル、安定ID、ケースから独立再計算、schema、生成来歴 | 高リスクの自動multi-run合意・モデル版取得は未実装 |
| C: Domain | 開閉、精度、線形複数変数、ON/OFF/IN/OUT、遮蔽検出 | anchor明示、数値・線形のみ。別anchor探索はしない |
| C: combinatorial | 制約付きbase_choice/pairwise/n_wise/all | 全割当10,000件まで。大規模solverや最小covering arrayなし |
| C: state | 単独・全・n-switch・round_trip、guardとaction更新 | contexts有限、経路長6まで。任意の状態を準備できる前提 |
| C: decision table | 完全性、矛盾、重複、実行可能性、最小化の条件・action保存 | 有限条件集合のみ |
| D: reporting / Gate / migration | 設計・実施・合格分離、shadow、別ファイルへの移行・legacy export | 新Gate閾値なし。report単独の真正性保証なし |
| E: CRUD / scenario / checklist | 操作・整合性経路、ループ、チェックリスト版 | 事前に宣言されたモデル内の検証 |
| E: random / metamorphic | seed付き試行、実測入力、joint評価と出力の一致 | uniformのみ。random時間制限は計画情報で判定対象外 |
| E: exploratory / session | charter・session_logの追加契約 | sessionの意味的採点・自動終了判断は未実装 |
| F: integration / Crowd / Agile | integration_pathsとcrowdの共通語彙 | adapter、連携経路の自動被覆、Example Mapping、toursは未実装 |

資料は段階的な拡張案として採用した。すべての要件を実装済みとは扱わない。優先したのは、必要な被覆を生成からGateまで失わないことと、計算できない状態を明示することである。

実装仕様は [技法被覆ガイド](../../skills/manual-bb-test-harness/references/technique-coverage.md)、実行結果は [検収記録](../acceptance/AC-20260910-istqb.md) を参照。Domainの点とround-trip定義は [ISTQB公式シラバス](https://istqb.org/wp-content/uploads/sdm-uploads/ISTQB-CTAL-TA-Syllabus-v4.0-EN-4.pdf) と照合した。
