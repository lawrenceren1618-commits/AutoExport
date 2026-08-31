# -*- coding: utf-8 -*-
"""Restore original Excel format from bak; append Jul/Aug in user's June style."""
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import xlrd
from xlutils.copy import copy as xl_copy

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
INBOX = ROOT / "1_Input_Raw" / "00_Master_Reference" / "发货统计" / "_inbox"
MAIN = INBOX / "2026年发货记录.xls"
BAK = INBOX / "_bak_before_jul_aug_20260826.xls"
DRAFTS = ROOT / "2_Processed_AI" / "drafts"


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def size_disp(size: str, color: str) -> str:
    """Match recent user rows: '60*102 白' / '90圆 米白' (space, 米白 not ivory)."""
    s = size.replace("inch", "").replace("Inch", "").strip()
    s = s.replace("×", "*").replace("X", "*").replace("x", "*")
    compact = s.replace(" ", "")
    if "round" in size.lower() or compact.startswith("90"):
        body = "90圆"
    elif "60*102" in compact or compact.endswith("102"):
        body = "60*102"
    elif "60*84" in compact or compact.endswith("84"):
        body = "60*84"
    elif "60*126" in compact or compact.endswith("126"):
        body = "60*126"
    elif "70*120" in compact or compact.endswith("120"):
        body = "70*120"
    else:
        body = compact
    c = color.strip()
    if c in ("象牙", "象牙白", "象牙白色", "Ivory", "ivory"):
        c = "米白"
    return f"{body} {c}"


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


def build_batches():
    m79a = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26079-C04-36460  桌布-2026.7.10/拆单比对/C26079-A_manifest.json"
    )
    m79b = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26079-C04-36460  桌布-2026.7.10/拆单比对/C26079-B_manifest.json"
    )
    fba79 = [
        "FBA19JT39521",
        "FBA19JT71WTZ",
        "FBA19JT3Q0H0",
        "FBA19JT0K3PY",
        "FBA19JT16DMQ",
        "STAR-QG6CTURZGY6MX",
    ]
    spec79: dict = defaultdict(lambda: defaultdict(int))
    for m in (m79a, m79b):
        for line in m["by_fnsku"]:
            spec = f"桌布-{line['strips_per_pack']}"
            key = size_disp(line["size"], line["color"])
            spec79[spec][key] += int(line["qty_cartons"])
    detail79 = []
    for spec, sizes in sorted(spec79.items()):
        for i, (sk, n) in enumerate(sorted(sizes.items(), key=lambda x: -x[1])):
            detail79.append({"spec": spec if i == 0 else "", "size": sk, "cartons": n})

    fs80 = load_json(ROOT / "2_Processed_AI/drafts/C26080_freight_summary.json")
    fba80 = [f["fba_shipment_id"] for f in fs80["files"]]
    spec80: dict = defaultdict(lambda: defaultdict(int))
    for f in fs80["files"]:
        for sp in f.get("specs", []):
            parsed = parse_c07_sku(sp.get("amazon_sku") or "")
            if not parsed:
                continue
            gsm, size, color, spp = parsed
            key = size_disp(size, color)
            spec80[f"{gsm}G 桌布-{spp}"][key] += int(
                sp.get("qty_cartons") or sp.get("cartons") or 0
            )
    detail80 = []
    for spec, sizes in sorted(spec80.items()):
        for i, (sk, n) in enumerate(sorted(sizes.items(), key=lambda x: -x[1])):
            detail80.append({"spec": spec if i == 0 else "", "size": sk, "cartons": n})

    c89 = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26089-C07-40000_C07_20260821_40000/FBA外箱贴/_recognize/c26089_carton_confirm.json"
    )
    return [
        {
            "month": "2026.7",
            "give": f"7.31\nC26079 {m79a['shipped_cartons'] + m79b['shipped_cartons']}箱\n（A{m79a['shipped_cartons']}+B{m79b['shipped_cartons']}）",
            "forwarder": "物易通",  # write into 运费列 (J), 渠道留空 — 与历史一致
            "fba": fba79,
            "details": detail79,
            "total": m79a["shipped_cartons"] + m79b["shipped_cartons"],
            "ticket": "C26079",
        },
        {
            "month": "2026.7",
            "give": f"7.31 易尚\nC26080+C26068 {fs80['cross_check']['order_cartons']}箱",
            "forwarder": "物易通",
            "fba": fba80,
            "details": detail80,
            "total": fs80["cross_check"]["order_cartons"],
            "ticket": "C26080",
        },
        {
            "month": "2026.8",
            "give": f"8.29 易尚\nC26089-A {c89['legs']['C26089-A']['qty_cartons']}箱 纽酷SEND",
            "forwarder": "纽酷",
            "fba": [r["fba_shipment_id"] for r in c89["legs"]["C26089-A"]["rows"]],
            "details": [{"spec": "90G 桌布-10", "size": "60*102 白", "cartons": 500}],
            "total": 500,
            "ticket": "C26089-A",
        },
        {
            "month": "2026.8",
            "give": f"8.29 易尚\nC26089-B {c89['legs']['C26089-B']['qty_cartons']}箱 物易通AWD",
            "forwarder": "物易通",
            "fba": [r["fba_shipment_id"] for r in c89["legs"]["C26089-B"]["rows"]],
            "details": [{"spec": "90G 桌布-10", "size": "60*102 白", "cartons": 500}],
            "total": 500,
            "ticket": "C26089-B",
        },
    ]


def last_nonempty(sh) -> int:
    last = 0
    for r in range(sh.nrows):
        if any(str(sh.cell_value(r, c)).strip() for c in range(min(11, sh.ncols))):
            last = r
    return last


def main() -> None:
    if not BAK.exists():
        raise SystemExit(f"missing bak: {BAK}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if MAIN.exists():
        try:
            shutil.copy2(MAIN, INBOX / f"_bak_before_restore_user_fmt_{stamp}.xls")
        except PermissionError:
            print("warn: MAIN bak skip (locked)")

    # Start from original-format bak (desktop content, pre our xlwt wipe)
    rb = xlrd.open_workbook(str(BAK), formatting_info=True)
    sh = rb.sheet_by_index(0)
    last = last_nonempty(sh)
    wb = xl_copy(rb)
    ws = wb.get_sheet(0)

    batches = build_batches()
    r = last + 1
    current_month = None
    for b in batches:
        if b["month"] != current_month:
            ws.write(r, 0, b["month"])
            r += 1
            current_month = b["month"]
        d0 = b["details"][0]
        ws.write(r, 2, b["give"])
        if d0.get("spec"):
            ws.write(r, 3, d0["spec"])
        ws.write(r, 4, d0["size"])
        ws.write(r, 6, d0["cartons"])
        # 渠道 H 留空；货代写入运费 J —— 与你 6 月行一致
        ws.write(r, 8, "\n".join(b["fba"]))
        ws.write(r, 9, b["forwarder"])
        r += 1
        for d in b["details"][1:]:
            if d.get("spec"):
                ws.write(r, 3, d["spec"])
            ws.write(r, 4, d["size"])
            ws.write(r, 6, d["cartons"])
            r += 1

    try:
        wb.save(str(MAIN))
        saved = MAIN
    except PermissionError:
        alt = INBOX / f"2026年发货记录_restored_{stamp}.xls"
        wb.save(str(alt))
        saved = alt
        print("MAIN locked →", alt.name)

    sums = {
        b["ticket"]: (sum(d["cartons"] for d in b["details"]), b["total"]) for b in batches
    }
    note = {
        "saved": str(saved),
        "base": str(BAK),
        "style": "user_june: channel empty, forwarder in freight col, size like 60*102 白",
        "historical": "unchanged (no size rewrite)",
        "sums": sums,
        "end_row": r,
    }
    (DRAFTS / "_ship_stats_restore_user_fmt_20260826.json").write_text(
        json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("ok", note)


if __name__ == "__main__":
    main()
