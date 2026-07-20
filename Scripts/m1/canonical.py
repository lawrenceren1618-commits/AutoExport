# -*- coding: utf-8 -*-
"""Canonical 字段规范化（与 Scripts/canonical_schema.json / web/lib/master-import.ts 对齐）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent.parent
SCHEMA_PATH = SCRIPTS / "canonical_schema.json"
ENTITY_RULES_PATH = SCRIPTS / "entity_brand_rules.json"

_BRAND_BY_ENTITY = {"C04": "WIGENIUS", "C07": "Dressmaker"}


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_entity_rules() -> dict:
    return json.loads(ENTITY_RULES_PATH.read_text(encoding="utf-8"))


def build_alias_map(schema: dict | None = None) -> dict[str, str]:
    schema = schema or load_schema()
    out: dict[str, str] = {}
    for key, aliases in schema.get("header_aliases", {}).items():
        for a in aliases:
            out[str(a).strip()] = key
            out[str(a).strip().lower()] = key
        out[key] = key
    return out


def normalize_entity_code(v: Any, order_code: str | None = None) -> str | None:
    raw = str(v or "").upper()
    if "C04" in raw:
        return "C04"
    if "C07" in raw:
        return "C07"
    m = re.search(r"C0[47]", raw)
    if m:
        return m.group(0)
    if order_code:
        m2 = re.search(r"C0[47]", str(order_code).upper())
        if m2:
            return m2.group(0)
    return None


def normalize_pack_method(v: Any) -> str | None:
    if v is None or v == "":
        return None
    s = str(v)
    if "热缩" in s or re.search(r"shrink", s, re.I):
        return "heat_shrink"
    if "纸箱" in s or "内盒" in s or re.search(r"carton", s, re.I):
        return "carton"
    if s in ("heat_shrink", "carton"):
        return s
    return s.strip()


def normalize_lwh(v: Any) -> str | None:
    if v is None or v == "":
        return None
    s = (
        str(v)
        .strip()
        .replace("×", "*")
        .replace("x", "*")
        .replace("X", "*")
    )
    s = re.sub(r"\s*cm\s*", "", s, flags=re.I)
    s = re.sub(r"纸箱规格[：:]\s*", "", s)
    s = re.sub(r"纸箱[：:]\s*", "", s)
    s = re.sub(r"\s+", "", s)
    return s or None


def normalize_size(v: Any) -> str | None:
    if v is None or v == "":
        return None
    s = str(v).strip()
    if re.search(r"(?i)90.*round", s):
        return "90inchround"
    # 仅替换尺寸乘号，避免误伤 round 等单词中的字母
    s = s.replace("×", "X").replace("*", "X")
    s = re.sub(r"(?<=\d)x(?=\d)", "X", s, flags=re.I)
    s = re.sub(r"\s+", "", s)
    return s


def normalize_color(v: Any) -> str | None:
    if v is None or v == "":
        return None
    return str(v).strip().replace(" ", "")


def normalize_gram_weight(v: Any) -> str | None:
    if v is None or v == "":
        return None
    s = str(v).strip()
    m = re.search(r"(\d+)\s*[Gg克]", s)
    if m:
        return f"{m.group(1)}G"
    if re.fullmatch(r"\d+", s):
        return f"{s}G"
    return s


def to_num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def to_date_str(v: Any) -> str | None:
    if v is None or v == "":
        return None
    if hasattr(v, "strftime"):
        try:
            return v.strftime("%Y-%m-%d")
        except Exception:
            pass
    s = str(v).strip().replace(".", "-").replace("/", "-")
    parts = re.findall(r"\d+", s)
    if len(parts) >= 3:
        y, m, d = parts[0], parts[1].zfill(2), parts[2].zfill(2)
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{m}-{d}"
    return s[:10] or None


def apply_brand_default(row: dict) -> dict:
    if not row.get("brand") and row.get("entity_code") in _BRAND_BY_ENTITY:
        row["brand"] = _BRAND_BY_ENTITY[row["entity_code"]]
    return row


def sku_key(row: dict) -> str | None:
    brand = row.get("brand") or ""
    size = row.get("size") or ""
    color = row.get("color") or ""
    key = "|".join(x for x in (brand, size, color) if x)
    return key or None


def product_pack_key(row: dict) -> str:
    """同品同牌同主体装箱冲突索引（不含 FNSKU，用于发现条数/包数分歧）。"""
    return "|".join(
        [
            str(row.get("entity_code") or ""),
            str(row.get("brand") or ""),
            str(row.get("size") or ""),
            str(row.get("color") or ""),
        ]
    )


def enrich_row(row: dict) -> dict:
    apply_brand_default(row)
    if row.get("size"):
        row["size"] = normalize_size(row["size"])
    if row.get("color"):
        row["color"] = normalize_color(row["color"])
    if row.get("gram_weight"):
        row["gram_weight"] = normalize_gram_weight(row["gram_weight"])
    if row.get("carton_lwh_cm"):
        row["carton_lwh_cm"] = normalize_lwh(row["carton_lwh_cm"])
    if row.get("inner_pack_lwh_cm"):
        ip = str(row["inner_pack_lwh_cm"])
        if "热缩" in ip:
            row["pack_method"] = row.get("pack_method") or "heat_shrink"
            row["inner_pack_lwh_cm"] = None
        else:
            row["inner_pack_lwh_cm"] = normalize_lwh(ip)
            row["pack_method"] = row.get("pack_method") or normalize_pack_method(ip) or "carton"
    spp = to_num(row.get("strips_per_pack"))
    ppc = to_num(row.get("packs_per_carton"))
    spc = to_num(row.get("strips_per_carton"))
    if spp is not None:
        row["strips_per_pack"] = int(spp) if spp == int(spp) else spp
    if ppc is not None:
        row["packs_per_carton"] = int(ppc) if ppc == int(ppc) else ppc
    if spc is None and spp is not None and ppc is not None:
        spc = spp * ppc
    if spc is not None:
        row["strips_per_carton"] = int(spc) if spc == int(spc) else spc
    row["sku_key"] = sku_key(row)
    row["product_key"] = row["sku_key"]
    return row
