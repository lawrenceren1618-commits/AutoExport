# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
import pandas as pd
import numpy as np

INPUT_RAW = Path(r"C:\Users\Administrator\.cursor\Cursor-projects\Order_Freight_Customs_Export\1_Input_Raw")
OUT_MD = Path(r"C:\Users\Administrator\.cursor\Cursor-projects\Order_Freight_Customs_Export\2_Processed_AI\Field_Mapping_Inventory.md")
OUT_JSON = Path(r"C:\Users\Administrator\.cursor\Cursor-projects\Order_Freight_Customs_Export\Scripts\field_correspondence.json")
PARSE_LOG = Path(r"C:\Users\Administrator\.cursor\Cursor-projects\Order_Freight_Customs_Export\2_Processed_AI\_parse_dump.json")

EXTRA_TEMPLATES = [
    Path(r"C:\Users\Administrator\Desktop\2026发货计划\5月发货计划\C26039-易尚  5.24发货 288箱\各仓点 C26039各5种产品下单模板.xlsx"),
    Path(r"C:\Users\Administrator\Desktop\2026发货计划\5月发货计划\C26037-易尚 5.17发货 400箱\各仓点 亚马逊5种产品下单模板.xlsx"),
    Path(r"C:\Users\Administrator\Desktop\2026发货计划\5月发货计划\C26036易  5.10发货 700箱-报关资料准备\模拟亚马逊5种产品下单模板.xlsx"),
]

TEMPLATES = [
    ("customs", Path(r"C:\Users\Administrator\Desktop\2026发货计划\215箱报关资料.xlsx"), 40),
    ("freight_forwarder", Path(r"C:\Users\Administrator\Desktop\2026发货计划\货代入库贴数据2026.6.18 易尚桌布 IUSW 215箱.xlsx"), 40),
    ("fba_first_leg", Path(r"C:\Users\Administrator\Downloads\导入头程物流单-V324.xlsx"), 40),
    ("fba_listing", Path(r"C:\Users\Administrator\Desktop\Super Browser\易尚\TABLECLOTH (1).xlsm"), 25),
]

KEYWORDS = [
    "订单", "订单号", "品名", "规格", "颜色", "尺寸", "条数", "克重", "箱数", "件数",
    "毛重", "净重", "体积", "单价", "金额", "供应商", "品牌", "公司", "FNSKU", "SKU",
    "ASIN", "数量", "总箱数", "报关", "货代", "仓库", "目的港", "收货人", "发货人",
    "海关", "HS", "编码", "材质", "成分", "包装", "每箱", "PCS", "CBM", "KG",
]

def cell_str(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    s = str(v).strip()
    return s

def df_to_rows(df, max_rows):
    rows = []
    for i in range(min(max_rows, len(df))):
        row = [cell_str(x) for x in df.iloc[i].tolist()]
        rows.append(row)
    return rows

def detect_headers(rows):
    found = []
    seen = set()
    for row in rows[:50]:
        for c in row:
            if not c:
                continue
            for kw in KEYWORDS:
                if kw in c and c not in seen:
                    seen.add(c)
                    found.append(c)
            if len(c) <= 30 and re.search(r"[\u4e00-\u9fff]", c):
                if any(k in c for k in KEYWORDS) or c.endswith("：") or c.endswith(":"):
                    if c not in seen:
                        seen.add(c)
                        found.append(c)
    return found

def detect_labels_in_sheet(rows):
    labels = set()
    for row in rows:
        for c in row:
            if not c:
                continue
            for kw in KEYWORDS:
                if kw in c:
                    labels.add(kw)
            if re.match(r"^[\u4e00-\u9fffA-Za-z0-9（）()\-/\.]{1,20}[:：]$", c):
                labels.add(c.rstrip(":："))
    return sorted(labels)

def read_workbook(path, max_rows_main=45):
    path = Path(path)
    info = {"path": str(path), "filename": path.name, "exists": path.exists(), "sheets": {}}
    if not path.exists():
        return info
    ext = path.suffix.lower()
    engine = None
    if ext == ".xls":
        engine = "xlrd"
    elif ext == ".xlsm":
        engine = "openpyxl"
    try:
        xl = pd.ExcelFile(path, engine=engine)
    except Exception as e:
        info["error"] = str(e)
        return info
    info["sheet_names"] = xl.sheet_names
    for sn in xl.sheet_names:
        try:
            df = pd.read_excel(xl, sheet_name=sn, header=None, dtype=object)
        except Exception as e:
            info["sheets"][sn] = {"error": str(e)}
            continue
        nrows = min(max_rows_main, len(df))
        rows = df_to_rows(df, nrows)
        info["sheets"][sn] = {
            "shape": [int(df.shape[0]), int(df.shape[1])],
            "rows_preview": rows,
            "detected_headers": detect_headers(rows),
            "keyword_labels": detect_labels_in_sheet(rows),
        }
    return info

def pick_main_sheets(sheet_names):
    if not sheet_names:
        return []
    # prefer sheets with 明细/订单/Sheet1/data
    priority = []
    for sn in sheet_names:
        sl = sn.lower()
        score = 0
        if "明细" in sn or "订单" in sn or "出货" in sn:
            score += 3
        if sn == "Sheet1" or sn.startswith("Sheet"):
            score += 1
        if "汇总" in sn or "说明" in sn or "模板" in sn:
            score -= 1
        priority.append((score, sn))
    priority.sort(key=lambda x: (-x[0], sheet_names.index(x[1])))
    main = [priority[0][1]]
    if len(priority) > 1 and priority[1][0] == priority[0][0]:
        main.append(priority[1][1])
    return main[:2]

def extract_order_codes(filename):
    m = re.findall(r"EF-C\d{5}[A-Z]?", filename, re.I)
    m2 = re.findall(r"C260\d{2,3}", filename, re.I)
    return list(dict.fromkeys(m + m2))

# --- parse all ---
dump = {"factory_orders": [], "templates": [], "extra_templates": []}

for p in sorted(INPUT_RAW.glob("*.xls")):
    rec = read_workbook(p, 45)
    rec["doc_type"] = "factory_order"
    rec["order_codes"] = extract_order_codes(p.name)
    rec["main_sheets"] = pick_main_sheets(rec.get("sheet_names", []))
    dump["factory_orders"].append(rec)

for doc_type, p, nrows in TEMPLATES:
    rec = read_workbook(p, nrows)
    rec["doc_type"] = doc_type
    rec["main_sheets"] = pick_main_sheets(rec.get("sheet_names", []))
    dump["templates"].append(rec)

for p in EXTRA_TEMPLATES:
    if p.exists():
        rec = read_workbook(p, 35)
        rec["doc_type"] = "freight_forwarder"
        rec["main_sheets"] = pick_main_sheets(rec.get("sheet_names", []))
        dump["extra_templates"].append(rec)

PARSE_LOG.parent.mkdir(parents=True, exist_ok=True)
with open(PARSE_LOG, "w", encoding="utf-8") as f:
    json.dump(dump, f, ensure_ascii=False, indent=2)

print("PARSED", len(dump["factory_orders"]), "factory", len(dump["templates"]), "templates", len(dump["extra_templates"]), "extra")
print("LOG", PARSE_LOG)
