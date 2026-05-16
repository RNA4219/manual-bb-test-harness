# exports/

このディレクトリには、外部ツール連携用 export の生成例を置く。

| file | producer | purpose |
|---|---|---|
| `testrail-order-cancel.csv` | `scripts/export-testrail.py` | TestRail import 例 |
| `xray-order-cancel.json` | `scripts/export-xray.py` | Xray import 例 |

## 再生成例

```powershell
uv run python .\scripts\export-testrail.py --input .\examples\artifacts\order-cancel.manual_case_set.json --format csv --output .\exports\testrail-order-cancel.csv
uv run python .\scripts\export-xray.py --input .\examples\artifacts\order-cancel.manual_case_set.json --output .\exports\xray-order-cancel.json
```
