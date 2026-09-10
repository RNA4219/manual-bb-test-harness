# 生成効率・実行証跡版の検収

対象: [spec-05](../specs/spec-05-efficient-generation-evidence-revisions.md)。ユーザー指示に従い仕様を作成してから実装した。前段のISTQB拡張の未コミット差分は保持している。

実装:

- compact既定、未被覆義務と関連モデルへの入力絞り込み、必要な補完の省略、レビューの差分適用。
- 初段の事前見積もり、runで共有する予算、修復・失敗を含むusage集計。欠測はnull、予算停止はモデルを追加呼出せずfailed manifestを保存。
- ケース本文とモデルのhashを実行証跡と照合。旧ケースはlegacy_unverified、非破壊bind-casesを追加。
- 同じfixture・profileでfull/compactを順次比較し、失敗・欠測を削減率に変換しない比較コマンド。

実モデル比較はQwen3.6-27B UD-Q4_K_XL、llama.cpp、context 32768、qwen36 profile、thinking無効、timeout 600秒で実施した。出力上限は同じprofileを使い、予算は未指定。入力はorder-cancel。試行ログは[比較結果](evidence/efficiency-20260910/comparison.json)、[full manifest](evidence/efficiency-20260910/full.local_run_manifest.json)、[compact manifest](evidence/efficiency-20260910/compact.local_run_manifest.json)。今回起動したサーバーは検証後に停止した。

| モード | 生成結果 | 入力tokens | 出力tokens | 総tokens | 呼出／修復 | 秒 |
|---|---|---:|---:|---:|---:|---:|
| full | ケース生成時のJSON不正 | 15,337 | 13,342 | 28,679 | 6／2 | 499.987 |
| compact | モデル生成時のJSON不正 | 836 | 3,500 | 4,336 | 1／0 | 107.923 |

両方とも出力上限に達した呼出でJSON解析が失敗した。生成完了・被覆比較が成立していないため**削減率はnull、9-runは未実施**。早い段階で止まったcompactを省トークンの成功例と解釈しない。構造・被覆の成功率も0/2。独立した意味的品質採点は未実施。

試行中に比較サマリのschema_validが「途中まで保存したartifactの妥当性」を示していたため、完成したrunだけtrueとするよう修正し、manifestから再集計した。生のmanifestは保持した。JSON不正のusageは既に計上できており、結果分類も現実装ではjson_parse_errorに分けた。

検証:

- 追加63件: 予算境界・修復停止・usage欠測／不正・JSON解析失敗・通信失敗、差分の未知／重複ID、必要な被覆が揃った際の補完省略、ケース／モデル差、旧形式、CLI、比較失敗を確認。
- 全体898件成功（107.04秒）。分岐を含むcoverage 87.07%（閾値85%）。ruff、仕様書5件、workflow-cookbook freshness、schema mirrorも成功。
- Gate専用103件成功、branchを含むcoverage 90.94%（閾値90%）。
- wheel／sdist smoke成功。bind-casesとネットワーク不要のestimate-onlyを配布環境で実行。
- schema例26件＋合成証跡3件成功。root／package schemaを同期。Skillの3種類のvalidator成功。

残る評価課題: 大きな型付きモデルやケース集合を、出力上限内で完結する単位に分けて生成すること。今回の予算・差分・版照合機能の回帰検証と、実LLMの生成品質受入は別に扱う。上限を無条件に増やさず、分割生成と継続条件を仕様化した上で再比較する。
