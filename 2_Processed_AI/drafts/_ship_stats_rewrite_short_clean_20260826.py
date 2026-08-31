# -*- coding: utf-8 -*-
"""Clean rewrite: short sizes (102白), lory→米白, append Jul/Aug after last real row."""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import xlrd
import xlwt

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
INBOX = ROOT / "1_Input_Raw" / "00_Master_Reference" / "发货统计" / "_inbox"
MAIN = INBOX / "2026年发货记录.xls"
BAK_CLEAN = INBOX / "_bak_before_jul_aug_20260826.xls"
DRAFTS = ROOT / "2_Processed_AI" / "drafts"
COLS = 11


def norm_color(tok: str) -> str:
    t = (tok or "").strip()
    low = t.lower().replace("lory", "ivory")  # typo in historical sheet
    if low in ("ivory", "米白", "象牙白", "象牙白色", "象牙", "象牙色"):
        return "米白"
    if t in ("白", "白色") or low == "white":
        return "白"
    if t in ("黑", "黑色") or low == "black":
        return "黑"
    if t in ("蓝", "蓝色") or low == "blue":
        return "蓝"
    return t


def to_short_size_color(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return s
    if s in ("灰蓝", "脏蓝"):
        return s
    # normalize typo lory → ivory for matching
    s2 = re.sub(r"\s+", " ", s)
    s2 = re.sub(r"lory", "ivory", s2, flags=re.I)

    m = re.match(
        r"^(?P<size>102|84|126|120|90圆|60\*102|60\*84|60\*126|70\*120|"
        r"60x102|60x84|60x126|70x120)"
        r"\s*(?P<color>ivory|Ivory|IVORY|米白|象牙白|象牙白色|象牙|白|黑|蓝|白色|黑色|蓝色)$",
        s2,
        re.I,
    )
    if not m:
        return s  # leave specialty / non-size rows

    size_raw = m.group("size")
    color = norm_color(m.group("color"))
    key = size_raw.replace("×", "*").replace("X", "x").replace(" ", "").lower()
    if key in ("102", "60*102", "60x102"):
        short = "102"
    elif key in ("84", "60*84", "60x84"):
        short = "84"
    elif key in ("126", "60*126", "60x126"):
        short = "126"
    elif key in ("120", "70*120", "70x120"):
        short = "120"
    elif "90" in key:
        short = "90圆"
    else:
        return s
    return f"{short}{color}"


def size_color_from_parts(size: str, color: str) -> str:
    s = size.replace("inch", "").replace("Inch", "").strip()
    s = s.replace("×", "*").replace("X", "*").replace("x", "*").replace(" ", "")
    if "round" in size.lower() or s.startswith("90"):
        short = "90圆"
    elif "60*102" in s or s.endswith("102"):
        short = "102"
    elif "60*84" in s or s.endswith("84"):
        short = "84"
    elif "60*126" in s or s.endswith("126"):
        short = "126"
    elif "70*120" in s or s.endswith("120"):
        short = "120"
    else:
        short = s
    return f"{short}{norm_color(color)}"


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def parse_c07_amazon_sku(sku: str):
    m = re.match(
        r"^(?P<cprefix>Ivory|White|I|W|B)(?P<gsm>\d{2,3})(?P<body>90round|\d+)-(?P<spp>\d+)$",
        sku,
        re.I,
    )
    if not m:
        return None
    pref = m.group("cprefix").lower()
    if pref in ("i", "ivory"):
        color = "米白"
    elif pref in ("w", "white"):
        color = "白"
    elif pref == "b":
        color = "黑"  # B11090round-2 only; confirm with user
    else:
        color = "白"
    gsm = m.group("gsm")
    body = m.group("body")
    spp = m.group("spp")
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
    return gsm, size, color, spp


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
            key = size_color_from_parts(line["size"], line["color"])
            spec79[spec][key] += int(line["qty_cartons"])
    detail79 = []
    for spec, sizes in sorted(spec79.items()):
        for i, (sk, cartons) in enumerate(sorted(sizes.items(), key=lambda x: -x[1])):
            detail79.append({"spec": spec if i == 0 else "", "size": sk, "cartons": cartons})

    fs80 = load_json(ROOT / "2_Processed_AI/drafts/C26080_freight_summary.json")
    fba80 = [f["fba_shipment_id"] for f in fs80["files"]]
    spec80: dict = defaultdict(lambda: defaultdict(int))
    for f in fs80["files"]:
        for sp in f.get("specs", []):
            parsed = parse_c07_amazon_sku(sp.get("amazon_sku") or "")
            if not parsed:
                continue
            gsm, size, color, spp = parsed
            key = size_color_from_parts(size, color)
            spec80[f"{gsm}G 桌布-{spp}"][key] += int(
                sp.get("qty_cartons") or sp.get("cartons") or 0
            )
    detail80 = []
    for spec, sizes in sorted(spec80.items()):
        for i, (sk, cartons) in enumerate(sorted(sizes.items(), key=lambda x: -x[1])):
            detail80.append({"spec": spec if i == 0 else "", "size": sk, "cartons": cartons})

    c89 = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26089-C07-40000_C07_20260821_40000/FBA外箱贴/_recognize/c26089_carton_confirm.json"
    )
    return [
        {
            "ticket": "C26079",
            "month": "2026.7",
            "give_label": (
                f"7.31\nC26079 {m79a['shipped_cartons'] + m79b['shipped_cartons']}箱"
                f"\n（A{m79a['shipped_cartons']}+B{m79b['shipped_cartons']}）"
            ),
            "channel": "物易通",
            "fba_ids": fba79,
            "details": detail79,
            "total": m79a["shipped_cartons"] + m79b["shipped_cartons"],
        },
        {
            "ticket": "C26080",
            "month": "2026.7",
            "give_label": f"7.31 易尚\nC26080+C26068 {fs80['cross_check']['order_cartons']}箱",
            "channel": "物易通",
            "fba_ids": fba80,
            "details": detail80,
            "total": fs80["cross_check"]["order_cartons"],
        },
        {
            "ticket": "C26089-A",
            "month": "2026.8",
            "give_label": f"8.29 易尚\nC26089-A {c89['legs']['C26089-A']['qty_cartons']}箱 纽酷SEND",
            "channel": "纽酷",
            "fba_ids": [r["fba_shipment_id"] for r in c89["legs"]["C26089-A"]["rows"]],
            "details": [{"spec": "90G 桌布-10", "size": "102白", "cartons": 500}],
            "total": 500,
        },
        {
            "ticket": "C26089-B",
            "month": "2026.8",
            "give_label": f"8.29 易尚\nC26089-B {c89['legs']['C26089-B']['qty_cartons']}箱 物易通AWD",
            "channel": "物易通",
            "fba_ids": [r["fba_shipment_id"] for r in c89["legs"]["C26089-B"]["rows"]],
            "details": [{"spec": "90G 桌布-10", "size": "102白", "cartons": 500}],
            "total": 500,
        },
    ]


def last_nonempty_row(sh) -> int:
    last = 0
    for r in range(sh.nrows):
        if any(str(sh.cell_value(r, c)).strip() for c in range(min(COLS, sh.ncols))):
            last = r
    return last


def main() -> None:
    src = BAK_CLEAN if BAK_CLEAN.exists() else MAIN
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = INBOX / f"_bak_before_clean_short_{stamp}.xls"
    if MAIN.exists():
        try:
            shutil.copy2(MAIN, bak)
        except PermissionError:
            print("warn: could not bak MAIN (locked)")

    rb = xlrd.open_workbook(str(src))
    sh = rb.sheet_by_index(0)
    last = last_nonempty_row(sh)
    print("src", src.name, "last_nonempty", last + 1, "sheet_nrows", sh.nrows)

    wb = xlwt.Workbook()
    ws = wb.add_sheet("Sheet1")
    changes = []

    for r in range(last + 1):
        for c in range(COLS):
            val = sh.cell_value(r, c) if c < sh.ncols else ""
            if c == 4 and r >= 2 and val != "":
                new = to_short_size_color(str(val))
                if new != str(val).strip():
                    changes.append({"r": r + 1, "from": str(val), "to": new})
                val = new
            if val == "" or val is None:
                continue
            ws.write(r, c, val)

    batches = build_batches()
    r = last + 1
    current_month = None
    for b in batches:
        if b["month"] != current_month:
            ws.write(r, 0, b["month"])
            r += 1
            current_month = b["month"]
        d0 = b["details"][0]
        ws.write(r, 2, b["give_label"])
        if d0.get("spec"):
            ws.write(r, 3, d0["spec"])
        ws.write(r, 4, d0["size"])
        ws.write(r, 6, d0["cartons"])
        ws.write(r, 7, b["channel"])
        ws.write(r, 8, "\n".join(b["fba_ids"]))
        r += 1
        for d in b["details"][1:]:
            if d.get("spec"):
                ws.write(r, 3, d["spec"])
            ws.write(r, 4, d["size"])
            ws.write(r, 6, d["cartons"])
            r += 1

    out_alt = INBOX / f"2025.畅选 发货情况_short_clean_{stamp}.xls"
    saved = MAIN
    try:
        wb.save(str(MAIN))
    except PermissionError:
        wb.save(str(out_alt))
        saved = out_alt
        print("MAIN locked →", out_alt)

    try:
        shutil.copy2(saved, INBOX / "_PROPOSED_jul_aug_20260826.xls")
    except PermissionError:
        pass

    sums = {
        b["ticket"]: (sum(d["cartons"] for d in b["details"]), b["total"]) for b in batches
    }
    report = {
        "saved_to": str(saved),
        "historical_changes": len(changes),
        "sample": changes[:30],
        "sums": sums,
        "end_row": r,
        "B_prefix": {
            "sku": "B11090round-2",
            "fnsku": "X00510BIG5",
            "cartons": 10,
            "written_as": "90圆黑",
        },
    }
    (DRAFTS / "_ship_stats_short_normalize_20260826.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        "# 发货统计 · 简略规格干净重写\n\n",
        f"- 写入：`{saved.name}`\n",
        f"- 历史尺寸统一：**{len(changes)}** 处（含 `lory`→米白）\n",
        "- 格式：`102白` / `84白` / `120米白` / `90圆米白`（无空格、无 60*）\n",
        "- 已去掉表尾空壳行后再追加 7–8 月\n\n",
        "## C26080 唯一 B 前缀\n\n",
        "`B11090round-2` / FNSKU `X00510BIG5` / **10 箱** / 表内写 **90圆黑**\n\n",
        "（同票还有 `W11090round-6`=90圆白；`I…`/`Ivory…`=米白。）\n\n",
        "## 勾稽\n\n",
    ]
    for t, (a, btot) in sums.items():
        md.append(f"- {t}: {a}/{btot} {'OK' if a == btot else 'MISMATCH'}\n")
    (DRAFTS / "_ship_stats_short_normalize_20260826.md").write_text("".join(md), encoding="utf-8")
    print("ok", "changes", len(changes), "end", r, "sums", sums, "saved", saved.name)


if __name__ == "__main__":
    main()
