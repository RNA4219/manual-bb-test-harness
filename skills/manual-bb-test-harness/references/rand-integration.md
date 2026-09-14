# RanD連携

RanDはR&Dの収集・分析・要求候補生成を担う。manual-bbがその成果物を取り込み、観点の展開、優先付け、実行後の追加探索を担当する。入力契約の正本はrepoの`docs/tasks/task-rand-integration-20260912.md`。

## 取り込み

```powershell
bb-harness import rand --input path/to/requirements_packet.json --feature-id MY-FEATURE --output tmp/rand-review-01
bb-harness import rand --input path/to/requirements_document.json --diff path/to/requirements_diff.json --feature-id MY-FEATURE --output tmp/rand-review-02
bb-harness import rand --input path/to/requirements_document.json --feature-id MY-FEATURE --defects path/to/defect_register.json --output tmp/rand-review-03
```

`--dry-run`は上記に付加でき、JSONを表示するだけで保存しない。出力先は毎回新規directoryにする。CLI自身は対象製品を操作せず、入力のURIも開かない。RanDをPython依存に持たない。

対応入力はschema 2.0の`requirements_packet`、`requirements_audit_packet`、`requirements_document`、`downstream_handoff`。差分は`requirements_document`と同じ版の`requirements_diff`を組み合わせる。audit-documentの標準出力全体ではなく、そのdocument artifactまたは保存されたJSONを渡す。legacyは拒否し、旧ファイルにversionだけを付け替えない。

## 設計への入口

生成された`test_design_prompt.md`を依頼文としてSkillを実行する。`rand_intake.json`には元payload、入力SHA256、要求ID、原文、AC、上流評価、差分、任意の欠陥台帳が残る。受入条件があれば`feature_spec.json`も生成する。

取り込み成功と入力十分性は別である。対象環境・役割・依存関係の補足が必要なため、通常は`degraded`から開始する。空文書または全件ACなしは`blocked`で、feature_specは生成しない。一部AC欠損はcritical assumptionとして残す。R&D由来のACは候補であり、採用と期待結果の確定が未確認であるcritical assumptionを保持する。

1. 根拠付き観点: data / rule / state / role / flow / regressionをモデル化する。RanDの指摘だけに限定せず、原文全体と共有機能・依存先を確認する。
2. リスク: 影響と発生条件を説明する。上流confidenceやKanoをリスク点数やP0へ直結しない。
3. 優先度: 変更・未解決欠陥・不確実な判定条件を手掛かりに、対象固有の根拠で決める。
4. ケース: oracleのある対象から同値クラス、境界3値、条件組合せ、状態遷移、履歴と再試行を検討する。根拠なしの期待値を作らず、探索charterまたは要確認へ回す。
5. 工数: 準備・実行・証跡・再試行を分け、timeboxで探索範囲を選ぶ。
6. Gate: 実際のexecution_evidence、automation_evidence、defect_registerを別途揃えて評価する。上流のgoは取り込まない。
7. Brief: 発見した不具合、仕様不足、未実施範囲を分けて示す。

全現行要求を保持する。added/modifiedは重点対象、unchangedも回帰候補、removedは廃止確認として扱う。関連する未変更要求の省略や既存caseの自動retireはしない。diffからコードの依存関係が分かったとは見なさない。

## 穴を起点に次を確認する

`--defects`で同じfeature_idの欠陥台帳を渡せる。固定・確認待ちを含む未解決欠陥は`follow_up_defect_ids`へ入り、resolvedも元snapshotに残る。元build_idと確認runを維持する。

既知の失敗について「同じ条件での確認テスト」と「隣接条件への探索」を分ける。例えば再試行で問題が見つかった場合は、中断位置、初期状態、過去の実行履歴、入力の同値クラスとの関係を検討する。対象との関係を説明できない組合せを無制限に増やさない。

台帳のsource_refsから既存case・要求・実行証跡を照合する。関連を確定できない場合は要確認とし、IDの似通いだけで紐付けない。実行後は新しいexecution_evidenceを保存し、根拠付きで台帳を更新する。再実行のpassだけで欠陥を閉じない。更新台帳を次のimportへ渡し、さらに必要な観点を設計する。

現在の連携は入力変換と設計依頼の生成までをCLIが担い、観点・ケースの展開と結果の検討をSkillが担う。製品操作、欠陥修正、case/台帳の自動更新を行うrunnerは含まない。
