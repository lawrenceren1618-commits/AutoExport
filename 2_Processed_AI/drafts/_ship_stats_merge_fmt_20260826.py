# -*- coding: utf-8 -*-
"""Append Jul/Aug to 发货记录 with merges/borders/center matching C26064 style."""
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import xlrd
import xlwt
from xlutils.copy import copy as xl_copy

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
INBOX = ROOT / "1_Input_Raw" / "00_Master_Reference" / "发货统计" / "_inbox"
MAIN = INBOX / "2026年发货记录.xls"
BAK = INBOX / "_bak_before_jul_aug_20260826.xls"
DRAFTS = ROOT / "2_Processed_AI" / "drafts"

# Styles matching historical XF (center + thin borders; wrap on date/FBA)
STY_WRAP = xlwt.easyxf(
    "align: wrap on, vert centre, horiz centre;"
    "borders: left thin, right thin, top thin, bottom thin"
)
STY_CELL = xlwt.easyxf(
    "align: wrap off, vert centre, horiz centre;"
    "borders: left thin, right thin, top thin, bottom thin"
)
# 月份分界：两行合并 + 浅蓝底（对齐历史空行分界习惯）
STY_SEP = xlwt.easyxf(
    "pattern: pattern solid, fore_colour pale_blue;"
    "borders: left thin, right thin, top thin, bottom thin;"
    "align: wrap off, vert centre, horiz centre"
)


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def size_short(size: str, color: str) -> str:
    """Simplified: 102白 / 84白 / 90圆米白 (no 60*, no ivory)."""
    s = size.replace("inch", "").replace("Inch", "").strip()
    s = s.replace("×", "*").replace("X", "*").replace("x", "*").replace(" ", "")
    if "round" in size.lower() or s.startswith("90"):
        body = "90圆"
    elif "60*102" in s or s.endswith("102"):
        body = "102"
    elif "60*84" in s or s.endswith("84"):
        body = "84"
    elif "60*126" in s or s.endswith("126"):
        body = "126"
    elif "70*120" in s or s.endswith("120"):
        body = "120"
    else:
        body = s
    c = color.strip()
    if c.lower() in ("ivory", "象牙", "象牙白", "象牙白色", "米白"):
        c = "米白"
    elif c in ("白色",):
        c = "白"
    elif c in ("黑色",):
        c = "黑"
    elif c in ("蓝色",):
        c = "蓝"
    return f"{body}{c}"


def parse_c07_sku(sku: str):
    import re

    m = re.match(
        r"^(?P<pre>Ivory|White|I|W|B)(?P<gsm>\d{2,3})(?P<body>90round|\d+)-(?P<spp>\d+)$",
        sku,
        re.I,
    )
    if not m:
        return None
    pre = m.group("pre").lower()
    if pre in ("i", "ivory"):
        color = "米白"
    elif pre in ("w", "white"):
        color = "白"
    elif pre == "b":
        color = "黑"
    else:
        color = "白"
    body = m.group("body")
    if "round" in body.lower():
        size = "90 inch round"
    elif body == "60102":
        size = "60X102inch"
    elif body == "60126":
        size = "60X126inch"
    elif body == "70120":
        size = "70X120inch"
    else:
        size = body
    return m.group("gsm"), size, color, m.group("spp")


def group_details(spec_map: dict) -> list[dict]:
    """[{spec, rows:[{size, cartons}, ...]} ...]"""
    out = []
    for spec, sizes in sorted(spec_map.items()):
        rows = [
            {"size": sk, "cartons": n}
            for sk, n in sorted(sizes.items(), key=lambda x: -x[1])
        ]
        out.append({"spec": spec, "rows": rows})
    return out


def specs_from_manifest_fnsku(manifest: dict) -> dict:
    spec_map: dict = defaultdict(lambda: defaultdict(int))
    for line in manifest.get("by_fnsku", []):
        spec = f"桌布-{line['strips_per_pack']}"
        key = size_short(line["size"], line["color"])
        spec_map[spec][key] += int(line["qty_cartons"])
    return spec_map


def specs_from_freight_files(files: list, leg: str | None = None, warehouses: set | None = None) -> tuple[dict, list[str], int]:
    """Aggregate specs + ordered unique FBA ids for a leg."""
    spec_map: dict = defaultdict(lambda: defaultdict(int))
    fba_ids: list[str] = []
    seen = set()
    cartons = 0
    for f in files:
        if leg and f.get("leg") != leg:
            continue
        if warehouses is not None and f.get("warehouse_code") not in warehouses:
            continue
        fid = f.get("fba_shipment_id") or ""
        if fid and fid not in seen:
            seen.add(fid)
            fba_ids.append(fid)
        cartons += int(f.get("cartons") or 0)
        for sp in f.get("specs", []):
            parsed = parse_c07_sku(sp.get("amazon_sku") or "")
            if not parsed:
                continue
            gsm, size, color, spp = parsed
            key = size_short(size, color)
            spec_map[f"{gsm}G 桌布-{spp}"][key] += int(
                sp.get("qty_cartons") or sp.get("cartons") or 0
            )
    return spec_map, fba_ids, cartons


def build_batches():
    """
    一票可同日并列多块；每块 FBA 只对应该腿发货明细。
    FC 多仓：该腿全部 FBA 号合并对应本腿全部规格行；AWD STAR 单独一块。
    """
    m79a = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26079-C04-36460  桌布-2026.7.10/拆单比对/C26079-A_manifest.json"
    )
    m79b = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26079-C04-36460  桌布-2026.7.10/拆单比对/C26079-B_manifest.json"
    )
    fba79a = [
        "FBA19JT39521",
        "FBA19JT71WTZ",
        "FBA19JT3Q0H0",
        "FBA19JT0K3PY",
        "FBA19JT16DMQ",
    ]
    fba79b = ["STAR-QG6CTURZGY6MX"]

    fs80 = load_json(ROOT / "2_Processed_AI/drafts/C26080_freight_summary.json")
    spec80a, fba80a, _c80a = specs_from_freight_files(fs80["files"], leg="C26080-A")
    # A may be tagged by warehouse only
    if not fba80a:
        spec80a, fba80a, _c80a = specs_from_freight_files(
            fs80["files"], warehouses={"SCK8"}
        )
    spec80b, fba80b, _c80b = specs_from_freight_files(fs80["files"], leg="C26080-B")
    if not fba80b:
        spec80b, fba80b, _c80b = specs_from_freight_files(
            fs80["files"], warehouses={"TOL3", "MCC1", "FWA4", "RDU2", "PSP3"}
        )
    # prefer manifest carton totals when available
    cartons80a = 30
    cartons80b = 320

    c89 = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26089-C07-40000_C07_20260821_40000/FBA外箱贴/_recognize/c26089_carton_confirm.json"
    )
    fba89a = [r["fba_shipment_id"] for r in c89["legs"]["C26089-A"]["rows"]]
    fba89b = [r["fba_shipment_id"] for r in c89["legs"]["C26089-B"]["rows"]]

    return [
        {
            "ticket": "C26079-A",
            "month": "2026.7",
            "give": f"7.31\nC26079-A {m79a['shipped_cartons']}箱",
            "forwarder": "物易通",
            "fba_ids": fba79a,
            "groups": group_details(specs_from_manifest_fnsku(m79a)),
            "total": m79a["shipped_cartons"],
            "note": "FC五仓；5个FBA对应本腿全部明细",
        },
        {
            "ticket": "C26079-B",
            "month": "2026.7",
            "give": f"7.31\nC26079-B {m79b['shipped_cartons']}箱 AWD",
            "forwarder": "物易通",
            "fba_ids": fba79b,
            "groups": group_details(specs_from_manifest_fnsku(m79b)),
            "total": m79b["shipped_cartons"],
            "note": "AWD IUTE；STAR 单独对应本腿明细",
        },
        {
            "ticket": "C26080-A",
            "month": "2026.7",
            "give": f"7.31 易尚\nC26080-A {cartons80a}箱",
            "forwarder": "物易通",
            "fba_ids": fba80a,
            "groups": group_details(spec80a),
            "total": cartons80a,
            "note": "SCK8 单仓；1个FBA对本腿明细",
        },
        {
            "ticket": "C26080-B",
            "month": "2026.7",
            "give": f"7.31 易尚\nC26080-B+C26068 {cartons80b}箱",
            "forwarder": "物易通",
            "fba_ids": fba80b,
            "groups": group_details(spec80b),
            "total": cartons80b,
            "note": "FC五仓；5个FBA对应本腿全部明细",
        },
        {
            "ticket": "C26089-A",
            "month": "2026.8",
            "give": f"8.29 易尚\nC26089-A {c89['legs']['C26089-A']['qty_cartons']}箱",
            "forwarder": "纽酷",
            "fba_ids": fba89a,
            "groups": [
                {
                    "spec": "90G 桌布-10",
                    "rows": [{"size": "102白", "cartons": 500}],
                }
            ],
            "total": 500,
            "note": "FC五仓纽酷SEND",
        },
        {
            "ticket": "C26089-B",
            "month": "2026.8",
            "give": f"8.29 易尚\nC26089-B {c89['legs']['C26089-B']['qty_cartons']}箱 AWD",
            "forwarder": "物易通",
            "fba_ids": fba89b,
            "groups": [
                {
                    "spec": "90G 桌布-10",
                    "rows": [{"size": "102白", "cartons": 500}],
                }
            ],
            "total": 500,
            "note": "AWD IUSP；STAR 单独",
        },
    ]


def flatten_rows(groups: list[dict]) -> list[dict]:
    rows = []
    for g in groups:
        for i, row in enumerate(g["rows"]):
            rows.append(
                {
                    "spec": g["spec"] if i == 0 else "",
                    "spec_span": len(g["rows"]) if i == 0 else 0,
                    "size": row["size"],
                    "cartons": row["cartons"],
                }
            )
    return rows


def last_nonempty(sh) -> int:
    last = 0
    for r in range(sh.nrows):
        if any(str(sh.cell_value(r, c)).strip() for c in range(min(11, sh.ncols))):
            last = r
    return last


def write_batch(ws, start: int, batch: dict) -> int:
    """Write one batch with merges. Returns next free row index."""
    flat = flatten_rows(batch["groups"])
    n = len(flat)
    assert n >= 1
    end = start + n - 1  # inclusive

    # 给货日期 C: merge full batch
    ws.write_merge(start, end, 2, 2, batch["give"], STY_WRAP)
    # FBA I: all ids
    ws.write_merge(start, end, 8, 8, "\n".join(batch["fba_ids"]), STY_WRAP)
    # 运费/货代 J
    ws.write_merge(start, end, 9, 9, batch["forwarder"], STY_CELL)

    # 规格 D: merge per group
    r = start
    for g in batch["groups"]:
        span = len(g["rows"])
        if span == 1:
            ws.write(r, 3, g["spec"], STY_CELL)
        else:
            ws.write_merge(r, r + span - 1, 3, 3, g["spec"], STY_CELL)
        for row in g["rows"]:
            ws.write(r, 4, row["size"], STY_CELL)  # 尺寸
            ws.write(r, 6, row["cartons"], STY_CELL)  # 箱数
            # empty bordered cells for visual grid where useful
            for c in (1, 5, 7):
                try:
                    ws.write(r, c, "", STY_CELL)
                except Exception:
                    pass
            r += 1
    assert r == end + 1
    return end + 1


def write_month_separator(ws, start: int, label: str = "") -> int:
    """两行合并分界（A–J），浅蓝底；可选写入月份标签。返回下一行。"""
    end = start + 1
    ws.write_merge(start, end, 0, 9, label, STY_SEP)
    return end + 1


def main() -> None:
    if not BAK.exists():
        raise SystemExit(f"missing {BAK}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if MAIN.exists():
        try:
            shutil.copy2(MAIN, INBOX / f"_bak_before_merge_fix_{stamp}.xls")
        except PermissionError:
            print("warn: could not backup MAIN")

    rb = xlrd.open_workbook(str(BAK), formatting_info=True)
    sh = rb.sheet_by_index(0)
    last = last_nonempty(sh)
    wb = xl_copy(rb)
    ws = wb.get_sheet(0)

    # Drop empty trailing merges that collide with new rows (e.g. 314:315 spacer)
    keep = []
    for m in list(ws.merged_ranges):
        r1, r2, c1, c2 = m
        if r1 > last:
            continue
        if r2 > last:
            continue
        keep.append(m)
    ws.merged_ranges[:] = keep
    print("merged kept", len(keep), "last_row", last + 1)

    batches = build_batches()
    for b in batches:
        s = sum(row["cartons"] for g in b["groups"] for row in g["rows"])
        if s != b["total"]:
            print("WARN sum", b["ticket"], s, "!=", b["total"])

    r = last + 1
    by_month: dict[str, list] = defaultdict(list)
    for b in batches:
        by_month[b["month"]].append(b)

    for month in sorted(by_month.keys()):
        # 不同月份之间：两行合并彩色分界
        r = write_month_separator(ws, r, "")
        month_batches = by_month[month]
        month_start = r
        for b in month_batches:
            r = write_batch(ws, r, b)
        month_end = r - 1
        if month_end >= month_start:
            ws.write_merge(month_start, month_end, 0, 0, month, STY_CELL)

    try:
        wb.save(str(MAIN))
        saved = MAIN
    except PermissionError:
        # 勿再用 _merged_ 正式名；仅临时
        alt = INBOX / f"_tmp_write_{stamp}.xls"
        wb.save(str(alt))
        saved = alt
        print("MAIN locked →", alt.name, "（关闭 Excel 后可覆盖主表）")

    # 清理误留的 _merged_ 临时件
    for p in INBOX.glob("*_merged_*.xls"):
        try:
            p.unlink()
            print("deleted temp", p.name)
        except OSError as e:
            print("could not delete", p.name, e)

    report = {
        "saved": str(saved),
        "base": str(BAK),
        "separator": "2-row merge A-J pale_blue between months",
        "start_row_1based": last + 2,
        "end_row_1based": r,
        "batches": [
            {
                "ticket": b["ticket"],
                "give": b["give"],
                "fba_count": len(b["fba_ids"]),
                "fba_ids": b["fba_ids"],
                "detail_rows": sum(len(g["rows"]) for g in b["groups"]),
                "carton_sum": sum(
                    row["cartons"] for g in b["groups"] for row in g["rows"]
                ),
                "total": b["total"],
            }
            for b in batches
        ],
    }
    (DRAFTS / "_ship_stats_merge_fix_20260826.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("ok saved", saved.name, "rows", last + 1, "->", r)
    for b in report["batches"]:
        print(b["ticket"], "fba", b["fba_count"], "cartons", b["carton_sum"])


if __name__ == "__main__":
    main()
