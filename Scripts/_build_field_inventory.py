# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
import pandas as pd
import numpy as np

INPUT_RAW = Path(r"C:\Users\Administrator\.cursor\Cursor-projects\Order_Freight_Customs_Export\1_Input_Raw")
OUT_MD = Path(r"C:\Users\Administrator\.cursor\Cursor-projects\Order_Freight_Customs_Export\2_Processed_AI\Field_Mapping_Inventory.md")
OUT_JSON = Path(r"C:\Users\Administrator\.cursor\Cursor-projects\Order_Freight_Customs_Export\Scripts\field_correspondence.json")
PARSE_LOG = Path(r"C:\Users\Administrator\.cursor\Cursor-projects\Order_Freight_Customs_Export\2_Processed_AI\_parse_dump.json")

TEMPLATES = [
    ("customs", Path(r"C:\Users\Administrator\Desktop\2026发货计划\215箱报关资料.xlsx"), {"报关地": 45, "发票": 30, "装箱单": 30}),
    ("freight_forwarder", Path(r"C:\Users\Administrator\Desktop\2026发货计划\货代入库贴数据2026.6.18 易尚桌布 IUSW 215箱.xlsx"), {"下单模板": 10, "收货数据": 40, "商品数据": 40}),
    ("fba_first_leg", Path(r"C:\Users\Administrator\Downloads\导入头程物流单-V324.xlsx"), {"头程物流": 5, "明细数据": 40}),
    ("fba_listing", Path(r"C:\Users\Administrator\Desktop\Super Browser\易尚\TABLECLOTH (1).xlsm"), {"Template": 25}),
]

EXTRA_GLOB_ROOT = Path(r"C:\Users\Administrator\Desktop\2026发货计划")

KEYWORDS = [
    "订单", "订单号", "品名", "规格", "颜色", "尺寸", "条数", "克重", "箱数", "件数",
    "毛重", "净重", "体积", "单价", "金额", "供应商", "品牌", "公司", "FNSKU", "SKU",
    "ASIN", "数量", "总箱数", "报关", "货代", "仓库", "目的港", "收货人", "发货人",
    "海关", "HS", "编码", "材质", "成分", "包装", "每箱", "PCS", "CBM", "KG", "布料",
    "下单", "出货", "备货", "备注", "箱规", "净重", "毛重",
]

def cell_str(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    return str(v).strip().replace("\r\n", "\\n").replace("\n", "\\n")

def read_sheet(path, sheet, nrows, engine=None):
    df = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object, nrows=nrows, engine=engine)
    return [[cell_str(x) for x in row] for row in df.values.tolist()]

def engine_for(path):
    ext = path.suffix.lower()
    if ext == ".xls":
        return "xlrd"
    if ext == ".xlsm":
        return "openpyxl"
    return None

def detect_headers(rows):
    found, seen = [], set()
    for row in rows[:50]:
        for c in row:
            if not c or c in seen:
                continue
            if any(kw in c for kw in KEYWORDS) or (re.search(r"[\u4e00-\u9fff]", c) and (c.endswith("：") or c.endswith(":"))):
                seen.add(c)
                found.append(c)
    return found

def keyword_labels(rows):
    labels = set()
    for row in rows:
        for c in row:
            if not c:
                continue
            for kw in KEYWORDS:
                if kw in c:
                    labels.add(kw)
    return sorted(labels)

def find_header_row(rows):
    """Return index of likely column header row."""
    best_i, best_score = None, 0
    for i, row in enumerate(rows[:30]):
        score = sum(1 for c in row if c and any(k in c for k in ["尺寸", "颜色", "数量", "条数", "箱数", "品名", "规格", "克重", "Order", "CTN", "QTY", "WEIGHT"]))
        if score > best_score:
            best_score, best_i = score, i
    return best_i

def columns_from_row(row):
    return [c for c in row if c]

def parse_factory(path):
    eng = engine_for(path)
    xl = pd.ExcelFile(path, engine=eng)
    out = {"filename": path.name, "path": str(path), "sheet_names": xl.sheet_names, "sheets": {}}
    for sn in xl.sheet_names:
        rows = read_sheet(path, sn, 45, eng)
        hr = find_header_row(rows)
        cols = columns_from_row(rows[hr]) if hr is not None else []
        out["sheets"][sn] = {
            "rows_preview": rows,
            "detected_headers": detect_headers(rows),
            "keyword_labels": keyword_labels(rows),
            "header_row_index": hr,
            "header_columns": cols,
        }
    return out

def parse_multi(path, sheet_rows: dict):
    eng = engine_for(path)
    xl = pd.ExcelFile(path, engine=eng)
    out = {"filename": path.name, "path": str(path), "sheet_names": xl.sheet_names, "sheets": {}}
    for sn, n in sheet_rows.items():
        if sn not in xl.sheet_names:
            continue
        rows = read_sheet(path, sn, n, eng)
        hr = find_header_row(rows)
        out["sheets"][sn] = {
            "rows_preview": rows,
            "detected_headers": detect_headers(rows),
            "keyword_labels": keyword_labels(rows),
            "header_row_index": hr,
            "header_columns": columns_from_row(rows[hr]) if hr is not None else [],
        }
    return out

# extra templates
extras = []
for p in EXTRA_GLOB_ROOT.rglob("*"):
    if p.suffix.lower() not in (".xlsx", ".xlsm"):
        continue
    if "下单模板" in p.name or ("货代" in p.name and "入库" in p.name):
        extras.append(p)
extras = sorted(set(extras), key=lambda x: x.stat().st_mtime, reverse=True)[:3]

dump = {
    "factory_orders": [parse_factory(p) for p in sorted(INPUT_RAW.glob("*.xls"))],
    "templates": [],
    "extra_templates": [],
}
for doc_type, path, sheets in TEMPLATES:
    rec = parse_multi(path, sheets)
    rec["doc_type"] = doc_type
    dump["templates"].append(rec)
for p in extras:
    rec = parse_multi(p, {"下单模板": 10, "收货数据": 40, "商品数据": 40, "Sheet1": 40})
    rec["doc_type"] = "freight_forwarder"
    dump["extra_templates"].append(rec)

with open(PARSE_LOG, "w", encoding="utf-8") as f:
    json.dump(dump, f, ensure_ascii=False, indent=2)

# --- build markdown + json ---
md = []
md.append("# 字段映射与模板清单（Field Mapping Inventory）")
md.append("")
md.append("> 自动生成：解析 `1_Input_Raw` 工厂 `.xls` 及 Desktop/Downloads 样本模板。")
md.append("")

# A 文件归类
md.append("## A. 文件归类")
md.append("")
md.append("| 类型 | 代表文件 | 用途 |")
md.append("|------|----------|------|")
md.append("| 工厂订单 | `1_Input_Raw/*.xls`（EF-C26xxx） | 备货/生产：颜色×尺寸×条数、箱规、毛净重、交期 |")
md.append("| 货代入库下单 | `货代入库贴数据*.xlsx`、各仓「下单模板」 | 按 FBA 仓/收货地址填 SKU、箱数、贴标数据 |")
md.append("| 报关 | `*报关资料.xlsx`（多 Sheet：报关地/发票/装箱单/合同） | 海关申报：HS、品名、数量、毛净重、金额、贸易国 |")
md.append("| FBA 头程 | `导入头程物流单-V324.xlsx` | ERP 头程：物流方式、计费重、费用（**待仓库/运单回填**） |")
md.append("| 亚马逊 listing 模板 | `TABLECLOTH (1).xlsm` | 商品属性/FNSKU 维度（**非出货单**，供 SKU 对照） |")
md.append("| 其他 | 利润/广告/标签 PDF 等 | 不参与本流水线字段映射 |")
md.append("")

# Per-file parse appendix
md.append("## 附录：逐文件解析摘要")
md.append("")

for fo in dump["factory_orders"]:
    md.append(f"### 工厂订单：`{fo['filename']}`")
    md.append(f"- **Sheet**：{', '.join(fo['sheet_names'])}")
    sn = fo["sheet_names"][0]
    sh = fo["sheets"][sn]
    md.append(f"- **表头行（0-based）**：{sh['header_row_index']} → `{sh['header_columns']}`")
    md.append(f"- **检出标签/关键词**：{', '.join(sh['keyword_labels'])}")
    md.append(f"- **非空字段标签（detected_headers 节选）**：")
    for h in sh["detected_headers"][:30]:
        md.append(f"  - {h}")
    md.append("")
    md.append("<details><summary>前 45 行（header=None，全列）</summary>")
    md.append("")
    md.append("```")
    for i, row in enumerate(sh["rows_preview"]):
        md.append(f"R{i:02d}: " + " | ".join(row))
    md.append("```")
    md.append("</details>")
    md.append("")

for group_name, items in [("样本模板", dump["templates"]), ("补充货代模板", dump["extra_templates"])]:
    for rec in items:
        md.append(f"### {group_name}：`{rec['filename']}`（{rec.get('doc_type','')}）")
        md.append(f"- **Sheet**：{', '.join(rec['sheet_names'])}")
        for sn, sh in rec["sheets"].items():
            md.append(f"- **Sheet `{sn}`** 表头行 {sh['header_row_index']}：`{sh['header_columns'][:20]}`")
            md.append(f"  - 关键词：{', '.join(sh['keyword_labels'])}")
        md.append("")
        main_sn = next(iter(rec["sheets"]))
        sh = rec["sheets"][main_sn]
        md.append("```")
        for i, row in enumerate(sh["rows_preview"][:40]):
            if any(row):
                md.append(f"R{i:02d}: " + " | ".join(row))
        md.append("```")
        md.append("")

# B 必填字段 - derive from analysis
factory_cols_new = ["订单编号", "商品品牌", "布料", "尺寸项", "颜色", "数量", "备注", "审核", "条数/箱", "总箱数", "总条数", "内包装尺寸", "外箱尺寸（长*宽*高）", "包装方式"]
factory_cols_old = ["Order", "Description", "Size", "Color", "QTY/条", "CTNS/箱", "N.W.", "G.W.", "CBM", "包装尺寸", "外箱尺寸"]
freight_cols = ["FBA仓库", "收货地址", "SKU", "FNSKU", "ASIN", "品名", "每箱数量", "箱数", "总件数", "毛重", "净重", "体积", "贴标要求"]
customs_cols = ["项号", "商品编号(HS)", "商品名称及规格型号", "数量及单位", "单价/总价/币制", "原产国", "最终目的国", "境内货源地", "毛重(KG)", "净重(KG)", "件数", "合同协议号", "贸易国", "运抵国", "指运港"]

md.append("## B. 各表必填字段清单（仅列实际用到的列）")
md.append("")
md.append("### 1）工厂订单 `.xls`（Sheet1）")
md.append("")
md.append("**新版表头（如 EF-C26079、EF-C26055A）**")
md.append("")
for c in factory_cols_new:
    md.append(f"- {c}")
md.append("")
md.append("**旧版表头（如 EF-C26039/40，含英文 Order 行）**")
md.append("")
for c in factory_cols_old:
    md.append(f"- {c}")
md.append("")
md.append("共性必填：订单号 `EF-Cxxxxx`、总数量（PCS/条）、交期（下单/出货日期）、分色分码数量明细、箱规与外箱尺寸、包装方式、总箱数/总毛净重/总体积（多在明细区或汇总行）。")
md.append("")
md.append("### 2）货代入库贴 / 下单模板 `.xlsx`")
md.append("")
md.append("- **下单模板** Sheet：货代名称、联系人（结构行，非明细）")
md.append("- **收货数据** / **商品数据** Sheet（同名文件不同版本）：FBA 仓代码、Shipment ID、地址、SKU/FNSKU、单箱件数、箱数、总数量、外箱尺寸、毛净重、体积（以实际 Sheet 表头为准；本样本「215箱」文件主数据可能在其他工作簿副本）")
for c in freight_cols:
    md.append(f"- {c}")
md.append("")
md.append("### 3）报关资料 `.xlsx`")
md.append("")
md.append("- **报关地** Sheet：收发货人、贸易方式、合同号、包装种类、件数、毛净重、成交方式、明细行（HS/品名/数量/金额/原产国/目的国）")
for c in customs_cols:
    md.append(f"- {c}")
md.append("- **发票 / 装箱单 / 合同 / 委托协议**：与报关地共享合同号、品名、数量、金额、毛净重、件数（多 Sheet 联动）")
md.append("")
md.append("### 4）FBA 头程 `导入头程物流单-V324.xlsx`")
md.append("")
md.append("- **头程物流**：物流方式、计费重 KG、体积 CMB、费用字段（导入说明行 + 列名）")
md.append("- **明细数据**：与 ERP 出库/货件关联（需运单生成后填写）→ **deferred**")
md.append("")
md.append("### 5）TABLECLOTH `.xlsm`")
md.append("")
md.append("- **Template** Sheet：Amazon 商品属性列（feed 模板），含 SKU、品牌、尺寸、颜色等 listing 字段；**不直接用于工厂/货代箱单**。")
md.append("")

# C 对应关系
md.append("## C. 字段对应关系主表")
md.append("")
md.append("说明：`source_shipment_plan` 为从工厂订单提炼的统一语义；报关 / FBA 入库在获得仓库与货件号后再处理。")
md.append("")
md.append("| 源字段（source_shipment_plan） | 工厂订单 `.xls` 列 | 货代入库/下单 `.xlsx` 列 | 报关 `.xlsx` | FBA/亚马逊 |")
md.append("|-------------------------------|-------------------|-------------------------|-------------|------------|")
mapping_rows = [
    ("order_code", "订单编号 / 订单号 EF-C…", "合同号/货件备注（间接）", "合同协议号", "deferred"),
    ("company_name", "页眉公司英文名", "—", "发货人/生产销售单位", "deferred"),
    ("brand", "商品品牌", "品牌/SKU 属性", "—", "Template.brand"),
    ("fabric_spec", "布料（如 90克/平纹单面磨毛）", "品名/描述", "商品名称及规格型号", "deferred"),
    ("color", "颜色", "Color/颜色", "规格型号内颜色段", "deferred"),
    ("size", "尺寸项 / Size", "Size/尺寸", "规格型号内尺寸段", "deferred"),
    ("strip_count", "数量 / QTY（条）", "总件数/数量", "数量及单位（条/PCS）", "deferred"),
    ("strip_per_carton", "条数/箱", "每箱数量", "—", "deferred"),
    ("cartons", "总箱数 / CTNS", "箱数", "件数（箱）", "deferred"),
    ("gram_weight", "布料克重（90克…）", "—", "规格型号克重段", "deferred"),
    ("inner_pack_size", "内包装尺寸", "—", "—", "deferred"),
    ("carton_size", "外箱尺寸", "外箱尺寸", "—", "deferred"),
    ("pack_method", "包装方式", "—", "包装种类", "deferred"),
    ("gross_weight_kg", "毛重 / G.W.", "毛重", "毛重(KG)", "deferred"),
    ("net_weight_kg", "净重 / N.W.", "净重", "净重(KG)", "deferred"),
    ("volume_cbm", "体积 / CBM", "体积", "—", "deferred"),
    ("unit_price", "—（工厂表未见）", "—", "单价/总价", "**脱敏**"),
    ("amount", "—", "—", "总价/金额", "**脱敏**"),
    ("supplier", "页眉工厂/制单（许昌…）", "—", "境内货源地", "**脱敏→别名**"),
    ("fnsku / sku", "—", "FNSKU/SKU", "—", "Template.SKU/FNSKU"),
    ("hs_code", "—", "—", "商品编号 6302539090（桌布默认）", "deferred"),
]
for row in mapping_rows:
    md.append("| " + " | ".join(row) + " |")
md.append("")
md.append("**报关与亚马逊入库**：标注为「待仓库/货件信息（Shipment ID、FBA 仓、入库结果）后处理」，脚本阶段 `deferred: true`。")
md.append("")

# D naming
md.append("## D. 订单命名/编码规律（从现有文件）")
md.append("")
md.append("- **EF-C260xx[-字母]-Cyy-NNNNN PCS**：`EF` 前缀 + 批次 `C26039` 等 + 子批 `-C07`/`-C04` + 总数量 + 品名（桌布/tablecloth）。")
md.append("- **字母后缀**：如 `EF-C26055A` 表示同系列改单/分单（文件名「改(3)」）。")
md.append("- **Desktop 发货计划文件夹**：`C26039-易尚 5.24发货 288箱` → 内部订单号 + 客户/品牌 + 发货日 + 总箱数。")
md.append("- **报关合同号**：可与 EF 号或内部简码对应（样本 `EF-C26065-IUSW`）。")
md.append("- **货代文件名**：`货代入库贴数据 + 日期 + 品牌 + FBA仓 + 箱数`。")
md.append("")

# E 脱敏
md.append("## E. 脱敏注意点")
md.append("")
md.append("- **不得进入 `2_Processed_AI` 明文**：采购单价、底价、成本、真实供应商全称（映射为 `SUPPLIER_001` 等）。")
md.append("- 报关**申报金额**与内部利润测算分离；汇率内部默认 **6.8** 仅作利润参考。")
md.append("- 工厂 `.xls` 页眉含真实公司英文地址 → 脱敏时保留订单结构，公司/地址走 `mapping_dict.json`。")
md.append("- 货代/ERP 模板可能含手机号、货代底价列 → 清洗后再给 AI。")
md.append("- 每条 SKU/行保留 **是否退税**（是/否），不可默认。")
md.append("")

OUT_MD.parent.mkdir(parents=True, exist_ok=True)
OUT_MD.write_text("\n".join(md), encoding="utf-8")

# JSON schema
json_obj = {
    "version": "1.0",
    "generated_from": [str(p) for p in INPUT_RAW.glob("*.xls")] + [str(t[1]) for t in TEMPLATES],
    "document_types": {
        "factory_order": {
            "category": "工厂订单",
            "file_pattern": "1_Input_Raw/EF-C*.xls",
            "required_fields": factory_cols_new,
            "legacy_required_fields": factory_cols_old,
        },
        "freight_forwarder": {
            "category": "货代入库下单",
            "required_fields": freight_cols,
            "sheets": ["下单模板", "收货数据", "商品数据"],
        },
        "customs": {
            "category": "报关",
            "required_fields": customs_cols,
            "sheets": ["报关地", "发票", "装箱单", "合同", "委托协议"],
            "deferred": True,
            "deferred_reason": "待仓库/货件/申报货值确认后处理",
        },
        "fba_first_leg": {
            "category": "FBA头程",
            "required_fields": ["物流方式", "计费重KG", "体积CMB", "费用"],
            "deferred": True,
            "deferred_reason": "待头程运单与ERP回填",
        },
        "fba_listing_template": {
            "category": "亚马逊listing",
            "file_example": "TABLECLOTH (1).xlsm",
            "deferred": True,
        },
    },
    "source_shipment_plan": {
        "description": "从工厂订单行项目抽象的统一字段",
        "fields": [
            "order_code", "company_name", "brand", "fabric_spec", "color", "size",
            "strip_count", "strip_per_carton", "cartons", "gram_weight",
            "inner_pack_size", "carton_size", "pack_method",
            "gross_weight_kg", "net_weight_kg", "volume_cbm",
        ],
    },
    "mappings": {
        "to_factory_order": {
            "order_code": "订单编号",
            "brand": "商品品牌",
            "fabric_spec": "布料",
            "color": "颜色",
            "size": "尺寸项",
            "strip_count": "数量",
            "strip_per_carton": "条数/箱",
            "cartons": "总箱数",
            "gram_weight": "布料(克重文案)",
            "inner_pack_size": "内包装尺寸",
            "carton_size": "外箱尺寸（长*宽*高）",
            "pack_method": "包装方式",
            "gross_weight_kg": "毛重",
            "net_weight_kg": "净重",
            "volume_cbm": "体积",
        },
        "to_freight_forwarder": {
            "color": "颜色",
            "size": "尺寸",
            "strip_count": "总件数/数量",
            "strip_per_carton": "每箱数量",
            "cartons": "箱数",
            "carton_size": "外箱尺寸",
            "gross_weight_kg": "毛重",
            "net_weight_kg": "净重",
            "volume_cbm": "体积",
            "fnsku": "FNSKU",
            "sku": "SKU",
        },
        "to_customs": {"deferred": True},
        "to_fba_inbound": {"deferred": True},
    },
    "sensitive_fields": ["unit_price", "amount", "supplier", "cost", "purchase_price"],
    "order_code_patterns": ["EF-C\\d{5}[A-Z]?-C\\d{2}-\\d+\\s*PCS", "C260\\d{2,3}"],
    "parsed_files": {
        "factory_count": len(dump["factory_orders"]),
        "template_count": len(dump["templates"]),
        "extra_freight_count": len(dump["extra_templates"]),
    },
}

OUT_JSON.write_text(json.dumps(json_obj, ensure_ascii=False, indent=2), encoding="utf-8")
print("WROTE", OUT_MD, OUT_JSON)
print("EXTRA", [p.name for p in extras])
