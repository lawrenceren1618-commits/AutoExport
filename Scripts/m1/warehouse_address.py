# -*- coding: utf-8 -*-
"""Amazon FC/AWD warehouse code → receiving address (settled JSON)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
ADDR_JSON = SCRIPTS / "amazon_warehouse_addresses.json"


def load_addresses(path: Path | None = None) -> dict:
    p = path or ADDR_JSON
    if not p.is_file():
        return {"warehouses": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def get_address(code: str, data: dict | None = None) -> dict | None:
    if not code:
        return None
    warehouses = (data or load_addresses()).get("warehouses") or {}
    rec = warehouses.get(str(code).strip().upper())
    return dict(rec) if rec else None


def placeholder(code: str) -> dict:
    wh = str(code or "").strip().upper()
    return {
        "company": "Amazon.com Services, Inc.",
        "line1": "",
        "city": "",
        "state": "",
        "zip": "",
        "country": "United States",
        "freight_addr": f"{wh} - United States (address pending FBA header)",
        "placeholder": True,
    }


def settle_address(
    *,
    code: str,
    freight_addr: str,
    line1: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
    channel: str = "",
    source: str = "",
    path: Path | None = None,
) -> dict:
    """Insert/update one warehouse after user confirmation. Does not write placeholders."""
    p = path or ADDR_JSON
    data = load_addresses(p)
    warehouses = data.setdefault("warehouses", {})
    wh = str(code).strip().upper()
    rec = {
        "channel": channel or (warehouses.get(wh) or {}).get("channel") or "",
        "company": "Amazon.com Services, Inc.",
        "line1": line1,
        "city": city,
        "state": state,
        "zip": zip_code,
        "country": "United States",
        "freight_addr": freight_addr,
        "source": source or "user_confirm",
        "confirmed_at": date.today().isoformat(),
    }
    warehouses[wh] = rec
    data["updated_at"] = rec["confirmed_at"]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rec
