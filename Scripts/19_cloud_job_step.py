# -*- coding: utf-8 -*-
"""
19_cloud_job_step.py — 云端作业步本地桥（供 web run API spawn）

用法（仓库根）:
  python Scripts/19_cloud_job_step.py --step gen_order|gen_product_labels|gen_trio \\
      --job-json path.json --work-dir path

成功时 stdout 末行: RESULT={...json...}
不写回本机 settled；输出写入 --work-dir 再由 Node 上传 Storage。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))


def _result(ok: bool, **kwargs) -> None:
    payload = {"ok": ok, **kwargs}
    print("RESULT=" + json.dumps(payload, ensure_ascii=False))


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def step_gen_order(job: dict, work: Path) -> int:
    from m1.assemble import assemble_order_lines, load_settled_products
    from m1.order_fill import fill_order_template

    meta = job.get("meta") or {}
    order_code = meta.get("order_code") or job.get("project_code")
    entity = job.get("entity_code")
    if not order_code or entity not in ("C04", "C07"):
        _result(False, error="missing order_code or entity_code")
        return 2

    lines_in = meta.get("lines") or []
    qty_plan = []
    for ln in lines_in:
        if not isinstance(ln, dict):
            continue
        qty_plan.append(
            {
                "size": ln.get("size"),
                "color": ln.get("color"),
                "qty_strips": ln.get("qty_strips"),
                "qty_cartons": ln.get("qty_cartons"),
                "strips_per_pack": ln.get("strips_per_pack"),
                "packs_per_carton": ln.get("packs_per_carton"),
                "strips_per_carton": ln.get("strips_per_carton"),
                "fnsku": ln.get("fnsku"),
                "gram_weight": ln.get("gram_weight"),
                "amazon_sku": ln.get("amazon_sku"),
            }
        )

    settled = load_settled_products()
    assembled = assemble_order_lines(
        entity_code=entity,
        order_code=order_code,
        order_date=meta.get("order_date"),
        qty_plan=qty_plan,
        settled=settled,
        master_rows=[],
        confirmed_resolutions={},
    )

    out_dir = work / "out" / "order"
    out_dir.mkdir(parents=True, exist_ok=True)
    draft_json = out_dir / f"{order_code}_order_draft.json"
    draft_json.write_text(
        json.dumps(
            {
                "created_at": _utc_now(),
                "order_code": order_code,
                "entity_code": entity,
                "assembled": assembled,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if assembled.get("pending"):
        _result(
            False,
            error="pending_matches_or_conflicts",
            pending=assembled["pending"][:20],
            draft_json=str(draft_json),
        )
        return 3

    if not assembled.get("lines"):
        _result(False, error="no_lines_to_fill", draft_json=str(draft_json))
        return 4

    from m1.order_fill import order_workbook_filename

    delivery = (meta.get("order_delivery_date") or job.get("ship_date") or "")[:10] or None
    out_xlsx = out_dir / order_workbook_filename(order_code, delivery)
    fill_order_template(
        order_code=order_code,
        order_date=meta.get("order_date"),
        delivery_date=delivery,
        entity_code=entity,
        lines=assembled["lines"],
        out_path=out_xlsx,
    )

    # —— 事后交叉核对（订单刚写入）——
    try:
        from m1.post_gen_verify import verify_order_artifact, write_report

        ord_report = verify_order_artifact(
            out_xlsx,
            order_code=order_code,
            entity_code=entity,
            ship_date=(job.get("ship_date") or "")[:10] or None,
        )
        write_report(ord_report)
        issues = [
            {
                "code": f"post_gen:{f.get('check')}",
                "message": f"expected={f.get('expected')!r} actual={f.get('actual')!r} {f.get('detail') or ''}",
            }
            for f in (ord_report.get("hard_failures") or [])
        ]
        if not ord_report.get("pass"):
            _result(
                False,
                step="gen_order",
                error="post_gen_order_failed",
                issues=issues,
                files=[
                    {
                        "section_id": "order_xlsx",
                        "path": str(out_xlsx),
                        "file_name": out_xlsx.name,
                    }
                ],
                post_gen=ord_report,
            )
            return 5
    except Exception as e:
        _result(
            False,
            step="gen_order",
            error="post_gen_order_error",
            issues=[{"code": "post_gen_order_error", "message": str(e)}],
        )
        return 5

    _result(
        True,
        step="gen_order",
        files=[
            {"section_id": "order_xlsx", "path": str(out_xlsx), "file_name": out_xlsx.name},
            {
                "section_id": "order_xlsx",
                "path": str(draft_json),
                "file_name": draft_json.name,
                "kind": "draft_json",
            },
        ],
        line_count=len(assembled["lines"]),
    )
    return 0


def step_gen_product_labels(job: dict, work: Path) -> int:
    """按订单行从桌布标签源只读复制 → 专属标签包（不改源）。"""
    from m1.label_copy import copy_product_labels

    meta = job.get("meta") or {}
    order_code = meta.get("order_code") or job.get("project_code")
    entity = job.get("entity_code")
    if not order_code or entity not in ("C04", "C07"):
        _result(False, error="missing order_code or entity_code")
        return 2

    lines = meta.get("lines") or []
    if not lines:
        _result(False, error="no_plan_lines_for_labels")
        return 3

    out_dir = work / "out" / "product_labels"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        report = copy_product_labels(
            order_code=order_code,
            entity_code=entity,
            lines=lines,
            dest_root=out_dir,
            require_source_stable=True,
        )
    except Exception as e:
        _result(False, error=f"label_copy_failed: {e}")
        return 4

    issues = []
    if report.get("missing"):
        issues.append(
            {
                "code": "label_missing",
                "message": f"{len(report['missing'])} 行未匹配到源标签",
                "detail": report["missing"][:20],
            }
        )
    if report.get("ambiguous"):
        issues.append(
            {
                "code": "label_ambiguous",
                "message": f"{len(report['ambiguous'])} 行源标签歧义",
                "detail": report["ambiguous"][:10],
            }
        )

    # —— 事后交叉核对（标签包身份）——
    if report.get("ok") and report.get("bundle_dir"):
        try:
            from m1.post_gen_verify import verify_labels_dir, write_report

            lab_report = verify_labels_dir(
                Path(report["bundle_dir"]), order_code=order_code
            )
            write_report(lab_report)
            for f in lab_report.get("hard_failures") or []:
                issues.append(
                    {
                        "code": f"post_gen:{f.get('check')}",
                        "message": f"expected={f.get('expected')!r} actual={f.get('actual')!r} {f.get('detail') or ''}",
                    }
                )
            if not lab_report.get("pass"):
                _result(
                    False,
                    step="gen_product_labels",
                    error="post_gen_labels_failed",
                    issues=issues,
                    files=report.get("files") or [],
                    post_gen=lab_report,
                    bundle_dir=report.get("bundle_dir"),
                )
                return 6
        except Exception as e:
            issues.append({"code": "post_gen_labels_error", "message": str(e)})
            _result(
                False,
                step="gen_product_labels",
                error="post_gen_labels_error",
                issues=issues,
            )
            return 6

    _result(
        bool(report.get("ok")),
        step="gen_product_labels",
        files=report.get("files") or [],
        copied=report.get("copied"),
        issues=issues,
        error=None if report.get("ok") else "label_copy_incomplete",
        bundle_dir=report.get("bundle_dir"),
    )
    return 0 if report.get("ok") else 5


def _build_headers_and_recognize(job: dict) -> tuple[dict, dict, list]:
    """从 carton_recognition + plan lines 物化 09 所需 JSON。"""
    meta = job.get("meta") or {}
    order_code = meta.get("order_code") or job.get("project_code")
    ship_date = (job.get("ship_date") or "")[:10]
    recog = meta.get("carton_recognition") or {}
    rows_in = recog.get("rows") or []
    issues = []
    if not rows_in:
        issues.append({"code": "no_carton_rows", "message": "无外箱贴确认识别行"})
        return {}, {}, issues
    if not recog.get("user_confirmed"):
        issues.append(
            {
                "code": "carton_unconfirmed",
                "message": "外箱贴识别未确认（仍尝试生成，请人工复核）",
            }
        )

    plan_lines = [ln for ln in (meta.get("lines") or []) if isinstance(ln, dict)]
    # 简易：按仓箱数比例分摊计划规格（无页级 FBA 规格时）
    total_cartons = sum(int(r.get("carton_count") or 0) for r in rows_in) or 1

    header_rows = []
    warehouses = []
    for r in rows_in:
        wh = (r.get("warehouse_code") or "").strip().upper()
        if not wh:
            issues.append({"code": "blank_warehouse", "message": f"行缺仓码: {r}"})
            continue
        cartons = int(r.get("carton_count") or 0)
        strips = r.get("strip_count")
        if strips is None:
            # 按箱占比分摊总条数
            total_strips = float(meta.get("total_strips") or 0)
            if not total_strips and plan_lines:
                total_strips = sum(float(ln.get("qty_strips") or 0) for ln in plan_lines)
            strips = int(round(total_strips * cartons / total_cartons)) if total_strips else 0
        strips = int(strips or 0)
        header_rows.append(
            {
                "warehouse_code": wh,
                "fba_shipment_id": r.get("fba_shipment_id") or "",
                "tracking_id": r.get("tracking_id") or recog.get("tracking_id") or "",
                "cartons": cartons,
                "strips": strips,
            }
        )
        # specs: share plan lines proportional (for master join); mark synthetic
        share = cartons / total_cartons
        specs = []
        for ln in plan_lines:
            qty = float(ln.get("qty_strips") or 0) * share
            ctn = float(ln.get("qty_cartons") or 0) * share
            if qty <= 0 and ctn <= 0:
                continue
            ctn_i = max(1, int(round(ctn))) if ctn else None
            specs.append(
                {
                    "fnsku": ln.get("fnsku"),
                    "size": ln.get("size"),
                    "color": ln.get("color"),
                    "strips_per_pack": ln.get("strips_per_pack"),
                    "packs_per_carton": ln.get("packs_per_carton"),
                    "strips": int(round(qty)),
                    "qty_strips": int(round(qty)),
                    "cartons": ctn_i,
                    "qty_cartons": ctn_i,
                    "synthetic_from_plan": True,
                }
            )
        warehouses.append({"warehouse_code": wh, "specs": specs})
        if not any(s.get("fnsku") for s in specs):
            issues.append(
                {
                    "code": "specs_without_fnsku",
                    "message": f"{wh}: 计划行无 FNSKU，货值可能为 0，须总表/识别补齐",
                }
            )

    headers = {
        "order_code": order_code,
        "ship_date": ship_date,
        "split_leg_id": f"{(meta.get('order_short') or 'LEG')}-A",
        "rows": header_rows,
    }
    recognize = {"warehouses": warehouses, "synthetic": True}
    return headers, recognize, issues


def step_gen_trio(job: dict, work: Path) -> int:
    """出货 + 货代 + 报关。"""
    from m1.outbound_fill import fill_outbound_template, format_outbound_filename

    meta = job.get("meta") or {}
    order_code = meta.get("order_code") or job.get("project_code")
    entity = job.get("entity_code")
    ship_date = (job.get("ship_date") or "")[:10]
    lines = meta.get("lines") or []
    issues: list[dict] = []
    files: list[dict] = []

    if not order_code or entity not in ("C04", "C07"):
        _result(False, error="missing order_code or entity_code", issues=issues)
        return 2
    if not lines:
        _result(False, error="no_plan_lines", issues=issues)
        return 3

    # —— 出货表 ——
    outbound_short = meta.get("outbound_short")
    if not outbound_short:
        issues.append(
            {
                "code": "outbound_short_missing",
                "message": "meta.outbound_short 缺失（创建作业时应已分配）",
            }
        )
        _result(False, step="gen_trio", error="outbound_short_missing", issues=issues)
        return 4

    out_ob = work / "out" / "outbound"
    out_ob.mkdir(parents=True, exist_ok=True)
    ob_name = format_outbound_filename(outbound_short, ship_date)
    ob_path = out_ob / ob_name
    try:
        fill_outbound_template(
            outbound_short=outbound_short,
            ship_date=ship_date,
            lines=lines,
            out_path=ob_path,
            order_code=order_code,
            order_short=meta.get("order_short"),
        )
        files.append(
            {"section_id": "outbound_xlsx", "path": str(ob_path), "file_name": ob_name}
        )
    except Exception as e:
        issues.append({"code": "outbound_fill_failed", "message": str(e)})
        _result(False, step="gen_trio", error="outbound_fill_failed", issues=issues, files=files)
        return 5

    # —— 事后交叉核对（出货刚写入）——
    try:
        from m1.post_gen_verify import verify_outbound_file, write_report

        brand = meta.get("brand") or {"C04": "WIGENIUS", "C07": "Dressmaker"}.get(
            entity, ""
        )
        ob_report = verify_outbound_file(
            ob_path,
            order_code=order_code,
            order_short=meta.get("order_short"),
            outbound_short=outbound_short,
            ship_date=ship_date,
            store=entity,
            brand=brand,
            strips=sum(float(x.get("qty_strips") or 0) for x in lines),
            lines=lines,
        )
        write_report(ob_report)
        for f in ob_report.get("hard_failures") or []:
            issues.append(
                {
                    "code": f"post_gen:{f.get('check')}",
                    "message": f"expected={f.get('expected')!r} actual={f.get('actual')!r} {f.get('detail') or ''}",
                }
            )
        if not ob_report.get("pass"):
            _result(
                False,
                step="gen_trio",
                error="post_gen_outbound_failed",
                issues=issues,
                files=files,
                post_gen=ob_report,
            )
            return 5
    except Exception as e:
        issues.append({"code": "post_gen_outbound_error", "message": str(e)})
        _result(
            False,
            step="gen_trio",
            error="post_gen_outbound_error",
            issues=issues,
            files=files,
        )
        return 5

    # —— 货代 / 报关（物化 JSON → 09）——
    headers, recognize, build_issues = _build_headers_and_recognize(job)
    issues.extend(build_issues)
    if not headers.get("rows"):
        _result(
            False,
            step="gen_trio",
            error="freight_customs_need_carton_rows",
            issues=issues,
            files=files,
        )
        return 6

    mid = work / "materialize"
    mid.mkdir(parents=True, exist_ok=True)
    headers_path = mid / "warehouse_headers.json"
    recognize_path = mid / "fba_recognize.json"
    headers_path.write_text(json.dumps(headers, ensure_ascii=False, indent=2), encoding="utf-8")
    recognize_path.write_text(json.dumps(recognize, ensure_ascii=False, indent=2), encoding="utf-8")

    freight_dir = work / "out" / "freight"
    customs_dir = work / "out" / "customs"
    freight_dir.mkdir(parents=True, exist_ok=True)
    customs_dir.mkdir(parents=True, exist_ok=True)

    project_stub = work / "project_stub"
    project_stub.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(SCRIPTS / "09_generate_freight_customs_drafts.py"),
        "--project",
        str(project_stub),
        "--recognize-json",
        str(recognize_path),
        "--headers-json",
        str(headers_path),
        "--order-code",
        order_code,
        "--ship-date",
        ship_date or "2026-07-31",
        "--leg-id",
        str(headers.get("split_leg_id") or "A"),
        "--out-freight-dir",
        str(freight_dir),
        "--out-customs-dir",
        str(customs_dir),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        issues.append(
            {
                "code": "freight_customs_script_failed",
                "message": (proc.stderr or proc.stdout or "")[-800:],
            }
        )
        _result(
            False,
            step="gen_trio",
            error="freight_customs_failed",
            issues=issues,
            files=files,
            stdout=proc.stdout[-500:],
        )
        return 7

    for p in sorted(freight_dir.glob("*.xlsx")):
        files.append(
            {"section_id": "freight_xlsx", "path": str(p), "file_name": p.name}
        )
    for p in sorted(customs_dir.glob("*.xlsx")):
        files.append(
            {"section_id": "customs_xlsx", "path": str(p), "file_name": p.name}
        )

    # —— 事后交叉核对（出货+货代+报关）——
    try:
        from m1.post_gen_verify import verify_gen_trio_artifacts, write_report

        trio_report = verify_gen_trio_artifacts(work, job)
        write_report(trio_report)
        for f in trio_report.get("hard_failures") or []:
            issues.append(
                {
                    "code": f"post_gen:{f.get('check')}",
                    "message": f"expected={f.get('expected')!r} actual={f.get('actual')!r} {f.get('detail') or ''}",
                }
            )
        if not trio_report.get("pass"):
            _result(
                False,
                step="gen_trio",
                error="post_gen_trio_failed",
                issues=issues,
                files=files,
                post_gen=trio_report,
            )
            return 9
    except Exception as e:
        issues.append({"code": "post_gen_trio_error", "message": str(e)})
        _result(
            False,
            step="gen_trio",
            error="post_gen_trio_error",
            issues=issues,
            files=files,
        )
        return 9

    # 货值 0 等警告视为 issues，但不一定整波失败（出货已成）
    soft = [i for i in issues if i.get("code") in ("specs_without_fnsku", "carton_unconfirmed")]
    hard = [i for i in issues if i not in soft]
    ok = len(hard) == 0 and any(f["section_id"] == "freight_xlsx" for f in files)
    _result(
        ok,
        step="gen_trio",
        files=files,
        issues=issues,
        error=None if ok else "trio_partial_or_warnings",
        note="outbound+freight+customs generated + post_gen cross-flow verify; Gate 前须确认",
    )
    return 0 if ok else 8


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True)
    ap.add_argument("--job-json", required=True)
    ap.add_argument("--work-dir", required=True)
    args = ap.parse_args()

    job = json.loads(Path(args.job_json).read_text(encoding="utf-8-sig"))
    work = Path(args.work_dir)
    work.mkdir(parents=True, exist_ok=True)

    if args.step == "gen_order":
        return step_gen_order(job, work)
    if args.step == "gen_product_labels":
        return step_gen_product_labels(job, work)
    if args.step == "gen_trio":
        return step_gen_trio(job, work)

    _result(False, error=f"unsupported_step:{args.step}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
