# -*- coding: utf-8 -*-
"""从沉淀库 +（已确认）总表行组装待填订单明细。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import enrich_row, load_entity_rules

SCRIPTS = Path(__file__).resolve().parent.parent
SETTLED_DB = SCRIPTS / "settled_knowledge_db.json"


def load_settled_products(path: Path = SETTLED_DB) -> dict[str, Any]:
    if not path.exists():
        return {"products": [], "packing_standards": [], "fnsku_index": []}
    return json.loads(path.read_text(encoding="utf-8"))


def assemble_order_lines(
    *,
    entity_code: str,
    order_code: str,
    order_date: str | None,
    qty_plan: list[dict],
    settled: dict | None = None,
    master_rows: list[dict] | None = None,
    confirmed_resolutions: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """
    qty_plan: [{size, color, qty_strips}, ...]
    从 settled.packing_standards / master_rows 匹配装箱与 FNSKU。
    confirmed_resolutions: conflict_key → 选用字段字典（使用者确认后传入）。
    未匹配或冲突未确认 → pending 列表，不静默填。
    """
    settled = settled or load_settled_products()
    master_rows = master_rows or []
    confirmed_resolutions = confirmed_resolutions or {}
    rules = load_entity_rules()
    brand = (
        rules.get("entities", {}).get(entity_code, {}).get("brand_tablecloth")
        or ({"C04": "WIGENIUS", "C07": "Dressmaker"}.get(entity_code))
    )

    pack_idx: dict[str, list[dict]] = {}
    for p in settled.get("packing_standards") or []:
        if p.get("entity_code") and p.get("entity_code") != entity_code:
            continue
        key = "|".join(
            [
                entity_code,
                str(p.get("brand") or brand),
                str(p.get("size") or ""),
                str(p.get("color") or ""),
            ]
        )
        pack_idx.setdefault(key, []).append(p)

    for m in master_rows:
        if m.get("entity_code") and m.get("entity_code") != entity_code:
            continue
        key = "|".join(
            [
                entity_code,
                str(m.get("brand") or brand),
                str(m.get("size") or ""),
                str(m.get("color") or ""),
            ]
        )
        pack_idx.setdefault(key, []).append({**m, "source": m.get("source") or "master_table"})

    lines: list[dict] = []
    pending: list[dict] = []
    for plan in qty_plan:
        size = plan.get("size")
        color = plan.get("color")
        key = f"{entity_code}|{brand}|{size}|{color}"
        cands = pack_idx.get(key) or []
        if key in confirmed_resolutions:
            chosen = {**confirmed_resolutions[key]}
        elif len(cands) == 1:
            chosen = dict(cands[0])
        elif len(cands) == 0:
            pending.append({"reason": "no_settled_or_master_match", "key": key, "plan": plan})
            continue
        else:
            pending.append(
                {
                    "reason": "multiple_candidates_need_confirm",
                    "key": key,
                    "plan": plan,
                    "candidates": cands,
                }
            )
            continue

        row = enrich_row(
            {
                "entity_code": entity_code,
                "brand": brand,
                "order_code": order_code,
                "order_date": order_date,
                "size": size,
                "color": color,
                "qty_strips": plan.get("qty_strips"),
                **{
                    k: chosen.get(k)
                    for k in (
                        "gram_weight",
                        "strips_per_pack",
                        "packs_per_carton",
                        "strips_per_carton",
                        "fnsku",
                        "pack_method",
                        "inner_pack_lwh_cm",
                        "carton_lwh_cm",
                        "product_name_zh",
                        "product_name_en",
                    )
                    if chosen.get(k) is not None
                },
            }
        )
        # 箱数勾稽
        spc = row.get("strips_per_carton")
        qty = row.get("qty_strips")
        if spc and qty and spc > 0:
            cartons = qty / spc
            if abs(cartons - round(cartons)) < 1e-6:
                row["qty_cartons"] = int(round(cartons))
            else:
                pending.append(
                    {
                        "reason": "qty_not_divisible_by_strips_per_carton",
                        "key": key,
                        "qty_strips": qty,
                        "strips_per_carton": spc,
                    }
                )
        lines.append(row)

    return {"lines": lines, "pending": pending, "brand": brand, "entity_code": entity_code}
