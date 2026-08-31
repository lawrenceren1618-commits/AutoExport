# -*- coding: utf-8 -*-
"""Customs 合同协议号：YYYYMMDD + 3-digit suffix; global uniqueness via registry.

See Templates/Customs_Contract_Protocol_No.md.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "Scripts" / "contract_protocol_registry.json"

PROTOCOL_RE = re.compile(r"^(\d{8})(\d{3})$")
# Prefer 501..999 then 001..500 (user habit: 501, 502, 506…)
PREFERRED_START = 501


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def normalize_ship_yyyymmdd(ship_date: str) -> str:
    s = (ship_date or "").strip().replace(".", "-").replace("/", "-")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 8:
        return digits[:8]
    raise ValueError(f"bad_ship_date:{ship_date}")


def load_registry(path: Path | None = None) -> dict:
    p = path or REGISTRY_PATH
    if not p.is_file():
        return {
            "version": "1.0",
            "doc": "Templates/Customs_Contract_Protocol_No.md",
            "preferred_suffix_start": PREFERRED_START,
            "entries": [],
        }
    return json.loads(p.read_text(encoding="utf-8"))


def save_registry(data: dict, path: Path | None = None) -> None:
    p = path or REGISTRY_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def used_protocol_nos(data: dict) -> set[str]:
    return {str(e.get("protocol_no") or "") for e in data.get("entries") or [] if e.get("protocol_no")}


def find_existing(
    data: dict,
    *,
    project: str,
    warehouse_code: str,
    ship_yyyymmdd: str | None = None,
) -> str | None:
    for e in data.get("entries") or []:
        if e.get("project") != project:
            continue
        if e.get("warehouse_code") != warehouse_code:
            continue
        if ship_yyyymmdd and str(e.get("ship_yyyymmdd") or "") != ship_yyyymmdd:
            continue
        no = e.get("protocol_no")
        if no:
            return str(no)
    return None


def find_existing_by_leg(
    data: dict,
    *,
    order_or_plan: str,
    warehouse_code: str,
    ship_yyyymmdd: str | None = None,
) -> str | None:
    """Reuse when gen_trio used project_stub but same 腿+仓+日."""
    if not order_or_plan:
        return None
    for e in data.get("entries") or []:
        if str(e.get("order_or_plan") or "") != str(order_or_plan):
            continue
        if e.get("warehouse_code") != warehouse_code:
            continue
        if ship_yyyymmdd and str(e.get("ship_yyyymmdd") or "") != ship_yyyymmdd:
            continue
        no = e.get("protocol_no")
        if no:
            return str(no)
    return None


def _suffix_candidates() -> list[str]:
    out: list[str] = []
    for n in range(PREFERRED_START, 1000):
        out.append(f"{n:03d}")
    for n in range(1, PREFERRED_START):
        out.append(f"{n:03d}")
    return out


def allocate_protocol_no(
    ship_date: str,
    *,
    project: str,
    warehouse_code: str,
    order_or_plan: str = "",
    registry_path: Path | None = None,
    dry_run: bool = False,
) -> str:
    """Return unique {YYYYMMDD}{NNN}; persist unless dry_run.

    Idempotent for same project + warehouse (+ same ship day).
    """
    ymd = normalize_ship_yyyymmdd(ship_date)
    data = load_registry(registry_path)
    existing = find_existing(
        data, project=project, warehouse_code=warehouse_code, ship_yyyymmdd=ymd
    )
    if existing:
        return existing
    existing = find_existing_by_leg(
        data,
        order_or_plan=order_or_plan,
        warehouse_code=warehouse_code,
        ship_yyyymmdd=ymd,
    )
    if existing:
        return existing

    used = used_protocol_nos(data)
    chosen: str | None = None
    for suf in _suffix_candidates():
        cand = f"{ymd}{suf}"
        if cand not in used:
            chosen = cand
            break
    if not chosen:
        raise RuntimeError(f"protocol_suffix_exhausted_for_date:{ymd}")

    entry = {
        "protocol_no": chosen,
        "ship_yyyymmdd": ymd,
        "ship_date": ship_date,
        "project": project,
        "warehouse_code": warehouse_code,
        "order_or_plan": order_or_plan or "",
        "allocated_at": _now(),
    }
    if not dry_run:
        # Enforce unique protocol_no in registry
        if chosen in used:
            raise RuntimeError(f"protocol_race_or_collision:{chosen}")
        data.setdefault("entries", []).append(entry)
        save_registry(data, registry_path)
    return chosen


def assert_unique_batch(protocol_nos: list[str]) -> list[str]:
    """Return error strings if batch has internal duplicates or bad format."""
    errs: list[str] = []
    seen: set[str] = set()
    for no in protocol_nos:
        if not PROTOCOL_RE.match(no or ""):
            errs.append(f"bad_format:{no}")
            continue
        if no in seen:
            errs.append(f"batch_duplicate:{no}")
        seen.add(no)
    return errs
