# -*- coding: utf-8 -*-
"""Rewrite ship-stats xls: short size+color (102白), unify ivory→米白, re-append Jul/Aug."""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import xlrd
from xlutils.copy import copy as xl_copy

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
INBOX = ROOT / "1_Input_Raw" / "00_Master_Reference" / "发货统计" / "_inbox"
MAIN = INBOX / "2026年发货记录.xls"
BAK_CLEAN = INBOX / "_bak_before_jul_aug_20260826.xls"
DRAFTS = ROOT / "2_Processed_AI" / "drafts"


def norm_color(tok: str) -> str:
    t = (tok or "").strip()
    low = t.lower()
    if low in ("ivory", "米白", "象牙白", "象牙白色", "象牙", "象牙色"):
        return "米白"
    if t in ("白", "白色") or low == "white":
        return "白"
    if t in ("黑", "黑色") or low == "black":
        return "黑"
    if t in ("蓝", "蓝色") or low == "blue":
        return "蓝"
    return t


def to_short_size_color(raw: str) -> str | None:
    """Return short form like 102白 / 90圆米白, or None if leave unchanged."""
    s = (raw or "").strip()
    if not s:
        return None
    if s in ("灰蓝", "脏蓝"):
        return s  # specialty — keep
    s2 = re.sub(r"\s+", " ", s)

    # already short glued: 102白 / 90圆米白 / 120Ivory
    m = re.match(
        r"^(?P<size>102|84|126|120|90圆|60\*102|60\*84|60\*126|70\*120|60x102|60x84|60x126|70x120)"
        r"\s*(?P<color>ivory|Ivory|IVORY|米白|象牙白|象牙白色|象牙|白|黑|蓝|白色|黑色|蓝色)$",
        s2,
        re.I,
    )
    if not m:
        # size only without color
        return None

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
    elif "90" in key or key == "90圆":
        short = "90圆"
    else:
        return None
    return f"{short}{color}"


def size_color_from_parts(size: str, color: str) -> str:
    """Canonical sheet short from pipeline size+color."""
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
        # only B11090round-2 in C26080 — treat as 黑 pending user; keep 黑 for now
        color = "黑"
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


def build_jul_aug_batches():
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
        items = sorted(sizes.items(), key=lambda x: -x[1])
        for i, (sk, cartons) in enumerate(items):
            detail79.append({"spec": spec if i == 0 else "", "size": sk, "cartons": cartons})

    fs80 = load_json(ROOT / "2_Processed_AI/drafts/C26080_freight_summary.json")
    fba80 = [f["fba_shipment_id"] for f in fs80["files"]]
    spec80: dict = defaultdict(lambda: defaultdict(int))
    b_skus = []
    for f in fs80["files"]:
        for sp in f.get("specs", []):
            sku = sp.get("amazon_sku") or ""
            if sku.startswith("B"):
                b_skus.append(
                    {
                        "sku": sku,
                        "fnsku": sp.get("fnsku"),
                        "cartons": int(sp.get("qty_cartons") or sp.get("cartons") or 0),
                        "wh": f.get("warehouse_code"),
                    }
                )
            parsed = parse_c07_amazon_sku(sku)
            if not parsed:
                continue
            gsm, size, color, spp = parsed
            key = size_color_from_parts(size, color)
            spec80[f"{gsm}G 桌布-{spp}"][key] += int(
                sp.get("qty_cartons") or sp.get("cartons") or 0
            )
    detail80 = []
    for spec, sizes in sorted(spec80.items()):
        items = sorted(sizes.items(), key=lambda x: -x[1])
        for i, (sk, cartons) in enumerate(items):
            detail80.append({"spec": spec if i == 0 else "", "size": sk, "cartons": cartons})

    c89 = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26089-C07-40000_C07_20260821_40000/FBA外箱贴/_recognize/c26089_carton_confirm.json"
    )

    batches = [
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
            "b_prefix_note": b_skus,
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
    return batches


def main() -> None:
    src = BAK_CLEAN if BAK_CLEAN.exists() else MAIN
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = INBOX / f"_bak_before_short_normalize_{stamp}.xls"
    shutil.copy2(MAIN, bak)

    rb = xlrd.open_workbook(str(src), formatting_info=True)
    sh = rb.sheet_by_index(0)
    wb = xl_copy(rb)
    ws = wb.get_sheet(0)

    changes = []
    for r in range(2, sh.nrows):
        raw = sh.cell_value(r, 4)
        if raw == "" or raw is None:
            continue
        raw_s = str(raw).strip()
        new = to_short_size_color(raw_s)
        if new and new != raw_s:
            ws.write(r, 4, new)
            changes.append({"r": r + 1, "from": raw_s, "to": new})

    batches = build_jul_aug_batches()
    r = sh.nrows
    current_month = None
    for b in batches:
        if b["month"] != current_month:
            ws.write(r, 0, b["month"])
            r += 1
            current_month = b["month"]
        fba_cell = "\n".join(b["fba_ids"])
        d0 = b["details"][0]
        ws.write(r, 2, b["give_label"])
        if d0.get("spec"):
            ws.write(r, 3, d0["spec"])
        ws.write(r, 4, d0["size"])
        ws.write(r, 6, d0["cartons"])
        ws.write(r, 7, b["channel"])
        ws.write(r, 8, fba_cell)
        r += 1
        for d in b["details"][1:]:
            if d.get("spec"):
                ws.write(r, 3, d["spec"])
            ws.write(r, 4, d["size"])
            ws.write(r, 6, d["cartons"])
            r += 1

    out_path = INBOX / f"2025.畅选 发货情况_short_{stamp}.xls"
    try:
        wb.save(str(MAIN))
        saved = MAIN
    except PermissionError:
        wb.save(str(out_path))
        saved = out_path
        print("MAIN locked; wrote", out_path)
    try:
        shutil.copy2(saved, INBOX / "_PROPOSED_jul_aug_20260826.xls")
    except PermissionError:
        pass

    # verify sums
    sums = {b["ticket"]: (sum(d["cartons"] for d in b["details"]), b["total"]) for b in batches}
    b_note = next((b.get("b_prefix_note") for b in batches if b["ticket"] == "C26080"), [])

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_base": str(src),
        "bak": str(bak),
        "saved_to": str(saved),
        "main_locked": saved != MAIN,
        "size_format": "short glued e.g. 102白 / 90圆米白",
        "historical_normalize_changes": len(changes),
        "historical_sample": changes[:40],
        "jul_aug_sums": sums,
        "c26080_B_prefix_only_sku": {
            "amazon_sku": "B11090round-2",
            "fnsku": "X00510BIG5",
            "meaning_guess": "110G 90圆 2条装；前缀 B 暂映射为黑（请确认）",
            "total_cartons": 10,
            "by_warehouse": b_note,
        },
        "end_row": r,
    }
    (DRAFTS / "_ship_stats_short_normalize_20260826.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = []
    md.append("# 发货统计 · 简略规格重写（2026-08-26）\n\n")
    md.append(f"- 基底：`{src.name}`；备份 `{bak.name}`\n")
    md.append(f"- 写入：`{saved.name}`" + ("（**主表被 Excel 占用，请关闭后让我覆盖主表**）" if saved != MAIN else "") + "\n")
    md.append("- 尺寸格式：**简略粘连** `102白` / `84白` / `120米白` / `90圆米白`（ivory→米白）\n")
    md.append(f"- 历史尺寸改写：**{len(changes)}** 处\n")
    md.append("- 7–8 月已按同格式重写追加；C26095 仍不写\n\n")
    md.append("## C26080 的 B 前缀 SKU\n\n")
    md.append("| amazon_sku | FNSKU | 箱数合计 | 说明 |\n|------------|-------|----------|------|\n")
    md.append("| `B11090round-2` | `X00510BIG5` | **10** | 全票仅此一个 B 前缀；表内暂写 **90圆黑** |\n\n")
    md.append("若 B 不是黑，告诉我正确颜色，我改这 10 箱。\n\n")
    md.append("## 箱数勾稽\n\n")
    for t, (a, btot) in sums.items():
        md.append(f"- {t}: 明细 {a} / 票面 {btot} {'OK' if a == btot else 'MISMATCH'}\n")
    (DRAFTS / "_ship_stats_short_normalize_20260826.md").write_text("".join(md), encoding="utf-8")
    print("ok changes", len(changes), "end", r, "saved", saved)
    print("B sku only: B11090round-2 / X00510BIG5 / 10 cartons")


if __name__ == "__main__":
    main()
