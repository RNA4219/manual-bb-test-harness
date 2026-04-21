# Evaluation Rubric

Skill 出力を forward-test した後、この rubric で採点する。

## Score Bands

| score | meaning |
|---:|---|
| 5 | 実務投入できる。重要な抜けがなく、根拠と判断が明確 |
| 4 | 軽微な補足で使える。主要観点と gate 判断は妥当 |
| 3 | 骨格はあるがレビューで手直しが必要 |
| 2 | 重要観点や oracle が抜け、実務投入には危険 |
| 1 | 仕様の言い換えに近く、テスト設計になっていない |

## Rubric

| category | weight | checks |
|---|---:|---|
| Coverage model | 20 | data/rule/state/role/regression/quality lens が cases より先に出ている |
| Observation quality | 15 | 観点が source_ref または assumption に紐づき、mandatory/optional が分かる |
| Risk quality | 15 | impact/likelihood/modifier の根拠があり、P0/P1 の乱発がない |
| Manual cases | 20 | scripted case に oracle refs、observable expected、trace_to、工数がある |
| Exploratory charters | 10 | oracle が薄い領域を scope/questions/timebox 付きで切り出している |
| Gate decision | 15 | automation/manual/defect/residual risk/waiver を分けて判断している |
| Communication | 5 | Go/No-Go brief が短く、意思決定に使える |

## Pass Rule

- 合計 80 点以上で pass。
- 70-79 点は conditional pass。Skill または domain pack 改善候補を記録する。
- 69 点以下は fail。golden expected を直接直すのではなく、Skill 本体か references を改善する。

## Automatic Fail Conditions

- Coverage model が出ない。
- P0/P1 の scripted case に oracle refs がない。
- Gate が coverage 数値だけで Go になる。
- 権限 feature で ownership context がない。
- stateful feature で invalid transition がない。
- 重大な不足情報があるのに `ok` または `go` になる。
