# -*- coding: utf-8 -*-
"""按固定中文订单模板填空 → xlsx（页眉 E-fashion，不写畅选）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from .canonical import load_entity_rules

PROJECT = Path(__file__).resolve().parent.parent.parent
ORDER_DIR = PROJECT / "1_Input_Raw" / "01_Order_Outbound"
TEMPLATE_XLSX = PROJECT / "Templates" / "order_blank_zh.xlsx"


HEADER_COMPANY = "Xuchang E-fashion Electronic Business Co., Ltd."
HEADER_ADDR = (
    "Add: 7th Floor Building Two, E-commerce Industrial Park Furong Road, "
    "Rural Intergration Demonstration Area of Xuchang, henan, China"
)


def resolve_blank_template() -> Path:
    """优先 Templates/order_blank_zh.xlsx；若无则现场生成空白骨架。"""
    if TEMPLATE_XLSX.exists():
        return TEMPLATE_XLSX
    ensure_blank_template(TEMPLATE_XLSX)
    return TEMPLATE_XLSX


def ensure_blank_template(path: Path = TEMPLATE_XLSX) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["D1"] = HEADER_COMPANY
    ws["D2"] = HEADER_ADDR
    ws["D4"] = "TEL:      FAX:    E-MAIL:"
    ws["A6"] = "订单编号："
    ws["D6"] = "下单日期："
    ws["G6"] = "交货日期："
    # 订单明细头
    for col, h in enumerate(
        ["订单编号", "产品品类", "重量", "尺寸规格", "颜色", "数量", "备注"], 1
    ):
        ws.cell(7, col, h)
    ws["A12"] = "制单："
    ws["F12"] = "审核："
    ws["A13"] = "装 箱 单 明 细"
    for col, h in enumerate(
        [
            "尺寸规格",
            "颜色",
            "条数/包",
            "产品标签",
            "包数/箱",
            "总箱数",
            "总条数",
            "箱号",
            "内包装尺寸",
            "外箱尺寸（长*宽*高）",
        ],
        1,
    ):
        ws.cell(14, col, h)
    wb.save(path)
    return path


def _inner_display(row: dict) -> str:
    if row.get("pack_method") == "heat_shrink":
        return "热缩膜包装"
    if row.get("inner_pack_lwh_cm"):
        return f"内盒{row['inner_pack_lwh_cm']}"
    return ""


def _outer_display(row: dict) -> str:
    c = row.get("carton_lwh_cm")
    if not c:
        return ""
    return f"纸箱规格：{c}cm" if "cm" not in str(c).lower() else f"纸箱规格：{c}"


def fill_order_template(
    *,
    order_code: str,
    order_date: str | None,
    delivery_date: str | None,
    entity_code: str,
    lines: list[dict],
    out_path: Path | str,
) -> Path:
    """
    只填模板已有列；页眉固定 E-fashion（C04 不印畅选）。
    输出 xlsx。
    """
    rules = load_entity_rules()
    ent = rules.get("entities", {}).get(entity_code, {})
    brand = ent.get("brand_tablecloth") or lines[0].get("brand") if lines else ""

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    title_font = Font(bold=True, size=14)
    ws["D1"] = HEADER_COMPANY
    ws["D1"].font = title_font
    ws["D2"] = HEADER_ADDR
    ws["D4"] = "TEL:      FAX:    E-MAIL:"

    ws["A6"] = f"订单编号：{order_code}"
    ws["D6"] = "下单日期："
    ws["E6"] = order_date or ""
    ws["G6"] = f"交货日期：{delivery_date or ''}"

    headers = ["订单编号", "产品品类", "重量", "尺寸规格", "颜色", "数量", "备注"]
    for col, h in enumerate(headers, 1):
        ws.cell(8, col, h)

    # 订单明细：按 size+color 汇总 qty（lines 已是装箱行时再汇总）
    summary: dict[tuple, dict] = {}
    for ln in lines:
        k = (ln.get("size"), ln.get("color"))
        if k not in summary:
            summary[k] = {
                "size": ln.get("size"),
                "color": ln.get("color"),
                "gram_weight": ln.get("gram_weight"),
                "product_name_zh": ln.get("product_name_zh") or "单面磨毛纤维桌布",
                "qty_strips": 0,
            }
        summary[k]["qty_strips"] += float(ln.get("qty_strips") or 0)

    r = 9
    first = True
    total_strips = 0
    for (_sz, _cl), s in summary.items():
        qty = int(s["qty_strips"]) if s["qty_strips"] == int(s["qty_strips"]) else s["qty_strips"]
        total_strips += float(s["qty_strips"] or 0)
        if first:
            ws.cell(r, 1, order_code.rsplit("-", 1)[0] if order_code else "")
            # 短单号：EF-C26079-C04
            short = order_code
            m = __import__("re").match(r"(EF-[A-Z0-9]+-C0[47])", order_code or "", __import__("re").I)
            if m:
                short = m.group(1)
            ws.cell(r, 1, short)
            ws.cell(r, 2, s["product_name_zh"])
            ws.cell(r, 3, s.get("gram_weight") or "")
            first = False
        ws.cell(r, 4, s["size"])
        ws.cell(r, 5, s["color"])
        ws.cell(r, 6, qty)
        r += 1

    ws.cell(r, 1, "合   计")
    ws.cell(r, 6, int(total_strips) if total_strips == int(total_strips) else total_strips)
    r += 2
    ws.cell(r, 1, "制单：")
    ws.cell(r, 6, "审核：")
    r += 1
    ws.cell(r, 1, "装 箱 单 明 细")
    r += 1
    pack_headers = [
        "尺寸规格",
        "颜色",
        "条数/包",
        "产品标签",
        "包数/箱",
        "总箱数",
        "总条数",
        "箱号",
        "内包装尺寸",
        "外箱尺寸（长*宽*高）",
    ]
    for col, h in enumerate(pack_headers, 1):
        ws.cell(r, col, h)
    r += 1

    pack_total_cartons = 0
    pack_total_strips = 0
    for ln in lines:
        ws.cell(r, 1, ln.get("size") or "")
        ws.cell(r, 2, ln.get("color") or "")
        ws.cell(r, 3, ln.get("strips_per_pack") or "")
        ws.cell(r, 4, ln.get("fnsku") or "")
        ws.cell(r, 5, ln.get("packs_per_carton") or "")
        ws.cell(r, 6, ln.get("qty_cartons") or "")
        ws.cell(r, 7, ln.get("qty_strips") or "")
        ws.cell(r, 8, ln.get("carton_range") or "")
        ws.cell(r, 9, _inner_display(ln))
        ws.cell(r, 10, _outer_display(ln))
        pack_total_cartons += float(ln.get("qty_cartons") or 0)
        pack_total_strips += float(ln.get("qty_strips") or 0)
        r += 1

    ws.cell(r, 1, "合计")
    ws.cell(r, 6, int(pack_total_cartons) if pack_total_cartons == int(pack_total_cartons) else pack_total_cartons)
    ws.cell(r, 7, int(pack_total_strips) if pack_total_strips == int(pack_total_strips) else pack_total_strips)

    # 备注：品牌仅内部，不强制印页眉；可在备注列空置
    _ = brand

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
