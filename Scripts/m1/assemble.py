# -*- coding: utf-8 -*-
"""从沉淀库 +（已确认）总表行组装待填订单明细。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import enrich_row, load_entity_rules, normalize_color

SCRIPTS = Path(__file__).resolve().parent.parent
SETTLED_DB = SCRIPTS / "settled_knowledge_db.json"


def load_settled_products(path: Path = SETTLED_DB) -> dict[str, Any]:
    if not path.exists():
        return {"products": [], "packing_standards": [], "fnsku_index": []}
    return json.loads(path.read_text(encoding="utf-8"))


SETTLED_PACK_FIELDS = (
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


def _pack_lookup_key(entity_code: str, brand: str, size: Any, color: Any) -> str:
    return "|".join(
        [
            entity_code,
            str(brand or ""),
            str(size or ""),
            str(normalize_color(color) or color or ""),
        ]
    )


def _same_val(a: Any, b: Any) -> bool:
    if a in (None, "") or b in (None, ""):
        return True
    return str(a).strip() == str(b).strip()


def _plan_vs_settled_diffs(plan: dict, settled: dict) -> list[dict]:
    diffs = []
    for f in SETTLED_PACK_FIELDS:
        pv, sv = plan.get(f), settled.get(f)
        if pv in (None, "") or sv in (None, ""):
            continue
        if not _same_val(pv, sv):
            diffs.append({"field": f, "plan": pv, "settled": sv})
    return diffs


def _filter_cands_for_plan(cands: list[dict], plan: dict) -> list[dict]:
    spp = plan.get("strips_per_pack")
    if spp in (None, "") or not cands:
        return list(cands)
    matched = [c for c in cands if _same_val(c.get("strips_per_pack"), spp)]
    return matched if matched else list(cands)


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
    装箱/内外箱以沉淀库 packing_standards 为准；计划行不得跳过库。
    confirmed_resolutions: conflict_key → 选用字段字典（使用者确认后传入）。
    库空、多套或与计划冲突 → pending，不静默填。
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
        key = _pack_lookup_key(entity_code, p.get("brand") or brand, p.get("size"), p.get("color"))
        pack_idx.setdefault(key, []).append(p)

    for m in master_rows:
        if m.get("entity_code") and m.get("entity_code") != entity_code:
            continue
        key = _pack_lookup_key(entity_code, m.get("brand") or brand, m.get("size"), m.get("color"))
        pack_idx.setdefault(key, []).append({**m, "source": m.get("source") or "master_table"})

    lines: list[dict] = []
    pending: list[dict] = []
    for plan in qty_plan:
        size = plan.get("size")
        color = plan.get("color")
        key = _pack_lookup_key(entity_code, brand, size, color)
        cands = _filter_cands_for_plan(pack_idx.get(key) or [], plan)
        if key in confirmed_resolutions:
            chosen = {**confirmed_resolutions[key]}
        elif not cands:
            pending.append(
                {
                    "reason": "missing_settled_packing",
                    "key": key,
                    "plan": plan,
                    "note": "箱规以沉淀库为准；库无对应行，须确认入库或指定本票箱规",
                }
            )
            continue
        elif len(cands) > 1:
            pending.append(
                {
                    "reason": "multiple_candidates_need_confirm",
                    "key": key,
                    "plan": plan,
                    "candidates": cands,
                }
            )
            continue
        else:
            settled_row = dict(cands[0])
            diffs = _plan_vs_settled_diffs(plan, settled_row)
            if diffs:
                pending.append(
                    {
                        "reason": "plan_conflicts_settled_packing",
                        "key": key,
                        "plan": plan,
                        "settled": settled_row,
                        "diffs": diffs,
                    }
                )
                continue
            chosen = {**plan, **{k: settled_row[k] for k in SETTLED_PACK_FIELDS if settled_row.get(k) not in (None, "")}}

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
                    for k in SETTLED_PACK_FIELDS
                    if chosen.get(k) is not None
                },
            }
        )
        # 箱规补全：有条/箱+条/包时可推包/箱
        if not row.get("packs_per_carton"):
            spp = row.get("strips_per_pack")
            spc0 = row.get("strips_per_carton")
            try:
                spp_i = int(float(spp)) if spp not in (None, "") else 0
                spc_i = int(float(spc0)) if spc0 not in (None, "") else 0
            except (TypeError, ValueError):
                spp_i, spc_i = 0, 0
            if spp_i > 0 and spc_i > 0 and spc_i % spp_i == 0:
                row["packs_per_carton"] = spc_i // spp_i
        # 计划已给箱数则保留；否则按条数÷条/箱勾稽
        if plan.get("qty_cartons") not in (None, ""):
            try:
                row["qty_cartons"] = int(float(plan["qty_cartons"]))
            except (TypeError, ValueError):
                pass
        if row.get("qty_strips") in (None, "") and row.get("qty_cartons") not in (None, "") and row.get("strips_per_carton"):
            try:
                row["qty_strips"] = int(float(row["qty_cartons"])) * int(float(row["strips_per_carton"]))
            except (TypeError, ValueError):
                pass
        spc = row.get("strips_per_carton")
        qty = row.get("qty_strips")
        if spc and qty and spc > 0 and row.get("qty_cartons") in (None, ""):
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
