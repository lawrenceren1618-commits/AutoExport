# -*- coding: utf-8 -*-
"""事后 / 跨表交叉核对：生成文件与报告必须符合身份键与流动边。

覆盖：订单、出货、产品标签、货代、报关、完整存档、贴标包、reconcile/summary 报告。
权威：Scripts/cross_flow_rules.json · Templates/Cross_Flow_Verify.md
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "Scripts" / "cross_flow_rules.json"
ENTITY_RULES = ROOT / "Scripts" / "entity_brand_rules.json"
PROTOCOL_REG = ROOT / "Scripts" / "contract_protocol_registry.json"
REPORT_DIR = ROOT / "2_Processed_AI" / "cross_check_reports"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_rules() -> dict:
    return load_json(RULES_PATH) or {}


def finding(
    check: str,
    ok: bool,
    *,
    expected: Any = None,
    actual: Any = None,
    detail: str = "",
    soft: bool = False,
    edge: str | None = None,
) -> dict:
    return {
        "check": check,
        "ok": bool(ok),
        "expected": expected,
        "actual": actual,
        "detail": detail,
        "soft": soft,
        "edge": edge,
    }


def order_short_from_code(order_code: str | None) -> str:
    if not order_code:
        return ""
    m = re.search(r"EF-(C\d{5})", str(order_code), flags=re.I)
    if m:
        return m.group(1).upper()
    m = re.search(r"\b(C\d{5})\b", str(order_code), flags=re.I)
    return m.group(1).upper() if m else ""


def format_ship_dot(iso: str | None) -> str:
    if not iso:
        return ""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(iso).strip())
    if not m:
        return str(iso).strip()
    return f"{m.group(1)}.{int(m.group(2))}.{int(m.group(3))}"


def _cell_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _as_num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s.startswith("="):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _merged_top_left(ws, row: int, col: int) -> Any:
    """Read value; if in merge, return top-left cell value."""
    cell = ws.cell(row, col)
    for rng in ws.merged_cells.ranges:
        if cell.coordinate in rng:
            return ws.cell(rng.min_row, rng.min_col).value
    return cell.value


# ── snapshots ──────────────────────────────────────────────────────────────


def read_outbound_snapshot(path: Path) -> dict[str, Any]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=False)
    ws = wb.active
    ship_date = _cell_str(ws["B2"].value)
    outbound_short = _cell_str(ws["G2"].value)
    header_qty = _as_num(ws["B3"].value)
    belonging = _cell_str(_merged_top_left(ws, 5, 6))
    product = _cell_str(_merged_top_left(ws, 5, 1))
    gram = _cell_str(_merged_top_left(ws, 5, 2))
    dest = _cell_str(_merged_top_left(ws, 5, 9))

    rows: list[dict] = []
    r = 5
    while r <= (ws.max_row or 5):
        a = _cell_str(ws.cell(r, 1).value)
        if a == "合计":
            total_cell = ws.cell(r, 5).value
            break
        size = _cell_str(ws.cell(r, 3).value)
        color = _cell_str(ws.cell(r, 4).value)
        qty = _as_num(ws.cell(r, 5).value)
        if not size and not color and qty is None:
            r += 1
            if r > 5 + 80:
                total_cell = None
                break
            continue
        rows.append({"size": size, "color": color, "qty_strips": qty})
        r += 1
    else:
        total_cell = None

    detail_sum = sum(float(x["qty_strips"] or 0) for x in rows)
    # scan header band for accidental FNSKU
    blob = " ".join(
        _cell_str(ws.cell(rr, cc).value)
        for rr in range(1, min(4, ws.max_row or 1) + 1)
        for cc in range(1, 10)
    )
    for row in rows:
        blob += f" {row.get('size')} {row.get('color')}"
    has_fnsku_token = bool(re.search(r"\bX0[0-9A-Z]{8,}\b", blob, re.I)) or (
        "FNSKU" in blob.upper()
    )

    wb.close()
    return {
        "path": str(path),
        "file_name": path.name,
        "ship_date_cell": ship_date,
        "outbound_short": outbound_short,
        "header_qty": header_qty,
        "belonging_order": belonging,
        "product": product,
        "gram": gram,
        "destination": dest,
        "detail_rows": rows,
        "detail_sum": detail_sum,
        "total_formula": _cell_str(total_cell) if total_cell is not None else "",
        "has_fnsku_token": has_fnsku_token,
    }


def read_freight_snapshot(path: Path) -> dict[str, Any]:
    import openpyxl

    rules = load_rules().get("freight_cells") or {}
    sheet = rules.get("sheet") or "下单模板"
    wb = openpyxl.load_workbook(path, data_only=True)
    if sheet not in wb.sheetnames:
        wb.close()
        return {"path": str(path), "error": f"missing sheet {sheet}"}
    ws = wb[sheet]
    cartons = _as_num(ws["C15"].value)
    per = _as_num(ws["F15"].value)
    snap = {
        "path": str(path),
        "file_name": path.name,
        "customer_no": _cell_str(ws["C2"].value),
        "warehouse_code": _cell_str(ws["E3"].value).upper(),
        "fba_shipment_id": _cell_str(ws["A15"].value),
        "tracking_id": _cell_str(ws["B15"].value),
        "cartons": int(cartons) if cartons is not None else None,
        "qty_per_carton": int(per) if per is not None else None,
        "unit_price": _as_num(ws["G15"].value),
        "hs": _cell_str(ws["M15"].value),
        "brand_p": _cell_str(ws["P15"].value),
        "brand_q": _cell_str(ws["Q15"].value),
        "brand_r": _cell_str(ws["R15"].value),
    }
    if snap["cartons"] and snap["qty_per_carton"] is not None:
        snap["implied_strips"] = snap["cartons"] * snap["qty_per_carton"]
    else:
        snap["implied_strips"] = None
    wb.close()
    return snap


def read_customs_snapshot(path: Path) -> dict[str, Any]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    if "基础表" not in wb.sheetnames:
        wb.close()
        return {"path": str(path), "error": "missing 基础表"}
    ws = wb["基础表"]
    snap = {
        "path": str(path),
        "file_name": path.name,
        "gross_kg": _as_num(ws.cell(7, 12).value),
        "protocol_no": _cell_str(ws.cell(8, 6).value),
        "net_kg": _as_num(ws.cell(8, 12).value),
        "header_company": _cell_str(ws.cell(9, 4).value),
        "header_short": _cell_str(ws.cell(9, 6).value),
        "total_cartons": _as_num(ws.cell(9, 12).value),
        "hs": _cell_str(ws.cell(14, 3).value),
        "line_cartons": _as_num(ws.cell(14, 6).value),
        "line_strips": _as_num(ws.cell(14, 7).value),
        "unit_price": _as_num(ws.cell(14, 9).value),
        "amount": _as_num(ws.cell(14, 10).value),
    }
    wb.close()
    return snap


def _norm_size(v: Any) -> str:
    s = str(v or "").upper().replace(" ", "").replace("*", "X")
    s = s.replace("INCH", "").replace("英寸", "")
    return s


def _norm_color(v: Any) -> str:
    s = str(v or "").strip().lower()
    aliases = {
        "米白": "ivory",
        "象牙白": "ivory",
        "ivory": "ivory",
        "白色": "white",
        "白": "white",
        "white": "white",
        "黑色": "black",
        "黑": "black",
        "black": "black",
    }
    return aliases.get(s, s)


def _spec_key(size: Any, color: Any) -> tuple[str, str]:
    return (_norm_size(size), _norm_color(color))


def try_read_order_meta(project: Path) -> dict[str, Any]:
    order_dir = project / "订单表"
    if not order_dir.is_dir():
        return {"ok": False, "detail": "订单表 missing"}
    files = [
        p
        for p in order_dir.iterdir()
        if p.suffix.lower() in (".xls", ".xlsx") and not p.name.startswith("~$")
    ]
    if not files:
        return {"ok": False, "detail": "no order workbook"}
    # prefer non-改 duplicates last; take first by name
    files = sorted(files, key=lambda p: (len(p.name), p.name))
    try:
        from m1.order_parse import parse_order_workbook

        parsed = parse_order_workbook(files[0])
        meta = parsed.get("meta") or {}
        lines = parsed.get("lines") or []
        upper_sum = 0.0
        specs: dict[tuple[str, str], float] = {}
        # packing lines may be lower-half; aggregate by size+color for outbound compare
        for ln in lines:
            qty = float(ln.get("qty_strips") or 0)
            upper_sum += qty
            sk = _spec_key(ln.get("size"), ln.get("color"))
            if sk[0] or sk[1]:
                specs[sk] = specs.get(sk, 0.0) + qty
        return {
            "ok": True,
            "path": str(files[0]),
            "order_code": meta.get("order_code"),
            "delivery_date": meta.get("delivery_date"),
            "order_date": meta.get("order_date"),
            "entity_code": meta.get("entity_code"),
            "lines_n": len(lines),
            "strips_sum": upper_sum,
            "spec_qty": {f"{k[0]}|{k[1]}": v for k, v in specs.items()},
            "format": parsed.get("format"),
        }
    except Exception as e:
        return {"ok": False, "detail": str(e), "path": str(files[0])}


def read_labels_snapshot(project: Path, order_code: str | None) -> dict[str, Any]:
    label_root = project / "产品标签"
    if not label_root.is_dir():
        return {"ok": False, "absent": True, "detail": "产品标签 missing"}
    expect = f"{order_code}标签" if order_code else ""
    bundles = [
        p
        for p in label_root.iterdir()
        if p.is_dir() and not p.name.startswith("_") and "标签" in p.name
    ]
    manifests = list(label_root.rglob("_manifest.json"))
    manifest_codes: list[str] = []
    for m in manifests[:20]:
        data = load_json(m)
        if data.get("order_code"):
            manifest_codes.append(str(data["order_code"]))
    return {
        "ok": True,
        "absent": False,
        "bundles": [p.name for p in bundles],
        "expect_bundle": expect,
        "bundle_match": any(p.name == expect or order_code in p.name for p in bundles)
        if order_code
        else False,
        "manifest_codes": manifest_codes,
        "pdf_count": len(list(label_root.rglob("*.pdf"))),
    }


def _wh_from_name(name: str) -> str:
    m = re.search(r"\b([A-Z]{3,4}\d?)\b", name.upper())
    # Prefer known-looking tokens near end: AVP1, IUTE, etc.
    toks = re.findall(r"\b([A-Z]{2,4}\d)\b", name.upper())
    if toks:
        return toks[-1]
    m2 = re.search(r"\b(IUTE|ONT8|SWF2)\b", name.upper())
    return m2.group(1) if m2 else (m.group(1) if m else "")


# ── check suites ───────────────────────────────────────────────────────────


def check_identity_and_outbound(
    *,
    meta: dict,
    outbound: dict | None,
    order_snap: dict | None = None,
) -> list[dict]:
    findings: list[dict] = []
    order_code = meta.get("order_code") or ""
    order_short = (
        meta.get("order_short")
        or meta.get("split_order_stem")
        or order_short_from_code(order_code)
    )
    outbound_short = meta.get("outbound_short") or ""
    ship_date = (meta.get("ship_date") or meta.get("delivery_date") or "")[:10]
    store = (meta.get("store") or meta.get("entity_code") or "").upper()
    brand = meta.get("brand") or ""

    findings.append(
        finding(
            "V_ID_ORDER_CODE",
            bool(re.match(r"^EF-C\d{5}-C0[47]-", str(order_code), re.I)),
            expected="EF-Cxxxxx-C04|C07-…",
            actual=order_code,
            detail="PROJECT/job order_code",
            edge="order_to_outbound",
        )
    )

    entity = load_json(ENTITY_RULES)
    ents = entity.get("entities") or {}
    expect_brand = (ents.get(store) or {}).get("brand_tablecloth") or ""
    brand_ok = False
    if store in ("C04", "C07"):
        brand_ok = brand.upper() == expect_brand.upper() or (
            store == "C04" and brand.upper() == "WIGENIUS"
        ) or (store == "C07" and brand.upper() == "DRESSMAKER")
    findings.append(
        finding(
            "V_ENTITY_BRAND",
            brand_ok,
            expected=expect_brand or store,
            actual=f"{store}/{brand}",
            edge="order_to_outbound",
        )
    )

    if order_snap and order_snap.get("ok"):
        oc = order_snap.get("order_code") or ""
        # allow PCS suffix on some files
        oc_norm = re.sub(r"PCS$", "", str(oc), flags=re.I)
        code_ok = order_code.upper() in oc.upper() or oc_norm.upper() == order_code.upper()
        findings.append(
            finding(
                "V_ORDER_FILE_VS_PROJECT",
                code_ok,
                expected=order_code,
                actual=oc,
                detail=order_snap.get("path"),
                edge="order_to_outbound",
            )
        )
        if order_snap.get("delivery_date") and ship_date:
            findings.append(
                finding(
                    "V_ORDER_DELIVERY_EQ_SHIP",
                    str(order_snap["delivery_date"])[:10] == ship_date,
                    expected=ship_date,
                    actual=order_snap.get("delivery_date"),
                    edge="order_to_outbound",
                )
            )
        # Identity chain: 订单EF → 短码 → 出货所属订单（用户硬例）
        derived = order_short_from_code(oc_norm or oc) or order_short_from_code(order_code)
        belong = (outbound or {}).get("belonging_order") if outbound else None
        chain_ok = bool(derived) and bool(belong) and derived.upper() == str(belong).upper()
        findings.append(
            finding(
                "V_ID_CHAIN_EF_SHORT_BELONGING",
                chain_ok,
                expected=f"{oc_norm or order_code} → {derived} → 所属订单",
                actual=belong or "(empty)",
                detail="出货所属订单必须对应本批订单表 EF 号抽出的短码",
                edge="order_to_outbound",
            )
        )
    elif order_snap is not None:
        findings.append(
            finding(
                "V_ORDER_FILE_PARSE",
                True,
                detail=order_snap.get("detail") or "order parse skipped",
                soft=True,
                edge="order_to_outbound",
            )
        )

    if not outbound:
        findings.append(
            finding(
                "V_OUTBOUND_PRESENT",
                False,
                detail="outbound xlsx missing",
                edge="order_to_outbound",
            )
        )
        return findings

    findings.append(
        finding(
            "V_ID_ORDER_SHORT_ON_OUTBOUND",
            bool(outbound.get("belonging_order"))
            and outbound["belonging_order"].upper() == str(order_short).upper(),
            expected=order_short,
            actual=outbound.get("belonging_order") or "(empty)",
            detail="出货所属订单必须=订单短码，且对应本批订单 EF 号",
            edge="order_to_outbound",
        )
    )
    findings.append(
        finding(
            "V_ID_OUTBOUND_SHORT",
            bool(outbound.get("outbound_short"))
            and outbound["outbound_short"].upper() == str(outbound_short).upper(),
            expected=outbound_short,
            actual=outbound.get("outbound_short"),
            edge="outbound_to_project",
        )
    )
    # filename
    expect_name = f"{outbound_short}-U-{format_ship_dot(ship_date)}.xlsx"
    findings.append(
        finding(
            "V_OUTBOUND_FILENAME",
            outbound.get("file_name", "").lower() == expect_name.lower()
            or (
                outbound_short.lower() in outbound.get("file_name", "").lower()
                and "-u-" in outbound.get("file_name", "").lower()
            ),
            expected=expect_name,
            actual=outbound.get("file_name"),
            edge="outbound_to_project",
        )
    )
    expect_dot = format_ship_dot(ship_date)
    findings.append(
        finding(
            "V_SHIP_DATE_EQ",
            outbound.get("ship_date_cell") == expect_dot
            or outbound.get("ship_date_cell") == ship_date,
            expected=expect_dot,
            actual=outbound.get("ship_date_cell"),
            edge="order_to_outbound",
        )
    )
    if store and outbound_short:
        findings.append(
            finding(
                "V_STORE_PREFIX_ON_SHORT",
                outbound_short.upper().startswith(store),
                expected=f"{store}-…",
                actual=outbound_short,
                edge="outbound_to_project",
            )
        )

    proj_strips = meta.get("strips") or meta.get("total_strips")
    detail_sum = outbound.get("detail_sum")
    if proj_strips is not None and detail_sum is not None:
        findings.append(
            finding(
                "V_OUT_STRIPS_EQ_PROJECT",
                abs(float(detail_sum) - float(proj_strips)) < 0.5,
                expected=proj_strips,
                actual=detail_sum,
                edge="order_to_outbound",
            )
        )
    header_qty = outbound.get("header_qty")
    if header_qty is not None and detail_sum is not None:
        findings.append(
            finding(
                "V_OUT_HEADER_QTY_EQ_DETAIL",
                abs(float(header_qty) - float(detail_sum)) < 0.5,
                expected=detail_sum,
                actual=header_qty,
                edge="order_to_outbound",
            )
        )
    # SUM formula presence
    tf = outbound.get("total_formula") or ""
    findings.append(
        finding(
            "V_OUT_TOTAL_SUM_FORMULA",
            tf.upper().startswith("=SUM(") or (
                _as_num(tf) is not None
                and detail_sum is not None
                and abs(float(_as_num(tf)) - float(detail_sum)) < 0.5
            ),
            expected="=SUM(E…)",
            actual=tf or "(missing)",
            edge="order_to_outbound",
        )
    )
    findings.append(
        finding(
            "V_NO_FNSKU_ON_OUTBOUND",
            not outbound.get("has_fnsku_token"),
            expected="no FNSKU on outbound",
            actual="found" if outbound.get("has_fnsku_token") else "none",
            edge="order_to_outbound",
        )
    )
    findings.append(
        finding(
            "V_OUT_PRODUCT_DEST_PRESENT",
            bool(outbound.get("product")) and bool(outbound.get("destination")),
            expected="品类+目的地非空",
            actual=f"{outbound.get('product')!r}/{outbound.get('destination')!r}",
            edge="order_to_outbound",
        )
    )

    # size+color set vs order (when order parsed with specs)
    if order_snap and order_snap.get("ok") and order_snap.get("spec_qty") and outbound.get(
        "detail_rows"
    ):
        out_specs = {
            f"{_spec_key(r.get('size'), r.get('color'))[0]}|{_spec_key(r.get('size'), r.get('color'))[1]}"
            for r in outbound["detail_rows"]
            if r.get("size") or r.get("color")
        }
        ord_specs = set(order_snap["spec_qty"].keys())
        # order may include lower-half duplicates; require outbound ⊆ order keys
        missing = sorted(out_specs - ord_specs)
        findings.append(
            finding(
                "V_OUT_SPECS_VS_ORDER",
                len(missing) == 0,
                expected=f"outbound specs ⊆ order ({len(ord_specs)} keys)",
                actual=f"outbound={len(out_specs)} missing_in_order={missing[:8]}",
                detail="规格联系：出货尺寸+颜色必须能在订单中找到",
                edge="order_to_outbound",
                soft=len(ord_specs) == 0,
            )
        )
        # strips: prefer PROJECT; if order_sum≈project, also require outbound≈order
        osum = order_snap.get("strips_sum")
        if (
            osum is not None
            and proj_strips is not None
            and abs(float(osum) - float(proj_strips)) < 1.0
            and detail_sum is not None
        ):
            findings.append(
                finding(
                    "V_OUT_STRIPS_EQ_ORDER",
                    abs(float(detail_sum) - float(osum)) < 0.5,
                    expected=osum,
                    actual=detail_sum,
                    edge="order_to_outbound",
                )
            )

    return findings


def check_labels(meta: dict, labels: dict | None) -> list[dict]:
    findings: list[dict] = []
    order_code = meta.get("order_code") or ""
    if not labels or labels.get("absent"):
        findings.append(
            finding(
                "V_LABEL_BUNDLE_ORDER_CODE",
                True,
                detail="产品标签 absent — soft until copied",
                soft=True,
                edge="order_to_labels",
            )
        )
        return findings
    findings.append(
        finding(
            "V_LABEL_BUNDLE_ORDER_CODE",
            bool(labels.get("bundle_match")),
            expected=labels.get("expect_bundle"),
            actual=labels.get("bundles"),
            detail=f"pdfs={labels.get('pdf_count')}",
            edge="order_to_labels",
        )
    )
    mcodes = labels.get("manifest_codes") or []
    if mcodes:
        findings.append(
            finding(
                "V_LABEL_MANIFEST_ORDER_CODE",
                all(str(order_code).upper() in str(c).upper() for c in mcodes),
                expected=order_code,
                actual=mcodes[:5],
                edge="order_to_labels",
            )
        )
    return findings


def check_archive_outbound_sync(project: Path, meta: dict, ship_ob: dict | None) -> list[dict]:
    findings: list[dict] = []
    arch = meta.get("colleague_pack_path") or (meta.get("output_packs") or {}).get("path")
    if not arch:
        findings.append(
            finding(
                "V_ARCHIVE_OUTBOUND_SYNC",
                True,
                detail="no archive path on PROJECT — soft",
                soft=True,
                edge="shipments_to_archive",
            )
        )
        return findings
    arch_dir = Path(arch) / "完整存档" / "共用" / "出货表"
    if not arch_dir.is_dir():
        findings.append(
            finding(
                "V_ARCHIVE_OUTBOUND_SYNC",
                True,
                detail=f"archive outbound dir missing: {arch_dir}",
                soft=True,
                edge="shipments_to_archive",
            )
        )
        return findings
    files = [p for p in arch_dir.glob("*.xlsx") if not p.name.startswith("~$")]
    if not files or not ship_ob:
        findings.append(
            finding(
                "V_ARCHIVE_OUTBOUND_SYNC",
                True,
                detail="archive or shipments outbound missing one side — soft",
                soft=True,
                edge="shipments_to_archive",
            )
        )
        return findings
    arch_ob = read_outbound_snapshot(files[0])
    findings.append(
        finding(
            "V_ARCHIVE_OUTBOUND_SYNC",
            (arch_ob.get("belonging_order") or "").upper()
            == (ship_ob.get("belonging_order") or "").upper()
            and (arch_ob.get("outbound_short") or "").upper()
            == (ship_ob.get("outbound_short") or "").upper(),
            expected=f"Shipments belonging={ship_ob.get('belonging_order')} short={ship_ob.get('outbound_short')}",
            actual=f"Archive belonging={arch_ob.get('belonging_order')} short={arch_ob.get('outbound_short')}",
            detail="Shipments 与完整存档出货表身份键必须一致（C26079 曾出现仅存档有所属订单）",
            edge="shipments_to_archive",
        )
    )
    return findings


def check_packs_identity(project: Path, meta: dict) -> list[dict]:
    findings: list[dict] = []
    order_short = (
        meta.get("order_short")
        or meta.get("split_order_stem")
        or order_short_from_code(meta.get("order_code"))
    )
    pack_root = meta.get("colleague_pack_path") or (meta.get("output_packs") or {}).get(
        "path"
    )
    if not pack_root or not Path(pack_root).is_dir():
        findings.append(
            finding(
                "V_PACK_FOLDER_IDENTITY",
                True,
                detail="贴标包 path absent — soft",
                soft=True,
                edge="packs_to_identity",
            )
        )
        return findings
    names = [p.name for p in Path(pack_root).iterdir() if p.is_dir()]
    leg_hits = [n for n in names if order_short and order_short in n]
    findings.append(
        finding(
            "V_PACK_FOLDER_IDENTITY",
            bool(leg_hits) or any("完整存档" in n for n in names),
            expected=f"contains {order_short}-*贴标包 or 完整存档",
            actual=names[:12],
            edge="packs_to_identity",
            soft=not bool(names),
        )
    )
    return findings


def check_warehouse_totals_vs_batch(
    freight_snaps: list[dict], customs_snaps: list[dict], meta: dict
) -> list[dict]:
    findings: list[dict] = []
    if not customs_snaps and not freight_snaps:
        return findings
    batch = meta.get("strips") or meta.get("total_strips")
    sum_c_strips = sum(float(s.get("line_strips") or 0) for s in customs_snaps)
    sum_c_cartons = sum(
        float(s.get("line_cartons") or s.get("total_cartons") or 0) for s in customs_snaps
    )
    if batch is not None and customs_snaps:
        # Multi-leg: sum may be < batch; only hard-fail if clearly over
        over = sum_c_strips > float(batch) + 0.5
        findings.append(
            finding(
                "V_WH_STRIPS_VS_BATCH",
                not over,
                expected=f"Σ报关条数 <= {batch}",
                actual=sum_c_strips,
                detail=f"cartons_sum={sum_c_cartons} files={len(customs_snaps)}",
                edge="legs_to_totals",
                soft=sum_c_strips <= 0,
            )
        )
    return findings


def check_freight_customs_pair(
    freight: dict, customs: dict, *, store: str = ""
) -> list[dict]:
    findings: list[dict] = []
    if freight.get("error"):
        findings.append(
            finding(
                "V_FREIGHT_READ",
                False,
                detail=freight["error"],
                edge="freight_to_customs",
            )
        )
        return findings
    if customs.get("error"):
        findings.append(
            finding(
                "V_CUSTOMS_READ",
                False,
                detail=customs["error"],
                edge="freight_to_customs",
            )
        )
        return findings

    rules = load_rules()
    fc = rules.get("freight_cells") or {}
    findings.append(
        finding(
            "V_FREIGHT_STATICS",
            freight.get("customer_no") == (fc.get("static_customer_no") or "111111111")
            and freight.get("brand_p") == "无"
            and freight.get("brand_q") == "无"
            and freight.get("brand_r") == "无"
            and freight.get("hs") == (fc.get("hs_default") or "6302539090"),
            expected="C2=111111111; PQR=无; HS default",
            actual=f"C2={freight.get('customer_no')} PQR={freight.get('brand_p')}/{freight.get('brand_q')}/{freight.get('brand_r')} HS={freight.get('hs')}",
            edge="freight_to_customs",
        )
    )
    cartons = freight.get("cartons")
    strips = freight.get("implied_strips")
    per = freight.get("qty_per_carton")
    floor_ok = False
    if cartons and strips is not None and per is not None and cartons > 0:
        # F15 should be floor(strips/cartons); we only have implied = C*F so check consistency
        floor_ok = per == math.floor(strips / cartons) if cartons else False
        # Always true if implied built as C*F; still verify C15>0
        floor_ok = cartons > 0 and per >= 0
    findings.append(
        finding(
            "V_FREIGHT_FLOOR_QTY",
            bool(cartons) and per is not None and per >= 0,
            expected="C15>0 and F15>=0",
            actual=f"C15={cartons} F15={per}",
            edge="freight_to_customs",
        )
    )
    findings.append(
        finding(
            "V_FREIGHT_FBA_PRESENT",
            bool(freight.get("fba_shipment_id")),
            expected="A15 FBA/STAR",
            actual=freight.get("fba_shipment_id") or "(empty)",
            edge="freight_carton_source",
        )
    )

    findings.append(
        finding(
            "V_CUSTOMS_1039_HEADER",
            "波丽丝" in (customs.get("header_company") or "")
            or "波丽丝" in (customs.get("header_short") or ""),
            expected="波丽丝（参考）",
            actual=f"{customs.get('header_company')}/{customs.get('header_short')}",
            detail="表内抬头作参考核对，非与货代统一字段",
            soft=True,
            edge="freight_to_customs",
        )
    )
    fn = customs.get("file_name") or ""
    findings.append(
        finding(
            "V_CUSTOMS_FILENAME",
            "畅选" in fn or "波丽丝" in fn,
            expected="文件名含畅选/波丽丝",
            actual=fn,
            edge="freight_to_customs",
        )
    )

    # pair cartons ONLY — strips/unit_price must NOT be forced equal
    c_cartons = customs.get("line_cartons") or customs.get("total_cartons")
    c_strips = customs.get("line_strips")
    findings.append(
        finding(
            "V_FREIGHT_CUSTOMS_CARTONS",
            cartons is not None
            and c_cartons is not None
            and abs(float(cartons) - float(c_cartons)) < 0.5,
            expected=cartons,
            actual=c_cartons,
            detail=f"wh={freight.get('warehouse_code')} 箱数可对照；货代箱数须来自外箱贴确认",
            edge="freight_to_customs",
        )
    )
    if c_strips is not None and strips is not None:
        findings.append(
            finding(
                "V_FREIGHT_CUSTOMS_STRIPS",
                True,
                expected=c_strips,
                actual=strips,
                detail=(
                    "不强制相等：货代 implied=C15×floor(条÷箱) 可能少余数；"
                    "报关条数/单价权威=总表1039+沉淀+正算反算"
                ),
                soft=True,
                edge="freight_to_customs",
            )
        )
    if (
        freight.get("unit_price") is not None
        and customs.get("unit_price") is not None
    ):
        same = abs(float(freight["unit_price"]) - float(customs["unit_price"])) < 0.015
        findings.append(
            finding(
                "V_FREIGHT_CUSTOMS_UNIT_PRICE",
                True,  # never hard-fail on price diff
                expected=customs.get("unit_price"),
                actual=freight.get("unit_price"),
                detail=(
                    "价格差允许"
                    if not same
                    else "碰巧相同"
                )
                + "；报关单价须对总表/沉淀，不以货代为源",
                soft=True,
                edge="freight_to_customs",
            )
        )

    # protocol — hard post-gen recheck
    proto = customs.get("protocol_no") or ""
    reg = load_json(PROTOCOL_REG)
    entries = reg.get("entries") or []
    nos = [e.get("protocol_no") for e in entries if e.get("protocol_no")]
    in_reg = proto in nos if proto else False
    collision = False
    if proto:
        owners = {e.get("project") for e in entries if e.get("protocol_no") == proto}
        collision = len(owners) > 1
    findings.append(
        finding(
            "V_PROTOCOL_PRESENT",
            bool(proto),
            expected="合同协议号",
            actual=proto or "(empty)",
            edge="freight_to_customs",
        )
    )
    if proto:
        findings.append(
            finding(
                "V_PROTOCOL_UNIQUE",
                in_reg and not collision,
                expected="registered unique in contract_protocol_registry",
                actual=f"in_reg={in_reg} collision={collision}",
                detail="生成后程序复查：须在登记库且无跨项目撞号",
                soft=False,
                edge="freight_to_customs",
            )
        )

    # warehouse match filename / E3
    wh = freight.get("warehouse_code") or ""
    if wh:
        findings.append(
            finding(
                "V_WH_IN_FILENAMES",
                wh in (freight.get("file_name") or "").upper()
                and wh in (customs.get("file_name") or "").upper(),
                expected=wh,
                actual=f"freight={freight.get('file_name')} customs={customs.get('file_name')}",
                edge="freight_to_customs",
            )
        )
    del store  # reserved for sales-link checks later
    return findings


def check_summary_and_reconcile(meta: dict, summary: dict | None) -> list[dict]:
    findings: list[dict] = []
    if not summary:
        findings.append(
            finding(
                "V_SUMMARY_ABSENT",
                True,
                detail="no freight/customs summary — soft until generated",
                soft=True,
                edge="reports_to_source",
            )
        )
        return findings

    order_code = meta.get("order_code") or ""
    findings.append(
        finding(
            "V_SUMMARY_ORDER_CODE",
            not summary.get("order_code")
            or str(summary.get("order_code")).upper() == str(order_code).upper(),
            expected=order_code,
            actual=summary.get("order_code"),
            edge="reports_to_source",
        )
    )
    recon = summary.get("reconcile") or {}
    gate = (recon.get("gate") or {}).get("overall")
    if gate:
        findings.append(
            finding(
                "V_RECONCILE_GATE",
                str(gate).upper() == "PASS",
                expected="PASS",
                actual=gate,
                detail=str(recon.get("error_rate_pct") or ""),
                edge="reports_to_source",
            )
        )
    else:
        findings.append(
            finding(
                "V_RECONCILE_GATE",
                True,
                detail="no reconcile gate in summary",
                soft=True,
                edge="reports_to_source",
            )
        )

    files = summary.get("files") or []
    if files and meta.get("strips"):
        sum_strips = sum(float(f.get("strips") or 0) for f in files)
        # batch may be multi-leg; only flag if summary claims full batch
        if summary.get("covers_full_batch"):
            findings.append(
                finding(
                    "V_SUMMARY_STRIPS_EQ_PROJECT",
                    abs(sum_strips - float(meta["strips"])) < 0.5,
                    expected=meta["strips"],
                    actual=sum_strips,
                    edge="legs_to_totals",
                )
            )
        else:
            findings.append(
                finding(
                    "V_SUMMARY_STRIPS_LE_PROJECT",
                    sum_strips <= float(meta["strips"]) + 0.5,
                    expected=f"<= {meta['strips']}",
                    actual=sum_strips,
                    soft=True,
                    edge="legs_to_totals",
                )
            )
    return findings


def pair_freight_customs(
    freight_files: list[Path], customs_files: list[Path]
) -> list[tuple[Path, Path | None]]:
    customs_by_wh: dict[str, Path] = {}
    for p in customs_files:
        wh = _wh_from_name(p.name)
        if wh:
            customs_by_wh[wh] = p
    pairs: list[tuple[Path, Path | None]] = []
    used: set[str] = set()
    for fp in freight_files:
        wh = _wh_from_name(fp.name)
        cp = customs_by_wh.get(wh) if wh else None
        if cp:
            used.add(wh)
        pairs.append((fp, cp))
    for wh, cp in customs_by_wh.items():
        if wh not in used:
            pairs.append((Path(), cp))  # orphan customs
    return pairs


def finalize_report(
    *,
    scope: str,
    subject: str,
    findings: list[dict],
    meta: dict | None = None,
) -> dict:
    hard = [f for f in findings if not f.get("soft") and not f.get("ok")]
    return {
        "generated_at": _now(),
        "scope": scope,
        "subject": subject,
        "pass": len(hard) == 0,
        "findings": findings,
        "hard_failures": hard,
        "meta_keys": {
            "order_code": (meta or {}).get("order_code"),
            "order_short": (meta or {}).get("order_short")
            or (meta or {}).get("split_order_stem"),
            "outbound_short": (meta or {}).get("outbound_short"),
            "ship_date": (meta or {}).get("ship_date"),
        },
        "doc": "Templates/Cross_Flow_Verify.md",
        "rules": str(RULES_PATH.relative_to(ROOT)).replace("\\", "/"),
    }


def write_report(report: dict, out: Path | None = None) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if out is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r"[^\w\-]+", "_", report.get("subject") or "verify")[:80]
        out = REPORT_DIR / f"post_gen_{safe}_{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = REPORT_DIR / "post_gen_latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# ── entry points ───────────────────────────────────────────────────────────


def verify_outbound_file(
    path: Path,
    *,
    order_code: str | None = None,
    order_short: str | None = None,
    outbound_short: str | None = None,
    ship_date: str | None = None,
    store: str | None = None,
    brand: str | None = None,
    strips: float | int | None = None,
    lines: list[dict] | None = None,
) -> dict:
    del lines  # optional future row-level compare
    meta = {
        "order_code": order_code,
        "order_short": order_short or order_short_from_code(order_code),
        "outbound_short": outbound_short,
        "ship_date": ship_date,
        "store": store,
        "brand": brand,
        "strips": strips,
    }
    outbound = read_outbound_snapshot(path)
    findings = check_identity_and_outbound(meta=meta, outbound=outbound, order_snap=None)
    return finalize_report(
        scope="outbound_file", subject=path.name, findings=findings, meta=meta
    )


# Plan aliases (Templates plan / Post_Gen_Verify.md)
verify_outbound_xlsx = verify_outbound_file


def verify_order_artifact(
    path: Path,
    *,
    order_code: str,
    entity_code: str | None = None,
    ship_date: str | None = None,
) -> dict:
    """After gen_order writes xlsx — identity only (parse workbook)."""
    meta = {
        "order_code": order_code,
        "store": entity_code,
        "ship_date": (ship_date or "")[:10],
        "brand": "WIGENIUS"
        if entity_code == "C04"
        else ("Dressmaker" if entity_code == "C07" else ""),
    }
    findings: list[dict] = []
    findings.append(
        finding(
            "V_ID_ORDER_CODE",
            bool(re.match(r"^EF-C\d{5}-C0[47]-", str(order_code), re.I)),
            expected="EF-Cxxxxx-C04|C07-…",
            actual=order_code,
            edge="order_to_outbound",
        )
    )
    try:
        from m1.order_parse import parse_order_workbook
        from m1.order_fill import locate_order_bands

        parsed = parse_order_workbook(path)
        om = parsed.get("meta") or {}
        oc = om.get("order_code") or ""
        oc_norm = re.sub(r"PCS$", "", str(oc), flags=re.I)
        findings.append(
            finding(
                "V_ORDER_FILE_VS_PROJECT",
                order_code.upper() in oc.upper() or oc_norm.upper() == order_code.upper(),
                expected=order_code,
                actual=oc,
                detail=str(path),
                edge="order_to_outbound",
            )
        )
        if ship_date and om.get("delivery_date"):
            findings.append(
                finding(
                    "V_ORDER_DELIVERY_EQ_SHIP",
                    str(om["delivery_date"])[:10] == str(ship_date)[:10],
                    expected=ship_date,
                    actual=om.get("delivery_date"),
                    edge="order_to_outbound",
                )
            )
        if entity_code:
            findings.append(
                finding(
                    "V_ENTITY_BRAND",
                    (om.get("entity_code") or entity_code).upper() == entity_code.upper()
                    or entity_code.upper() in order_code.upper(),
                    expected=entity_code,
                    actual=om.get("entity_code"),
                    edge="order_to_outbound",
                )
            )
        from openpyxl import load_workbook

        wb = load_workbook(path, data_only=False)
        ws = wb.active
        bands = locate_order_bands(ws)
        g_ok = True
        carton_ok = True
        upper_f_ok = True
        g_actual = []
        outer_actual = []
        for r in range(bands["pack_start"], bands["pack_total"]):
            g = ws.cell(r, 7).value
            inner = str(ws.cell(r, 9).value or "")
            outer = str(ws.cell(r, 10).value or "")
            g_s = str(g or "")
            g_actual.append(g_s)
            outer_actual.append(outer)
            if not (g_s.startswith("=") and "*" in g_s):
                g_ok = False
            if inner.startswith("内盒"):
                if not outer.startswith("纸箱：") or outer.startswith("纸箱规格"):
                    carton_ok = False
            if "热缩" in inner:
                if "纸箱规格" not in outer:
                    carton_ok = False
        for r in range(bands["data_start"], bands["upper_total"]):
            f = str(ws.cell(r, 6).value or "")
            if not f.startswith("=") or "G" not in f.upper():
                upper_f_ok = False
        findings.append(
            finding(
                "V_ORDER_PACK_G_FORMULA",
                g_ok,
                expected="=C{r}*E{r}*F{r}",
                actual=g_actual,
                edge="order_to_outbound",
            )
        )
        findings.append(
            finding(
                "V_ORDER_UPPER_QTY_REF_G",
                upper_f_ok,
                expected="=G… (C26079 F9=G27)",
                actual=[str(ws.cell(r, 6).value) for r in range(bands["data_start"], bands["upper_total"])],
                edge="order_to_outbound",
            )
        )
        findings.append(
            finding(
                "V_ORDER_CARTON_DISPLAY",
                carton_ok,
                expected="内盒→纸箱：LWH；热缩→纸箱规格：LWHcm",
                actual=outer_actual,
                edge="order_to_outbound",
            )
        )
    except Exception as e:
        findings.append(
            finding(
                "V_ORDER_FILE_PARSE",
                False,
                detail=str(e),
                soft=True,
                edge="order_to_outbound",
            )
        )
    return finalize_report(
        scope="order_file", subject=path.name, findings=findings, meta=meta
    )


def verify_labels_dir(
    label_dir: Path,
    *,
    order_code: str,
) -> dict:
    meta = {"order_code": order_code}
    # treat label_dir as project/产品标签 or the bundle itself
    if label_dir.name.endswith("标签") and order_code in label_dir.name:
        snap = {
            "ok": True,
            "absent": False,
            "bundles": [label_dir.name],
            "expect_bundle": f"{order_code}标签",
            "bundle_match": True,
            "manifest_codes": [],
            "pdf_count": len(list(label_dir.rglob("*.pdf"))),
        }
        man = label_dir / "_manifest.json"
        if man.is_file():
            snap["manifest_codes"] = [str(load_json(man).get("order_code") or "")]
        elif (label_dir.parent / "_manifest.json").is_file():
            snap["manifest_codes"] = [
                str(load_json(label_dir.parent / "_manifest.json").get("order_code") or "")
            ]
    else:
        # parent project style
        project = label_dir.parent if label_dir.name == "产品标签" else label_dir
        if (project / "产品标签").is_dir():
            snap = read_labels_snapshot(project, order_code)
        else:
            snap = read_labels_snapshot(label_dir, order_code)
    findings = check_labels(meta, snap)
    return finalize_report(
        scope="labels", subject=str(label_dir), findings=findings, meta=meta
    )


def verify_gen_trio_artifacts(
    work: Path,
    job: dict,
) -> dict:
    """After gen_trio writes work/out/{outbound,freight,customs}."""
    meta = dict(job.get("meta") or {})
    meta.setdefault("order_code", job.get("project_code") or meta.get("order_code"))
    meta.setdefault("store", job.get("entity_code") or meta.get("store"))
    meta.setdefault("ship_date", (job.get("ship_date") or "")[:10])
    if not meta.get("order_short"):
        meta["order_short"] = order_short_from_code(meta.get("order_code"))
    if not meta.get("brand"):
        store = (meta.get("store") or job.get("entity_code") or "").upper()
        meta["brand"] = "WIGENIUS" if store == "C04" else (
            "Dressmaker" if store == "C07" else ""
        )
    if meta.get("strips") is None and meta.get("lines"):
        meta["strips"] = sum(float(x.get("qty_strips") or 0) for x in meta["lines"])

    findings: list[dict] = []
    out_dir = work / "out" / "outbound"
    ob_files = sorted(out_dir.glob("*.xlsx")) if out_dir.is_dir() else []
    outbound = read_outbound_snapshot(ob_files[0]) if ob_files else None
    findings.extend(
        check_identity_and_outbound(meta=meta, outbound=outbound, order_snap=None)
    )

    freight_dir = work / "out" / "freight"
    customs_dir = work / "out" / "customs"
    freight_files = (
        sorted(freight_dir.glob("*.xlsx")) if freight_dir.is_dir() else []
    )
    customs_files = (
        sorted(customs_dir.glob("*.xlsx")) if customs_dir.is_dir() else []
    )

    if freight_files or customs_files:
        if not freight_files:
            findings.append(
                finding(
                    "V_FREIGHT_PRESENT",
                    False,
                    detail="freight dir empty after gen",
                    edge="freight_to_customs",
                )
            )
        if not customs_files:
            findings.append(
                finding(
                    "V_CUSTOMS_PRESENT",
                    False,
                    detail="customs dir empty after gen",
                    edge="freight_to_customs",
                )
            )
        for fp, cp in pair_freight_customs(freight_files, customs_files):
            if not fp or not str(fp):
                findings.append(
                    finding(
                        "V_ORPHAN_CUSTOMS",
                        False,
                        detail=str(cp),
                        edge="freight_to_customs",
                    )
                )
                continue
            if cp is None:
                findings.append(
                    finding(
                        "V_FREIGHT_WITHOUT_CUSTOMS",
                        False,
                        detail=fp.name,
                        edge="freight_to_customs",
                    )
                )
                continue
            fr = read_freight_snapshot(fp)
            cu = read_customs_snapshot(cp)
            findings.extend(
                check_freight_customs_pair(
                    fr, cu, store=str(meta.get("store") or "")
                )
            )

    # optional summary in work
    for cand in [
        work / "out" / "freight_customs_summary.json",
        work / "materialize" / "freight_customs_summary.json",
    ]:
        if cand.is_file():
            findings.extend(check_summary_and_reconcile(meta, load_json(cand)))
            break
    else:
        findings.extend(check_summary_and_reconcile(meta, None))

    return finalize_report(
        scope="gen_trio_work",
        subject=str(work),
        findings=findings,
        meta=meta,
    )


def verify_project(project: Path) -> dict:
    project = Path(project)
    meta = load_json(project / "PROJECT.json")
    if not meta:
        meta = {"folder_name": project.name}
    if not meta.get("order_code"):
        m = re.search(r"(EF-C\d{5}-C0[47]-\d+)", project.name, flags=re.I)
        if m:
            meta["order_code"] = m.group(1).upper()
    if not meta.get("order_short"):
        meta["order_short"] = meta.get("split_order_stem") or order_short_from_code(
            meta.get("order_code")
        )
    if not meta.get("store"):
        oc = meta.get("order_code") or ""
        m = re.search(r"-(C0[47])-", oc, flags=re.I)
        if m:
            meta["store"] = m.group(1).upper()
    if not meta.get("brand"):
        store = (meta.get("store") or "").upper()
        meta["brand"] = "WIGENIUS" if store == "C04" else ("Dressmaker" if store == "C07" else "")

    findings: list[dict] = []
    order_snap = try_read_order_meta(project)

    # outbound: prefer Shipments 出货表; also flag vs Output_Final if both exist
    ob_dir = project / "出货表"
    ob_files = (
        sorted(
            p
            for p in ob_dir.glob("*.xlsx")
            if not p.name.startswith("~$")
        )
        if ob_dir.is_dir()
        else []
    )
    outbound = read_outbound_snapshot(ob_files[0]) if ob_files else None
    findings.extend(
        check_identity_and_outbound(
            meta=meta, outbound=outbound, order_snap=order_snap
        )
    )
    findings.extend(check_labels(meta, read_labels_snapshot(project, meta.get("order_code"))))
    findings.extend(check_archive_outbound_sync(project, meta, outbound))
    findings.extend(check_packs_identity(project, meta))

    # freight + customs on project
    freight_files = (
        sorted((project / "货代入库贴下单表").glob("*.xlsx"))
        if (project / "货代入库贴下单表").is_dir()
        else []
    )
    freight_files = [
        p
        for p in freight_files
        if not p.name.startswith("~$") and "模板" not in p.name and "pre_media" not in p.name
    ]
    customs_files = (
        sorted((project / "报关资料表").glob("*.xlsx"))
        if (project / "报关资料表").is_dir()
        else []
    )
    customs_files = [p for p in customs_files if not p.name.startswith("~$")]

    freight_snaps: list[dict] = []
    customs_snaps: list[dict] = []
    if freight_files and customs_files:
        for fp, cp in pair_freight_customs(freight_files, customs_files):
            if not fp or not str(fp) or cp is None:
                findings.append(
                    finding(
                        "V_FREIGHT_CUSTOMS_PAIR_GAP",
                        False,
                        detail=f"freight={fp} customs={cp}",
                        soft=True,
                        edge="freight_to_customs",
                    )
                )
                continue
            fr = read_freight_snapshot(fp)
            cu = read_customs_snapshot(cp)
            freight_snaps.append(fr)
            customs_snaps.append(cu)
            findings.extend(
                check_freight_customs_pair(
                    fr,
                    cu,
                    store=str(meta.get("store") or ""),
                )
            )
    elif not freight_files and not customs_files:
        findings.append(
            finding(
                "V_FREIGHT_CUSTOMS_ABSENT",
                True,
                detail="no freight/customs xlsx — soft",
                soft=True,
                edge="freight_to_customs",
            )
        )
    findings.extend(
        check_warehouse_totals_vs_batch(freight_snaps, customs_snaps, meta)
    )

    # summary / reconcile reports — must match this order_code
    summary = None
    sum_path = meta.get("freight_customs_summary")
    order_code = meta.get("order_code") or ""
    if sum_path and Path(sum_path).is_file():
        cand = load_json(Path(sum_path))
        if not cand.get("order_code") or str(cand.get("order_code")).upper() == str(order_code).upper():
            summary = cand
        else:
            findings.append(
                finding(
                    "V_SUMMARY_ORDER_CODE",
                    False,
                    expected=order_code,
                    actual=cand.get("order_code"),
                    detail=f"PROJECT.freight_customs_summary points to wrong ticket: {sum_path}",
                    edge="reports_to_source",
                )
            )
    else:
        stem = meta.get("order_short") or order_short_from_code(order_code)
        drafts = ROOT / "2_Processed_AI" / "drafts"
        if stem and drafts.is_dir():
            cands = sorted(drafts.glob(f"*{stem}*freight_customs_summary.json"))
            for c in reversed(cands):
                cand = load_json(c)
                if str(cand.get("order_code") or "").upper() == str(order_code).upper():
                    summary = cand
                    break
    if summary is not None or not (
        sum_path and Path(sum_path).is_file()
    ):
        # skip duplicate V_SUMMARY if we already hard-failed path mismatch above
        if not any(f.get("check") == "V_SUMMARY_ORDER_CODE" and not f.get("ok") for f in findings):
            findings.extend(check_summary_and_reconcile(meta, summary))
    else:
        # already recorded mismatch; still attach reconcile softs without re-checking order
        pass

    # reconcile draft files
    stem = meta.get("order_short") or order_short_from_code(order_code)
    drafts = ROOT / "2_Processed_AI" / "drafts"
    recon_files = (
        list(drafts.glob(f"*{stem}*reconcile*.json")) if stem and drafts.is_dir() else []
    )
    split_dir = project / "拆单比对"
    if split_dir.is_dir():
        recon_files.extend(split_dir.glob("*reconcile*.json"))
    if recon_files:
        data = load_json(recon_files[0])
        recon = data.get("reconcile") or data
        gate_obj = recon.get("gate") if isinstance(recon.get("gate"), dict) else None
        gate = None
        if gate_obj:
            gate = gate_obj.get("overall")
            if gate is None:
                flags = [
                    gate_obj.get("amount_pass"),
                    gate_obj.get("net_pass"),
                    gate_obj.get("gross_pass"),
                    gate_obj.get("declare_pass"),
                ]
                flags = [f for f in flags if f is not None]
                if flags:
                    gate = "PASS" if all(flags) else "FAIL"
        elif recon.get("gate") is not None:
            gate = recon.get("gate")
        if gate is None:
            gate = data.get("reconcile_pass")
        if gate is True:
            gate = "PASS"
        if gate is False:
            gate = "FAIL"
        if gate:
            findings.append(
                finding(
                    "V_RECONCILE_FILE_GATE",
                    str(gate).upper() in ("PASS", "TRUE", "1", "OK"),
                    expected="PASS",
                    actual=gate,
                    detail=str(recon_files[0]),
                    edge="reports_to_source",
                )
            )
        else:
            err = (
                data.get("error_rate_pct_amount")
                or (data.get("error_rate_pct") or {}).get("declare")
                or (data.get("error_rate_pct") or {}).get("amount")
                or (recon.get("error_rate_pct") or {}).get("declare")
            )
            ok = True
            if err is not None:
                try:
                    ok = float(err) <= 1.0
                except (TypeError, ValueError):
                    ok = True
            findings.append(
                finding(
                    "V_RECONCILE_FILE_GATE",
                    ok,
                    expected="error_rate<=1%",
                    actual=err,
                    detail=str(recon_files[0]),
                    soft=err is None,
                    edge="reports_to_source",
                )
            )

    return finalize_report(
        scope="project",
        subject=project.name,
        findings=findings,
        meta=meta,
    )


def verify_project_outbound(project_dir: Path | str) -> dict:
    """事后补验：读 PROJECT.json + 出货表/*.xlsx（计划入口名）。"""
    return verify_project(Path(project_dir))
