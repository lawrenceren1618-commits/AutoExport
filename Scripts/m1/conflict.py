# -*- coding: utf-8 -*-
"""装箱 / 总表冲突检测。冲突只汇报，不静默覆盖。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


PACK_COMPARE_FIELDS = (
    "gram_weight",
    "strips_per_pack",
    "packs_per_carton",
    "strips_per_carton",
    "pack_method",
    "inner_pack_lwh_cm",
    "carton_lwh_cm",
    "fnsku",
)


@dataclass
class ConflictVariant:
    source: str  # order | master
    order_code: str | None = None
    order_date: str | None = None
    master_upload_at: str | None = None
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictReport:
    conflict_key: str
    kind: str  # packing | gram_weight | master | cross_source
    suggested_default: str | None
    suggestion_reason: str
    variants: list[ConflictVariant]
    confirmed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _pack_sig(row: dict) -> tuple:
    return tuple(row.get(f) for f in PACK_COMPARE_FIELDS)


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _suggest_latest_order(variants: list[ConflictVariant]) -> str | None:
    dated = [(_parse_ts(v.order_date), v) for v in variants]
    dated_ok = [p for p in dated if p[0] is not None]
    if not dated_ok:
        return None
    dated_ok.sort(key=lambda p: p[0], reverse=True)
    return dated_ok[0][1].order_code


def _suggest_gram_preference(variants: list[ConflictVariant]) -> str | None:
    """克重冲突：默认倾向 90G（仍须当次人工确认）；无 90G 则退回下单日最新。"""
    ninety = [v for v in variants if str(v.values.get("gram_weight") or "").upper().startswith("90")]
    if ninety:
        return _suggest_latest_order(ninety) or ninety[0].order_code
    return _suggest_latest_order(variants)


def detect_packing_conflicts(rows: list[dict]) -> list[ConflictReport]:
    """
    冲突索引：entity|brand|size|color|strips_per_pack
    （同色同尺寸下 6条装 vs 10条装是不同 listing，不算冲突）
    另：同 entity|brand|size|color 下克重不一致单独汇报。
    建议默认：order_date 最新（仅建议）。
    """
    buckets: dict[str, list[dict]] = {}
    gram_buckets: dict[str, list[dict]] = {}
    for r in rows:
        base = "|".join(
            [
                str(r.get("entity_code") or ""),
                str(r.get("brand") or ""),
                str(r.get("size") or ""),
                str(r.get("color") or ""),
            ]
        )
        if base == "|||":
            continue
        spp = r.get("strips_per_pack")
        key = f"{base}|{spp if spp is not None else ''}"
        buckets.setdefault(key, []).append(r)
        gram_buckets.setdefault(base, []).append(r)

    reports: list[ConflictReport] = []
    reason = "订单按下单日期最新（建议，须确认）"

    for base, items in gram_buckets.items():
        grams = {x.get("gram_weight") for x in items if x.get("gram_weight")}
        if len(grams) <= 1:
            continue
        seen_g: set = set()
        variants: list[ConflictVariant] = []
        for x in items:
            g = x.get("gram_weight")
            if not g or g in seen_g:
                continue
            seen_g.add(g)
            variants.append(
                ConflictVariant(
                    source="order",
                    order_code=x.get("order_code"),
                    order_date=x.get("order_date"),
                    values={f: x.get(f) for f in PACK_COMPARE_FIELDS},
                )
            )
        reports.append(
            ConflictReport(
                conflict_key=f"gram:{base}",
                kind="gram_weight",
                suggested_default=_suggest_gram_preference(variants),
                suggestion_reason="克重冲突须当次确认；建议默认 90G（保留其它克重入口），否则按下单日最新",
                variants=variants,
            )
        )

    for key, items in buckets.items():
        detailed = [x for x in items if x.get("strips_per_pack") is not None]
        compare_items = detailed if len(detailed) >= 2 else items
        sigs = {_pack_sig(x) for x in compare_items}
        if len(sigs) <= 1:
            continue
        seen: set[tuple] = set()
        variants = []
        for x in compare_items:
            sig = _pack_sig(x)
            if sig in seen:
                continue
            seen.add(sig)
            variants.append(
                ConflictVariant(
                    source="order",
                    order_code=x.get("order_code"),
                    order_date=x.get("order_date"),
                    values={f: x.get(f) for f in PACK_COMPARE_FIELDS},
                )
            )
        if len(variants) <= 1:
            continue
        reports.append(
            ConflictReport(
                conflict_key=key,
                kind="packing",
                suggested_default=_suggest_latest_order(variants),
                suggestion_reason=reason,
                variants=variants,
            )
        )
    return reports


def detect_master_conflicts(rows: list[dict]) -> list[ConflictReport]:
    """总表多行同键：以 master_upload_at 最新为建议。"""
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        key = "|".join(
            [
                str(r.get("entity_code") or ""),
                str(r.get("brand") or ""),
                str(r.get("size") or ""),
                str(r.get("color") or ""),
                str(r.get("strips_per_pack") or ""),
                str(r.get("fnsku") or ""),
            ]
        )
        buckets.setdefault(key, []).append(r)

    reports: list[ConflictReport] = []
    for key, items in buckets.items():
        sigs = {_pack_sig(x) for x in items}
        if len(sigs) <= 1:
            continue
        seen: set[tuple] = set()
        variants: list[ConflictVariant] = []
        for x in items:
            sig = _pack_sig(x)
            if sig in seen:
                continue
            seen.add(sig)
            variants.append(
                ConflictVariant(
                    source="master",
                    order_code=x.get("order_code"),
                    master_upload_at=x.get("master_upload_at"),
                    values={f: x.get(f) for f in PACK_COMPARE_FIELDS},
                )
            )
        dated = [(_parse_ts(v.master_upload_at), v) for v in variants]
        dated_ok = [p for p in dated if p[0] is not None]
        suggested = None
        if dated_ok:
            dated_ok.sort(key=lambda p: p[0], reverse=True)
            suggested = dated_ok[0][1].master_upload_at
        reports.append(
            ConflictReport(
                conflict_key=key,
                kind="master",
                suggested_default=suggested,
                suggestion_reason="总表按上传时间最新（建议，须确认）",
                variants=variants,
            )
        )
    return reports
