# -*- coding: utf-8 -*-
"""
smoke_check.py — 仓库健康冒烟（无外部网络）

检查：关键 JSON 可解析、A/B 渠道键存在、User_IO 骨架、接口表 cloud 字段合法。
用法：python Scripts/smoke_check.py
退出码：0 全部通过；1 有失败。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS: list[str] = []
PASSES: list[str] = []


def ok(msg: str) -> None:
    PASSES.append(msg)
    print(f"PASS  {msg}")


def bad(msg: str) -> None:
    FAILS.append(msg)
    print(f"FAIL  {msg}")


def load_json(rel: str) -> dict | list | None:
    p = ROOT / rel
    if not p.is_file():
        bad(f"missing {rel}")
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        ok(f"json {rel}")
        return data
    except Exception as e:  # noqa: BLE001
        bad(f"json {rel}: {e}")
        return None


def main() -> int:
    settled = load_json("Scripts/settled_knowledge_db.json")
    interfaces = load_json("Scripts/data_source_interfaces.json")
    load_json("Scripts/canonical_schema.json")
    load_json("Scripts/entity_brand_rules.json")
    load_json("Scripts/local_operational_paths.json")
    load_json("Scripts/document_field_preflight.json")

    if isinstance(settled, dict):
        cd = settled.get("confirmed_defaults") or {}
        for key in (
            "channel_ab_roles",
            "user_io_layout",
            "folder_simplify_policy",
            "gate_cross_validate",
            "customs_c04_1039_for_all_stores",
            "c07_inherits_c04_pipeline",
        ):
            if key in cd:
                ok(f"settled.confirmed_defaults.{key}")
            else:
                bad(f"settled missing confirmed_defaults.{key}")

    if isinstance(interfaces, dict):
        policy = interfaces.get("policy") or {}
        if policy.get("heavy_binaries"):
            ok("interfaces.policy.heavy_binaries noted")
        else:
            bad("interfaces.policy.heavy_binaries missing")
        ids = {i.get("id") for i in interfaces.get("interfaces") or [] if isinstance(i, dict)}
        for need in (
            "ref.settled_knowledge",
            "tpl.freight_order_xlsx",
            "tpl.customs_1039_xlsx",
            "pack.factory_label_kit",
        ):
            if need in ids:
                ok(f"interface {need}")
            else:
                bad(f"interface missing {need}")
        # user_io channel interface optional until registered
        if "job.user_io_project" in ids:
            ok("interface job.user_io_project")
        else:
            bad("interface missing job.user_io_project (A channel)")

    # A channel scaffold
    user_io = ROOT / "User_IO"
    if user_io.is_dir():
        ok("User_IO/ exists")
    else:
        bad("User_IO/ missing")
    tmpl = user_io / "_TEMPLATE"
    for leaf in (
        "输入端/订单发货数据",
        "输入端/亚马逊外箱贴与追踪截图",
        "输入端/货代入库贴",
        "输出端/订单表",
        "输出端/出货表",
        "输出端/货代下单表",
        "输出端/报关单证",
        "输出端/产品标签",
        "输出端/贴标包",
        "汇总存档",
    ):
        if (tmpl / leaf).is_dir():
            ok(f"template {leaf}")
        else:
            bad(f"template missing {leaf}")

    for d in (
        "Templates/Channel_AB_Architecture.md",
        "Templates/User_IO_Layout.md",
        "Templates/Data_Source_Interfaces.md",
        "Templates/Next_Session_Handoff.md",
        "Templates/Cloud_Workspace_Pipeline.md",
        "Scripts/cloud_workspace_pipeline.json",
        "web/lib/pipeline/cloud_workspace_pipeline.json",
    ):
        if (ROOT / d).is_file():
            ok(f"doc {d}")
        else:
            bad(f"doc missing {d}")

    # B channel: at least Scripts entrypoints exist
    for s in (
        "Scripts/03_cross_validate.py",
        "Scripts/09_generate_freight_customs_drafts.py",
        "Scripts/12_freight_inbound_label_ingest.py",
        "Scripts/13_export_output_packs.py",
        "web/app/workspace/page.tsx",
        "web/app/api/jobs/route.ts",
    ):
        if (ROOT / s).is_file():
            ok(f"script {s}")
        else:
            bad(f"script missing {s}")

    print("---")
    print(f"passed={len(PASSES)} failed={len(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
