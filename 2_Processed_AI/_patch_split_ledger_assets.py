# -*- coding: utf-8 -*-
import json
from pathlib import Path

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
SCHEMA = ROOT / "Scripts" / "canonical_schema.json"
MD = ROOT / "Templates" / "Canonical_Data_Schema.md"
PROJECT = ROOT / r"1_Input_Raw\Shipments\EF-C26079-C04-36460  桌布-2026.7.10"
COMPARE = PROJECT / "拆单比对"
LEDGER_PATH = COMPARE / "split_ledger.json"

data = json.loads(SCHEMA.read_text(encoding="utf-8"))
arr = data["tiers"]["temporary_shipment"]
for key in ("remaining_strips", "remaining_cartons"):
    if key not in arr:
        idx = arr.index("split_batch_no") + 1
        arr.insert(idx, key)

ha = data.setdefault("header_aliases", {})
new_aliases = {
    "remaining_strips": ["剩余条数", "未发条数", "remaining_strips"],
    "remaining_cartons": ["剩余箱数", "未发箱数", "remaining_cartons"],
    "split_shipment": ["是否拆单", "拆单", "split_shipment"],
    "split_batch_no": ["拆单批次", "批次号", "split_batch_no"],
}
for k, v in new_aliases.items():
    ha[k] = v

SCHEMA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("A) canonical_schema.json patched")
i = arr.index("split_batch_no")
print("   slice:", arr[i:i+5])

text = MD.read_text(encoding="utf-8")
rows = [
    "| `remaining_strips` | 剩余条数 | number | 拆单账本累计 |",
    "| `remaining_cartons` | 剩余箱数 | number | 拆单账本累计 |",
]
if "remaining_strips" not in text:
    marker = "| `split_batch_no` | 拆单序号 | string | |"
    if marker not in text:
        raise SystemExit("split_batch_no row not found in MD")
    insert = "\n".join(rows) + "\n"
    text = text.replace(marker + "\n", marker + "\n" + insert, 1)
    MD.write_text(text, encoding="utf-8")
    print("B) Canonical_Data_Schema.md: added rows")
else:
    print("B) already had remaining_strips")

ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
plan_sc = ledger.get("plan", {}).get("by_size_color") or []
plan_fn = ledger.get("plan", {}).get("by_fnsku") or []

batch = {
    "batch_no": 1,
    "ship_date": "",
    "outbound_short": "",
    "note": "填写本批发货后另存为 batch_1_manifest.json，再执行 add-batch",
    "shipped_strips": 0,
    "shipped_cartons": 0,
    "by_size_color": [
        {"size": line.get("size", ""), "color": line.get("color", ""), "qty_strips": 0, "qty_cartons": 0}
        for line in plan_sc
    ],
    "by_fnsku": [
        {
            "size": line.get("size", ""),
            "color": line.get("color", ""),
            "strips_per_pack": line.get("strips_per_pack"),
            "fnsku": line.get("fnsku", ""),
            "qty_strips": 0,
            "qty_cartons": 0,
        }
        for line in plan_fn
    ],
    "warehouses": [{"warehouse_code": "", "cartons": 0, "strips": 0}],
}

tpl_json = COMPARE / "batch_1_TEMPLATE.json"
tpl_json.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

md_body = """# batch_1 填写说明

1. 复制 `batch_1_TEMPLATE.json` 为 `batch_1_manifest.json`（或直接改模板后另存）。
2. 按 **FBA 货件 / 实际出库** 填写顶栏、`by_size_color`、`by_fnsku`、`warehouses`（未发填 0）。
3. 保存后执行：

```powershell
python Scripts/07_split_shipment_ledger.py add-batch --project "%s" --batch-json "%s"
```

4. 脚本会更新 `split_ledger.json`、写入侧车 `batch_1_manifest.json`，并刷新 `_last_compare_report.md`。
""" % (PROJECT, COMPARE / "batch_1_manifest.json")
(COMPARE / "batch_1_TEMPLATE.md").write_text(md_body, encoding="utf-8")
print("C) batch templates written")

proj_path = PROJECT / "PROJECT.json"
proj = json.loads(proj_path.read_text(encoding="utf-8"))
changed = False
if proj.get("split_shipment") is not True:
    proj["split_shipment"] = True
    changed = True
ledger_abs = str(LEDGER_PATH.resolve())
if proj.get("split_ledger") != ledger_abs:
    proj["split_ledger"] = ledger_abs
    changed = True
if changed:
    proj_path.write_text(json.dumps(proj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("D) PROJECT.json updated")
else:
    print("D) PROJECT.json unchanged (already correct)")

print("ALL OK")
