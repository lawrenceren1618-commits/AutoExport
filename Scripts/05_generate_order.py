# -*- coding: utf-8 -*-
"""
05_generate_order.py — 块 B / M1 订单生成入口

流程：
  1) 扫描 01_Order_Outbound 历史单 → 冲突汇报（order_date 最新建议）
  2) 读取沉淀库 +（可选）已确认总表行 → 组装
  3) 填固定订单模板 → 2_Processed_AI/drafts/
  4) 交叉对照通过后 → 3_Output_Final/（须 --finalize 且 Gate 通过）

冲突默认不写入；须 --confirm-conflicts JSON 或人工确认后再出最终件。
握手：M0→M1；出最终前 HX(Gate)。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# allow `python Scripts/05_generate_order.py`
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from m1.assemble import assemble_order_lines, load_settled_products  # noqa: E402
from m1.conflict import detect_master_conflicts, detect_packing_conflicts  # noqa: E402
from m1.order_fill import fill_order_template, resolve_blank_template  # noqa: E402
from m1.order_parse import parse_order_workbook  # noqa: E402

PROJECT = SCRIPTS.parent
ORDER_DIR = PROJECT / "1_Input_Raw" / "01_Order_Outbound"
MASTER_DIR = PROJECT / "1_Input_Raw" / "00_Master_Reference"
DRAFT_DIR = PROJECT / "2_Processed_AI" / "drafts"
REPORT_DIR = PROJECT / "2_Processed_AI" / "cross_check_reports"
OUTPUT_DIR = PROJECT / "3_Output_Final"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scan_orders(directory: Path = ORDER_DIR) -> dict:
    files = sorted(
        p
        for p in directory.iterdir()
        if p.suffix.lower() in {".xls", ".xlsx"} and not p.name.startswith("~$")
    )
    all_lines: list[dict] = []
    metas: list[dict] = []
    for p in files:
        try:
            parsed = parse_order_workbook(p)
        except Exception as e:
            metas.append({"path": str(p), "error": str(e)})
            continue
        metas.append(
            {
                "path": p.name,
                "format": parsed["format"],
                "meta": parsed["meta"],
                "line_count": len(parsed["lines"]),
            }
        )
        all_lines.extend(parsed["lines"])
    conflicts = detect_packing_conflicts(all_lines)
    return {
        "scanned_at": _utc_now(),
        "files": metas,
        "line_count": len(all_lines),
        "lines": all_lines,
        "conflicts": [c.to_dict() for c in conflicts],
    }


def write_conflict_report(scan: dict, out: Path | None = None) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = out or REPORT_DIR / f"order_conflicts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    payload = {
        "scanned_at": scan["scanned_at"],
        "files": scan["files"],
        "line_count": scan["line_count"],
        "conflict_count": len(scan["conflicts"]),
        "conflicts": scan["conflicts"],
        "rule": {
            "order_recency": "order_date",
            "master_recency": "master_upload_at",
            "action": "report_then_user_confirm",
        },
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def cross_check_draft(lines: list[dict], settled: dict) -> dict:
    """轻量 Gate：主体品牌、FNSKU 串店、装箱缺失。完整对照仍走 03_cross_validate。"""
    issues: list[dict] = []
    brand_map = {"C04": "WIGENIUS", "C07": "Dressmaker"}
    fnsku_owner: dict[str, str] = {}
    for f in settled.get("fnsku_index") or []:
        if f.get("fnsku") and f.get("entity_code"):
            fnsku_owner[str(f["fnsku"]).upper()] = f["entity_code"]

    for i, ln in enumerate(lines):
        ent = ln.get("entity_code")
        brand = ln.get("brand")
        if ent in brand_map and brand and brand != brand_map[ent]:
            issues.append(
                {
                    "row": i,
                    "field": "brand",
                    "draft": brand,
                    "expected": brand_map[ent],
                    "msg": "品牌与主体不匹配",
                }
            )
        fn = (ln.get("fnsku") or "").upper()
        if fn and ent and fn in fnsku_owner and fnsku_owner[fn] != ent:
            issues.append(
                {
                    "row": i,
                    "field": "fnsku",
                    "draft": fn,
                    "expected_entity": fnsku_owner[fn],
                    "msg": "FNSKU 跨店冲突",
                }
            )
        for req in ("size", "color", "strips_per_pack", "packs_per_carton", "fnsku"):
            if ln.get(req) in (None, ""):
                issues.append({"row": i, "field": req, "msg": "缺失必填装箱字段"})
    return {"pass": len(issues) == 0, "issues": issues}


def main() -> None:
    parser = argparse.ArgumentParser(description="M1 订单生成：扫描冲突 / 填模板 / 终审输出")
    parser.add_argument("--scan", action="store_true", help="扫描 01 历史单并汇报冲突")
    parser.add_argument("--ensure-template", action="store_true", help="生成空白订单模板 xlsx")
    parser.add_argument("--order-code", type=str, help="新订单编号，如 EF-C26xxx-C04-nnnnn")
    parser.add_argument("--order-date", type=str, help="下单日期 YYYY-MM-DD")
    parser.add_argument("--delivery-date", type=str, help="交货日期")
    parser.add_argument("--entity", type=str, choices=["C04", "C07"], help="主体代码")
    parser.add_argument(
        "--qty-plan",
        type=str,
        help='数量计划 JSON 文件：[{"size":"60X102inch","color":"白","qty_strips":2000}, ...]',
    )
    parser.add_argument(
        "--confirm-conflicts",
        type=str,
        help="已确认冲突决议 JSON：{conflict_key: {字段...}}",
    )
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="对照通过后写入 3_Output_Final（默认只写 drafts）",
    )
    args = parser.parse_args()

    if args.ensure_template:
        p = resolve_blank_template()
        print(f"blank_template={p}")
        return

    if args.scan or not args.order_code:
        scan = scan_orders()
        report_path = write_conflict_report(scan)
        print(f"scanned_files={len(scan['files'])}")
        print(f"lines={scan['line_count']}")
        print(f"conflicts={len(scan['conflicts'])}")
        print(f"report={report_path}")
        for c in scan["conflicts"][:20]:
            print("---")
            print(f"key={c['conflict_key']}")
            print(f"suggest={c['suggested_default']} ({c['suggestion_reason']})")
            for v in c["variants"]:
                print(
                    f"  {v.get('order_code')} @ {v.get('order_date')}: "
                    f"gw={v['values'].get('gram_weight')} "
                    f"spp={v['values'].get('strips_per_pack')} "
                    f"ppc={v['values'].get('packs_per_carton')} "
                    f"spc={v['values'].get('strips_per_carton')} "
                    f"fnsku={v['values'].get('fnsku')} "
                    f"pack={v['values'].get('pack_method')}"
                )
        if not args.order_code:
            return

    entity = args.entity
    if not entity and args.order_code:
        from m1.canonical import normalize_entity_code

        entity = normalize_entity_code(args.order_code)
    if not entity:
        print("ERROR: need --entity or C04/C07 in --order-code")
        sys.exit(2)

    qty_plan = []
    if args.qty_plan:
        qty_plan = json.loads(Path(args.qty_plan).read_text(encoding="utf-8"))

    confirmed = {}
    if args.confirm_conflicts:
        confirmed = json.loads(Path(args.confirm_conflicts).read_text(encoding="utf-8"))

    settled = load_settled_products()
    # 若沉淀库空：用扫描结果中已确认前的候选作 pending（不自动入库）
    master_rows: list[dict] = []
    # 本地总表仅当目录有文件时由 04_ingest 确认后进入 settled；此处不自动读未确认总表

    assembled = assemble_order_lines(
        entity_code=entity,
        order_code=args.order_code,
        order_date=args.order_date,
        qty_plan=qty_plan,
        settled=settled,
        master_rows=master_rows,
        confirmed_resolutions=confirmed,
    )

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    draft_json = DRAFT_DIR / f"{args.order_code}_order_draft.json"
    draft_json.write_text(
        json.dumps(
            {
                "created_at": _utc_now(),
                "order_code": args.order_code,
                "entity_code": entity,
                "assembled": assembled,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"draft_json={draft_json}")
    print(f"lines_ready={len(assembled['lines'])} pending={len(assembled['pending'])}")

    if assembled["pending"]:
        print("BLOCKED: pending matches/conflicts — confirm before fill/finalize")
        for p in assembled["pending"]:
            print(json.dumps(p, ensure_ascii=False)[:300])
        sys.exit(3)

    if not assembled["lines"]:
        print("ERROR: no lines to fill")
        sys.exit(4)

    gate = cross_check_draft(assembled["lines"], settled)
    gate_path = REPORT_DIR / f"{args.order_code}_gate.json"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"gate_pass={gate['pass']} report={gate_path}")
    if not gate["pass"]:
        print("BLOCKED by gate")
        sys.exit(5)

    out_xlsx = DRAFT_DIR / f"{entity}_{args.order_code}_order_{datetime.now().strftime('%Y%m%d')}.xlsx"
    fill_order_template(
        order_code=args.order_code,
        order_date=args.order_date,
        delivery_date=args.delivery_date,
        entity_code=entity,
        lines=assembled["lines"],
        out_path=out_xlsx,
    )
    print(f"draft_xlsx={out_xlsx}")

    if args.finalize:
        final_dir = OUTPUT_DIR / args.order_code
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / out_xlsx.name
        final_path.write_bytes(out_xlsx.read_bytes())
        print(f"final={final_path}")
    else:
        print("draft only (pass --finalize after confirm to write 3_Output_Final)")


if __name__ == "__main__":
    main()
