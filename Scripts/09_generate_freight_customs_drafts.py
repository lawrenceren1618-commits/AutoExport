# -*- coding: utf-8 -*-
"""Generate C26079-A freight + customs drafts (one xlsx per warehouse).

Writes under project 货代入库贴下单表/ and 报关资料表/, and mirrors JSON summary
to 2_Processed_AI/drafts/. Does NOT write 3_Output_Final (Gate still required).

Usage:
  python Scripts/09_generate_freight_customs_drafts.py --project "<Shipments/...>"
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import sys
import zipfile
from copy import copy
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]

FREIGHT_TEMPLATE = ROOT / (
    "1_Input_Raw/Shipments/EF-C26040-C04-8490_C04_20260510_8490/"
    "货代入库贴下单表/货代入库贴数据2026.5.10 HEA2 248箱.xlsx"
)
# 样例固定：客户单号不得改为追踪码/FBA；箱重尺默认 16；图片用样例 DISPIMG+media
FREIGHT_CUSTOMER_NO = "111111111"
FREIGHT_CARTON_DIM_DEFAULT = 16
FREIGHT_DISPIMG = '=DISPIMG("ID_3D20B9B273A54ACBA2D957C7EE1766FF",1)'
FREIGHT_SALES_LINK = {
    "C04": "https://www.amazon.com/dp/B0CCRKDW1K?th=1",
    "C07": "https://www.amazon.com/gp/product/B0FNVMX537",
}
FREIGHT_MEDIA_PARTS = (
    "xl/cellimages.xml",
    "xl/_rels/cellimages.xml.rels",
)
CUSTOMS_TEMPLATE = ROOT / (
    "1_Input_Raw/Shipments/EF-C26040-C04-8490_C04_20260510_8490/"
    "_来源归档/畅选+波丽丝 2026.5.10发货 248箱 市场采购数据.xlsx"
)
MASTER = ROOT / "1_Input_Raw/00_Master_Reference/2026.7.20桌布当前产品总表.xlsx"

WH_ADDRESS = {
    "AVP1": {
        "company": "Amazon.com Services, Inc.",
        "line1": "550 Oak Ridge Road",
        "city": "Hazle Township",
        "state": "PA",
        "zip": "18202-9361",
        "freight_addr": "AVP1 - 550 Oak Ridge Road - Hazle Township, PA 18202-9361 - United States",
    },
    "CLT2": {
        "company": "Amazon.com Services, Inc.",
        "line1": "10240 Old Dowd Rd",
        "city": "Charlotte",
        "state": "NC",
        "zip": "28214-8082",
        "freight_addr": "CLT2 - 10240 Old Dowd Rd - Charlotte, NC 28214-8082 - United States",
    },
    "GYR2": {
        "company": "Amazon.com Services, Inc.",
        "line1": "17341 W MINNEZONA AVE",
        "city": "GOODYEAR",
        "state": "AZ",
        "zip": "85395-7672",
        "freight_addr": "GYR2 - 17341 W MINNEZONA AVE - GOODYEAR, AZ 85395-7672 - United States",
    },
    "LGB8": {
        "company": "Amazon.com Services, Inc.",
        "line1": "1568 N Linden Ave",
        "city": "Rialto",
        "state": "CA",
        "zip": "92376-8624",
        "freight_addr": "LGB8 - 1568 N Linden Ave - Rialto, CA 92376-8624 - United States",
    },
    "MDW2": {
        "company": "Amazon.com Services, Inc.",
        "line1": "250 EMERALD DR",
        "city": "Joliet",
        "state": "IL",
        "zip": "60433-3280",
        "freight_addr": "MDW2 - 250 EMERALD DR - Joliet, IL 60433-3280 - United States",
    },
}

PROTOCOL_SUFFIX = {
    "AVP1": "801",
    "CLT2": "802",
    "GYR2": "803",
    "LGB8": "804",
    "MDW2": "805",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def _parse_lwh(text: str) -> tuple[float, float, float]:
    if not text:
        return (57.0, 40.0, 33.0)
    m = re.search(r"(\d+(?:\.\d+)?)\s*[*×xX]\s*(\d+(?:\.\d+)?)\s*[*×xX]\s*(\d+(?:\.\d+)?)", str(text))
    if m:
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    return (57.0, 40.0, 33.0)


def load_master_by_fnsku() -> dict[str, dict]:
    wb = openpyxl.load_workbook(MASTER, data_only=True)
    ws = wb["Sheet1"]
    spp = None
    size = None
    out: dict[str, dict] = {}
    for r in range(2, (ws.max_row or 1) + 1):
        brand = ws.cell(r, 1).value
        # stop at C07 block roughly: when brand mentions C07
        if brand and "C07" in str(brand):
            break
        if ws.cell(r, 2).value not in (None, ""):
            spp = int(ws.cell(r, 2).value)
        if ws.cell(r, 3).value not in (None, ""):
            size = ws.cell(r, 3).value
        fn = ws.cell(r, 5).value
        if not fn:
            continue
        net = ws.cell(r, 9).value
        gross = ws.cell(r, 10).value
        price_ctn = ws.cell(r, 11).value
        lwh = _parse_lwh(ws.cell(r, 7).value)
        ppc = ws.cell(r, 8).value
        out[str(fn).strip()] = {
            "strips_per_pack": spp,
            "size": size,
            "packs_per_carton": int(ppc) if ppc else None,
            "net_kg": float(net) if net is not None else None,
            "gross_kg": float(gross) if gross is not None else None,
            "price_per_carton": float(price_ctn) if price_ctn is not None else None,
            "lwh": lwh,
        }
    return out


def warehouse_money_weights(wh_specs: list[dict], master: dict[str, dict]) -> dict:
    """Aggregate net/gross/declare amount for one warehouse from its specs."""
    total_net = 0.0
    total_gross = 0.0
    total_amount = 0.0
    missing = []
    lwh_votes: dict[tuple, int] = {}
    for s in wh_specs:
        fn = s.get("fnsku")
        ctn = int(s.get("qty_cartons") or 0)
        if not fn or fn not in master:
            missing.append(s)
            continue
        m = master[fn]
        total_net += ctn * float(m["net_kg"] or 0)
        total_gross += ctn * float(m["gross_kg"] or 0)
        total_amount += ctn * float(m["price_per_carton"] or 0)
        lwh_votes[m["lwh"]] = lwh_votes.get(m["lwh"], 0) + ctn
    lwh = max(lwh_votes.items(), key=lambda kv: kv[1])[0] if lwh_votes else (57.0, 40.0, 33.0)
    return {
        "net_kg": round(total_net, 2),
        "gross_kg": round(total_gross, 2),
        "declare_amount_raw": round(total_amount, 2),
        "lwh": lwh,
        "missing_specs": missing,
    }


def price_check(amount: float, strips: int) -> tuple[float, float]:
    unit = round(amount / strips, 2) if strips else 0.0
    amount2 = round(unit * strips, 2)
    return unit, amount2


def _reinject_freight_media(target: Path, template: Path) -> None:
    """openpyxl save strips WPS DISPIMG media; copy media/cellimages back from template."""
    with zipfile.ZipFile(target, "r") as zt:
        media = [n for n in zt.namelist() if n.startswith("xl/media/") and not n.endswith("/")]
        if media:
            return
        entries = {name: zt.read(name) for name in zt.namelist()}

    with zipfile.ZipFile(template, "r") as zs:
        template_rels = zs.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        for name in zs.namelist():
            if name.startswith("xl/media/") and not name.endswith("/"):
                entries[name] = zs.read(name)
            elif name in FREIGHT_MEDIA_PARTS:
                entries[name] = zs.read(name)

    ct = entries["[Content_Types].xml"].decode("utf-8")
    if 'Extension="png"' not in ct:
        ct = ct.replace(
            '<Default Extension="rels"',
            '<Default Extension="png" ContentType="image/png"/><Default Extension="rels"',
        )
    if "cellimages.xml" not in ct:
        ct = ct.replace(
            "</Types>",
            '<Override PartName="/xl/cellimages.xml" '
            'ContentType="application/vnd.wps-officedocument.cellimage+xml"/></Types>',
        )
    entries["[Content_Types].xml"] = ct.encode("utf-8")

    rels = entries["xl/_rels/workbook.xml.rels"].decode("utf-8")
    if "cellimages.xml" not in rels:
        m = re.search(
            r'<Relationship[^>]+Target="cellimages\.xml"[^>]*/>',
            template_rels,
        )
        if m:
            rel_line = m.group(0)
            ids = {int(x) for x in re.findall(r'Id="rId(\d+)"', rels)}
            tid = re.search(r'Id="(rId\d+)"', rel_line)
            if tid and tid.group(1) in rels:
                next_id = max(ids) + 1 if ids else 1
                rel_line = re.sub(r'Id="rId\d+"', f'Id="rId{next_id}"', rel_line)
            rels = rels.replace("</Relationships>", rel_line + "</Relationships>")
            entries["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")

    tmp = target.with_suffix(".mediafix.xlsx")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zw:
        for name, data in entries.items():
            zw.writestr(name, data)
    tmp.replace(target)


def fill_freight(path: Path, row: dict, money: dict, unit_price: float) -> None:
    """Fill freight 下单模板: only allowed change fields; keep static from template/defaults.

    Change: E3 仓库代码, E7 收件人姓名(空), E8 地址=仓码+地址,
            A15 FBA, B15 追踪码, C15 箱, D15/E15 品名, F15 floor(条/箱), G15 单价,
            S15 样例图片(+media reinject).
    Static: C2 客户单号=111111111; I/J/K/L=16; HS/材质/用途/品牌三列; 勿填 E10–E12.
    """
    del money  # freight 箱重尺不再用总表毛重/箱规
    wb = openpyxl.load_workbook(path)
    ws = wb["下单模板"]
    wh = row["warehouse_code"]
    addr = WH_ADDRESS[wh]
    cartons = int(row["cartons"])
    strips = int(row["strips"])
    per_carton = math.floor(strips / cartons) if cartons else 0

    # 客户单号固定；禁止写入追踪码
    ws["C2"] = FREIGHT_CUSTOMER_NO
    ws["E3"] = wh
    ws["E7"] = None  # 收件人姓名不填
    ws["E8"] = addr["freight_addr"]
    for clear_ref in ("E10", "E11", "E12"):
        ws[clear_ref] = None

    ws["A15"] = row["fba_shipment_id"]
    ws["B15"] = row.get("tracking_id") or ""
    ws["C15"] = cartons
    ws["D15"] = "桌布"
    ws["E15"] = "table cloth"
    ws["F15"] = per_carton
    ws["G15"] = unit_price
    ws["H15"] = "USD"
    dim = FREIGHT_CARTON_DIM_DEFAULT
    ws["I15"] = dim
    ws["J15"] = dim
    ws["K15"] = dim
    ws["L15"] = dim
    ws["M15"] = "6302539090"
    ws["N15"] = "聚酯纤维/polyester"
    ws["O15"] = "餐桌"
    ws["P15"] = "无"
    ws["Q15"] = "无"
    ws["R15"] = "无"
    s15 = ws["S15"].value
    if not (isinstance(s15, str) and "DISPIMG" in s15.upper()):
        ws["S15"] = FREIGHT_DISPIMG
    store = str(row.get("store") or row.get("entity_code") or "C04").upper()
    if store not in FREIGHT_SALES_LINK:
        store = "C04" if store.startswith("C04") else store
    ws["T15"] = FREIGHT_SALES_LINK.get(store, FREIGHT_SALES_LINK["C04"])
    wb.save(path)
    wb.close()
    _reinject_freight_media(path, FREIGHT_TEMPLATE)
    # 强制校验：公式在、media 不在 = 图丢失（FC/AWD 均不可接受）
    import zipfile as _zf

    with _zf.ZipFile(path, "r") as zf:
        media_n = sum(
            1 for n in zf.namelist() if n.startswith("xl/media/") and not n.endswith("/")
        )
    if media_n < 1:
        raise RuntimeError(
            f"freight image missing after reinject: {path} (xl/media={media_n})"
        )


def fill_customs(path: Path, row: dict, money: dict, unit_price: float, amount: float, protocol: str) -> None:
    wb = openpyxl.load_workbook(path)
    ws = wb["基础表"]
    cartons = int(row["cartons"])
    strips = int(row["strips"])
    # change fields only
    ws.cell(7, 12).value = money["gross_kg"]  # 总毛重
    ws.cell(8, 6).value = protocol  # 合同协议号
    ws.cell(8, 12).value = money["net_kg"]  # 总净重
    ws.cell(9, 4).value = "许昌波丽丝贸易有限公司"  # 表内抬头
    ws.cell(9, 6).value = "波丽丝"
    ws.cell(9, 12).value = cartons  # 总件数
    # commodity row 14
    ws.cell(14, 3).value = "6302539090"
    ws.cell(14, 4).value = "聚酯纤维桌布"
    ws.cell(14, 6).value = cartons  # 件数
    ws.cell(14, 7).value = strips  # 成交数量
    ws.cell(14, 8).value = "条"
    ws.cell(14, 9).value = unit_price
    ws.cell(14, 10).value = amount
    ws.cell(14, 11).value = money["net_kg"]
    ws.cell(14, 14).value = "许昌波丽丝贸易有限公司"
    ws.cell(14, 15).value = "无品牌"
    ws.cell(14, 16).value = "无货号"
    # buyer
    ws.cell(2, 8).value = "Amazon.com Services, Inc."
    wb.save(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    project = Path(args.project)
    rec_path = ROOT / "2_Processed_AI" / "drafts" / "C26079-A_fba_recognize.json"
    headers_path = ROOT / "2_Processed_AI" / "drafts" / "C26079-A_warehouse_headers.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    headers = json.loads(headers_path.read_text(encoding="utf-8"))
    master = load_master_by_fnsku()

    freight_dir = project / "货代入库贴下单表"
    customs_dir = project / "报关资料表"
    freight_dir.mkdir(parents=True, exist_ok=True)
    customs_dir.mkdir(parents=True, exist_ok=True)

    # map warehouse -> specs from recognize
    specs_by_wh = {w["warehouse_code"]: w.get("specs") or [] for w in rec["warehouses"]}

    summary = {
        "generated_at": _now(),
        "order_code": "EF-C26079-C04-36460",
        "split_leg_id": "C26079-A",
        "pricing_method": "per_warehouse: raw=sum(cartons*master_1039_ctn_price); unit=round(raw/strips,2); amount=round(unit*strips,2)",
        "note": "草稿；未进 Final；B腿剩余3规格未纳入；货值按仓正算反算",
        "remaining_for_B": rec.get("plan_compare", {}).get("missing_specs_in_fba"),
        "files": [],
        "warnings": [],
    }

    if not FREIGHT_TEMPLATE.is_file() or not CUSTOMS_TEMPLATE.is_file():
        print("missing templates", file=sys.stderr)
        return 1

    grand_amount = 0.0
    grand_raw = 0.0
    # 店铺：从订单号解析 C04/C07，供货代销售链接
    order_code = str(headers.get("order_code") or summary["order_code"])
    store = "C07" if "-C07-" in order_code or order_code.startswith("C07") else "C04"
    for row in headers["rows"]:
        row = {**row, "store": store}
        wh = row["warehouse_code"]
        money = warehouse_money_weights(specs_by_wh.get(wh, []), master)
        if money["missing_specs"]:
            summary["warnings"].append(f"{wh}: {len(money['missing_specs'])} specs missing master join")
        raw = float(money["declare_amount_raw"])
        unit, amount = price_check(raw, int(row["strips"]))
        if amount <= 0:
            summary["warnings"].append(f"{wh}: declare amount 0 — check master join")
        grand_amount += amount
        grand_raw += raw

        freight_name = f"货代下单表_C26079-A 2026.7.31桌布 {wh} {row['cartons']}箱.xlsx"
        customs_name = (
            f"畅选+波丽丝 2026.7.31发货 C26079-A {wh} {row['cartons']}箱 市场采购数据.xlsx"
        )
        freight_path = freight_dir / freight_name
        customs_path = customs_dir / customs_name
        shutil.copy2(FREIGHT_TEMPLATE, freight_path)
        shutil.copy2(CUSTOMS_TEMPLATE, customs_path)

        fill_freight(freight_path, row, money, unit)
        protocol = f"20260731{PROTOCOL_SUFFIX[wh]}"
        fill_customs(customs_path, row, money, unit, amount, protocol)

        summary["files"].append(
            {
                "warehouse_code": wh,
                "fba_shipment_id": row["fba_shipment_id"],
                "tracking_id": row.get("tracking_id"),
                "cartons": row["cartons"],
                "strips": row["strips"],
                "raw_carton_x_price": round(raw, 2),
                "unit_price_usd": unit,
                "declare_amount_usd": amount,
                "net_kg": money["net_kg"],
                "gross_kg": money["gross_kg"],
                "protocol_no": protocol,
                "freight_file": str(freight_path),
                "customs_file": str(customs_path),
            }
        )
        print(
            f"{wh}: cartons={row['cartons']} strips={row['strips']} "
            f"raw={round(raw,2)} unit={unit} amount={amount}"
        )

    summary["total_raw_carton_x_price"] = round(grand_raw, 2)
    summary["total_declare_amount_usd"] = round(grand_amount, 2)
    # 规格汇总 A vs 分仓 B：误差率闸门（≤1% 不报告）
    spec_amt = round(grand_raw, 2)  # raw 合计 = 规格汇总货值（同算法）
    # 更精确：从全部 specs 重算 A（与 grand_raw 应一致）
    a_amt = a_net = a_gross = 0.0
    for specs in specs_by_wh.values():
        mny = warehouse_money_weights(specs, master)
        a_amt += float(mny["declare_amount_raw"])
        a_net += float(mny["net_kg"])
        a_gross += float(mny["gross_kg"])
    b_net = sum(float(f["net_kg"]) for f in summary["files"])
    b_gross = sum(float(f["gross_kg"]) for f in summary["files"])

    def _err_pct(b: float, a: float) -> float | None:
        if a == 0:
            return 0.0 if b == 0 else None
        return abs(b - a) / a * 100.0

    er_amt = _err_pct(grand_amount, a_amt)
    er_net = _err_pct(b_net, a_net)
    er_gross = _err_pct(b_gross, a_gross)
    summary["reconcile"] = {
        "doc": "Templates/Amount_Weight_Reconcile.md",
        "A_spec": {"amount": round(a_amt, 2), "net_kg": round(a_net, 2), "gross_kg": round(a_gross, 2)},
        "B_warehouse": {
            "amount": round(grand_amount, 2),
            "net_kg": round(b_net, 2),
            "gross_kg": round(b_gross, 2),
        },
        "error_rate_pct": {
            "declare": None if er_amt is None else round(er_amt, 4),
            "net": None if er_net is None else round(er_net, 4),
            "gross": None if er_gross is None else round(er_gross, 4),
        },
        "pass_max_pct": 1.0,
        "gate": {
            "declare": "PASS" if er_amt is not None and er_amt <= 1.0 else "CONFIRM",
            "net": "PASS" if er_net is not None and er_net <= 1.0 else "CONFIRM",
            "gross": "PASS" if er_gross is not None and er_gross <= 1.0 else "CONFIRM",
        },
    }
    summary["reconcile"]["gate"]["overall"] = (
        "PASS"
        if all(summary["reconcile"]["gate"][k] == "PASS" for k in ("declare", "net", "gross"))
        else "CONFIRM"
    )
    print(
        f"五仓合计 raw箱×单价={summary['total_raw_carton_x_price']} "
        f"正算反算货值={summary['total_declare_amount_usd']}"
    )
    print(
        f"对照误差率 declare={summary['reconcile']['error_rate_pct']['declare']}% "
        f"net={summary['reconcile']['error_rate_pct']['net']}% "
        f"gross={summary['reconcile']['error_rate_pct']['gross']}% "
        f"gate={summary['reconcile']['gate']['overall']}"
    )
    if summary["reconcile"]["gate"]["overall"] != "PASS":
        summary["warnings"].append(
            "误差率>1%：须人工确认后再继续（见 Templates/Amount_Weight_Reconcile.md）"
        )
        print("WARN: 误差率超过 1%，须人工确认")

    out = ROOT / "2_Processed_AI" / "drafts" / "C26079-A_freight_customs_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    for w in summary["warnings"]:
        print("WARN:", w)

    note_path = project / "拆单比对" / "C26079-B_PENDING.md"
    note_path.write_text(
        "\n".join(
            [
                "# C26079-B 待发（已确认）",
                "",
                "A 腿外箱贴未含、确认进 B：",
                "",
                "| 尺寸 | 颜色 | 条数/包 | 计划箱 | 计划条 |",
                "|------|------|---------|--------|--------|",
                "| 60X126inch | 白 | 10 | 50 | 1500 |",
                "| 70X120inch | 白 | 6 | 50 | 1500 |",
                "| 70X120inch | 米白 | 6 | 40 | 1200 |",
                "",
                "合计约 **140 箱 / 4200 条**。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"wrote {note_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
