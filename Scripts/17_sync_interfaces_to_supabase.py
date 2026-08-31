# -*- coding: utf-8 -*-
"""
17_sync_interfaces_to_supabase.py — 将 interfaces + settled confirmed_defaults 灌入 autoexport 表

隔离（2026-07-27）：
  - 只写云端表；绝不写本机 settled / interfaces / Shipments
  - 见 Templates/Cloud_Local_Isolation.md
  - 推荐改用：node Scripts/18_cloud_supabase_bootstrap.mjs --apply

默认 dry-run。真正写入须：
  --apply
  且环境变量 SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
    （或 web/.env.local 中 NEXT_PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY）

不上传 PDF；只同步元数据行。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent


def _load_env_local() -> None:
    env = ROOT / "web" / ".env.local"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to Supabase (default dry-run)")
    args = ap.parse_args()
    _load_env_local()

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    interfaces = json.loads((SCRIPTS / "data_source_interfaces.json").read_text(encoding="utf-8"))
    settled = json.loads((SCRIPTS / "settled_knowledge_db.json").read_text(encoding="utf-8"))

    iface_rows = []
    for item in interfaces.get("interfaces") or []:
        iface_rows.append(
            {
                "id": item.get("id"),
                "task": item.get("task"),
                "needs": item.get("needs"),
                "channel": item.get("channel"),
                "module": item.get("module"),
                "obtain": item.get("obtain") or {},
                "cloud": item.get("cloud") or {"status": "pending_cloud"},
            }
        )
    cfg_rows = []
    for k, v in (settled.get("confirmed_defaults") or {}).items():
        cfg_rows.append(
            {
                "key": f"confirmed_defaults.{k}",
                "value": v if isinstance(v, (dict, list)) else {"_": v},
                "confirmed_at": (v.get("confirmed_at") if isinstance(v, dict) else None),
            }
        )
    for code, ent in (settled.get("entities") or {}).items():
        cfg_rows.append({"key": f"entities.{code}", "value": ent, "confirmed_at": None})

    print(f"interfaces_rows={len(iface_rows)} settled_config_rows={len(cfg_rows)}")
    print(f"supabase_url_set={bool(url)} service_role_set={bool(key)} apply={args.apply}")
    print("isolation=local_read_only→cloud_write_only (no local file writes)")

    if not args.apply:
        print("dry-run only; pass --apply to upsert")
        return 0
    if not url or not key:
        print("FAIL: missing SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return 2

    try:
        from supabase import create_client  # type: ignore
    except ImportError:
        print("FAIL: pip install supabase  (or run via environment that has @supabase client)")
        print("NOTE: migration must be applied first: 20260726000000_channel_ab_interfaces.sql")
        return 3

    client = create_client(url, key)
    # upsert interfaces
    for row in iface_rows:
        client.schema("autoexport").table("data_source_interfaces").upsert(row).execute()
    for row in cfg_rows:
        payload = {
            "key": row["key"],
            "value": row["value"],
            "confirmed_at": row.get("confirmed_at"),
        }
        client.schema("autoexport").table("settled_config").upsert(payload).execute()
    print("OK upserted interfaces + settled_config")
    return 0


if __name__ == "__main__":
    sys.exit(main())
