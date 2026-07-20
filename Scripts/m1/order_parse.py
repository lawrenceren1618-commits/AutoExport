# -*- coding: utf-8 -*-
"""解析 01_Order_Outbound 固定订单模板（中文备货+装箱明细 / 旧英文 Order）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .canonical import (
    enrich_row,
    normalize_entity_code,
    normalize_gram_weight,
    normalize_pack_method,
    normalize_size,
    to_date_str,
    to_num,
)


def _cell(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def extract_order_meta(df: pd.DataFrame) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "order_code": None,
        "order_date": None,
        "delivery_date": None,
        "entity_code": None,
        "header_company": None,
    }
    # scan first 15 rows for labels
    for i in range(min(15, len(df))):
        for j, raw in enumerate(df.iloc[i].tolist()):
            s = _cell(raw)
            if not s:
                continue
            if "Xuchang E-fashion" in s or "E-fashion" in s:
                meta["header_company"] = s
            m_code = re.search(r"(EF-[A-Z0-9\-]+)", s, re.I)
            if ("订单编号" in s or "订单号" in s) and m_code:
                meta["order_code"] = m_code.group(1)
            if s.startswith("EF-") and "PCS" in s.upper():
                meta["order_code"] = meta["order_code"] or s.split()[0]
            if "下单日期" in s:
                # date may be same cell or next cells
                dm = re.search(r"下单日期[：:]\s*([0-9./\-]+)", s)
                if dm:
                    meta["order_date"] = to_date_str(dm.group(1))
                else:
                    for k in range(j + 1, min(j + 4, len(df.columns))):
                        ns = _cell(df.iloc[i, k])
                        if re.search(r"\d{4}", ns):
                            meta["order_date"] = to_date_str(ns)
                            break
            if "交货日期" in s:
                dm = re.search(r"交货日期[：:]\s*([0-9./\-]+)", s)
                if dm:
                    meta["delivery_date"] = to_date_str(dm.group(1))
            if "订单编号：" in s and m_code:
                meta["order_code"] = m_code.group(1)

    # QTY / 订单编号行（英文旧表）
    for i in range(min(15, len(df))):
        row = [_cell(x) for x in df.iloc[i].tolist()]
        joined = " ".join(row)
        m = re.search(r"(EF-[A-Z0-9\-]+PCS)", joined, re.I)
        if m and not meta["order_code"]:
            meta["order_code"] = m.group(1)
        m2 = re.search(r"订单编号[：:]\s*(EF-[A-Z0-9\-]+)", joined, re.I)
        if m2:
            meta["order_code"] = m2.group(1)
        m3 = re.search(r"下单日期[：:]\s*([0-9./\-]+)", joined)
        if m3:
            meta["order_date"] = to_date_str(m3.group(1))

    if meta["order_code"]:
        meta["entity_code"] = normalize_entity_code(meta["order_code"])
    return meta


def _find_row_containing(df: pd.DataFrame, text: str) -> int | None:
    for i in range(len(df)):
        for v in df.iloc[i].tolist():
            if text in _cell(v).replace(" ", ""):
                return i
    return None


def _parse_chinese_packing(df: pd.DataFrame, meta: dict) -> list[dict]:
    hdr_i = _find_row_containing(df, "条数/包")
    if hdr_i is None:
        return []
    headers = [_cell(x).replace(" ", "") for x in df.iloc[hdr_i].tolist()]
    col = {h: i for i, h in enumerate(headers) if h}

    def col_get(*names: str) -> int | None:
        for n in names:
            if n in col:
                return col[n]
        return None

    i_size = col_get("尺寸规格", "尺寸")
    i_color = col_get("颜色", "颜 色")
    i_spp = col_get("条数/包")
    i_fnsku = col_get("产品标签", "FNSKU")
    i_ppc = col_get("包数/箱")
    i_cartons = col_get("总箱数")
    i_strips = col_get("总条数")
    i_inner = col_get("内包装尺寸")
    i_outer = col_get("外箱尺寸（长*宽*高）", "外箱尺寸")

    # gram from order section
    gram = None
    for i in range(min(20, len(df))):
        for v in df.iloc[i].tolist():
            s = _cell(v)
            if "克" in s or re.search(r"\d+G", s, re.I):
                g = normalize_gram_weight(s)
                if g:
                    gram = g
                    break

    rows: list[dict] = []
    for i in range(hdr_i + 1, len(df)):
        vals = [_cell(x) for x in df.iloc[i].tolist()]
        if not any(vals):
            continue
        if "合计" in vals[0] or "合 计" in "".join(vals):
            break
        size = vals[i_size] if i_size is not None else ""
        color = vals[i_color] if i_color is not None else ""
        if not size and not color:
            continue
        # forward-fill size from previous
        if not size and rows:
            size = rows[-1].get("_raw_size") or ""
        row = {
            "order_code": meta.get("order_code"),
            "order_date": meta.get("order_date"),
            "entity_code": meta.get("entity_code"),
            "size": normalize_size(size),
            "color": color,
            "gram_weight": gram,
            "strips_per_pack": to_num(vals[i_spp]) if i_spp is not None else None,
            "fnsku": vals[i_fnsku] if i_fnsku is not None else None,
            "packs_per_carton": to_num(vals[i_ppc]) if i_ppc is not None else None,
            "qty_cartons": to_num(vals[i_cartons]) if i_cartons is not None else None,
            "qty_strips": to_num(vals[i_strips]) if i_strips is not None else None,
            "inner_pack_lwh_cm": vals[i_inner] if i_inner is not None else None,
            "carton_lwh_cm": vals[i_outer] if i_outer is not None else None,
            "source_file": None,
            "source": "document",
            "_raw_size": size,
        }
        if row.get("inner_pack_lwh_cm"):
            row["pack_method"] = normalize_pack_method(row["inner_pack_lwh_cm"])
        rows.append(enrich_row(row))
    for r in rows:
        r.pop("_raw_size", None)
    return rows


def _parse_english_order(df: pd.DataFrame, meta: dict) -> list[dict]:
    hdr_i = None
    for i in range(len(df)):
        vals = [_cell(x) for x in df.iloc[i].tolist()]
        if "ITEM" in vals and ("COLOR" in vals or "QTY" in vals):
            hdr_i = i
            break
    if hdr_i is None:
        return []
    headers = [_cell(x) for x in df.iloc[hdr_i].tolist()]
    idx = {h: n for n, h in enumerate(headers) if h}

    def g(rowvals: list[str], *names: str) -> str:
        for n in names:
            if n in idx:
                return rowvals[idx[n]]
        return ""

    last_po = meta.get("order_code")
    last_item = ""
    last_grade = ""
    last_weight = ""
    rows: list[dict] = []
    for i in range(hdr_i + 1, len(df)):
        vals = [_cell(x) for x in df.iloc[i].tolist()]
        if not any(vals):
            continue
        if vals[0].lower() == "total" or "Total" in vals[0]:
            break
        po = g(vals, "P.O#", "P.O")
        item = g(vals, "ITEM")
        grade = g(vals, "Grade")
        color = g(vals, "COLOR")
        weight = g(vals, "WEIGHT/规格", "WEIGHT")
        qty = g(vals, "QTY")
        cartons = g(vals, "箱数")
        if po:
            last_po = po
        if item:
            last_item = item
        if grade:
            last_grade = grade
        if weight:
            last_weight = weight
        if not color and not qty:
            continue
        # ITEM like TABLECLOTH 60X102inch
        size = None
        m = re.search(r"(TABLECLOTH\s+)?(.+)", last_item, re.I)
        if m:
            size = normalize_size(m.group(2) if m.lastindex and m.lastindex >= 2 else last_item)
            size = normalize_size(re.sub(r"(?i)^TABLECLOTH\s*", "", last_item))
        row = {
            "order_code": meta.get("order_code") or last_po,
            "order_date": meta.get("order_date"),
            "entity_code": meta.get("entity_code")
            or normalize_entity_code(last_po or meta.get("order_code")),
            "size": size,
            "color": color,
            "gram_weight": normalize_gram_weight(last_weight),
            "product_name_zh": last_grade or None,
            "product_name_en": "TABLECLOTH",
            "qty_strips": to_num(qty),
            "qty_cartons": to_num(cartons),
            "source": "document",
        }
        # derive strips_per_carton if possible
        if row["qty_strips"] and row["qty_cartons"] and row["qty_cartons"] > 0:
            spc = row["qty_strips"] / row["qty_cartons"]
            if abs(spc - round(spc)) < 1e-6:
                row["strips_per_carton"] = int(round(spc))
        rows.append(enrich_row(row))
    return rows


def parse_order_workbook(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    df = pd.read_excel(path, header=None)
    meta = extract_order_meta(df)
    packing = _parse_chinese_packing(df, meta)
    lines = packing if packing else _parse_english_order(df, meta)
    for r in lines:
        r["source_file"] = path.name
    return {
        "meta": meta,
        "lines": lines,
        "format": "zh_packing" if packing else "en_order",
        "path": str(path),
    }
