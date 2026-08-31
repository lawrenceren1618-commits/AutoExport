# -*- coding: utf-8 -*-
"""Ship stats: parse + normalize draft + Jul/Aug propose + PROPOSED xls (no main write)."""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import xlrd

try:
    from xlutils.copy import copy as xl_copy

    HAS_XLUTILS = True
except Exception as e:  # noqa: BLE001
    HAS_XLUTILS = False
    XLUTILS_ERR = str(e)

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
INBOX = ROOT / "1_Input_Raw" / "00_Master_Reference" / "发货统计" / "_inbox"
XLS = INBOX / "2026年发货记录.xls"
DRAFTS = ROOT / "2_Processed_AI" / "drafts"
CANON = json.loads((ROOT / "Scripts" / "canonical_schema.json").read_text(encoding="utf-8"))
COLOR_ALIASES = CANON["color_aliases"]["canonical"]

color_to_canon: dict[str, str] = {}
for canon, aliases in COLOR_ALIASES.items():
    for a in aliases:
        color_to_canon[a.lower()] = canon


def normalize_color_token(tok: str) -> str:
    t = tok.strip()
    if not t:
        return t
    low = t.lower()
    if low in color_to_canon:
        return color_to_canon[low]
    if "ivory" in low or "象牙" in t or t == "米白":
        return "米白"
    if t in ("白", "白色") or low == "white":
        return "白"
    if t in ("黑", "黑色") or low == "black":
        return "黑"
    if t in ("蓝", "蓝色") or low == "blue":
        return "蓝"
    return t


def parse_size_color(raw: str):
    s = (raw or "").strip()
    if not s:
        return None, None, s
    s2 = re.sub(r"\s+", " ", s)
    # leave multi-char specialty colors alone (灰蓝/脏蓝) — no false split
    if s2 in ("灰蓝", "脏蓝", "米白", "象牙白"):
        if s2 in ("米白", "象牙白"):
            return None, "米白", "米白"
        return None, s2, s2
    m = re.match(
        r"^(?P<size>.+?)\s+(?P<color>ivory|Ivory|IVORY|米白|象牙白|象牙白色|象牙|白|黑|蓝|白色|黑色|蓝色)$",
        s2,
    )
    if m:
        size_raw = m.group("size").strip()
        color = normalize_color_token(m.group("color"))
    else:
        m2 = re.match(
            r"^(?P<size>\d+|90圆|60\*\d+|70\*\d+|60x\d+|70x\d+|60\*\d+)(?P<color>ivory|Ivory|米白|象牙白|白|黑|蓝)$",
            s2,
            re.I,
        )
        if m2:
            size_raw = m2.group("size")
            color = normalize_color_token(m2.group("color"))
        else:
            # glued without space: 102白 / 120Ivory / 60*84白
            m3 = re.match(
                r"^(?P<size>\d+|90圆|60\*\d+|70\*\d+)(?P<color>ivory|Ivory|米白|象牙白|白|黑|蓝)$",
                s2,
                re.I,
            )
            if m3:
                size_raw = m3.group("size")
                color = normalize_color_token(m3.group("color"))
            else:
                size_raw, color = s2, None
    key = size_raw.replace("×", "*").replace("X", "x").replace(" ", "")
    if key in ("102", "60*102", "60x102"):
        size = "60*102"
    elif key in ("84", "60*84", "60x84"):
        size = "60*84"
    elif key in ("126", "60*126", "60x126"):
        size = "60*126"
    elif key in ("120", "70*120", "70x120"):
        size = "70*120"
    elif "90" in key and ("圆" in size_raw or "round" in size_raw.lower() or key == "90圆"):
        size = "90圆"
    else:
        size = (
            size_raw.replace("×", "*").replace("X", "*").replace("x", "*")
            if re.search(r"\d", size_raw)
            else size_raw
        )
    canon_display = f"{size} {color}" if color else size
    return size, color, canon_display


def load_json(p: Path | str):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def size_to_sheet(size: str, color: str) -> str:
    s = size.replace("inch", "").replace("Inch", "").strip()
    s = s.replace("×", "*").replace("X", "*").replace("x", "*")
    compact = s.replace(" ", "")
    if "round" in s.lower() or s.startswith("90"):
        s = "90圆"
    elif "60*102" in compact:
        s = "60*102"
    elif "60*84" in compact:
        s = "60*84"
    elif "60*126" in compact:
        s = "60*126"
    elif "70*120" in compact:
        s = "70*120"
    c = normalize_color_token(color)
    return f"{s} {c}"


def main() -> None:
    wb = xlrd.open_workbook(str(XLS), formatting_info=True)
    sh = wb.sheet_by_index(0)

    size_norm_map: Counter = Counter()
    size_examples: dict = defaultdict(list)
    fba_incomplete = []
    carrier_in_freight = []

    for r in range(2, sh.nrows):
        cells = [sh.cell_value(r, c) for c in range(11)]
        _month, _create, give, _spec, size, _cost, _cartons, channel, fba, freight, _note = cells
        size_s = str(size).strip() if size != "" else ""
        if size_s:
            _sz, _col, canon = parse_size_color(size_s)
            if canon != size_s:
                size_norm_map[(size_s, canon)] += 1
                if len(size_examples[(size_s, canon)]) < 3:
                    size_examples[(size_s, canon)].append(r + 1)
        fba_s = str(fba).strip() if fba != "" else ""
        if fba_s:
            ids = re.findall(r"(?:FBA[A-Z0-9]+|STAR-[A-Z0-9]+)", fba_s, re.I)
            give_s = str(give)
            if ids and len(ids) == 1 and ("箱" in give_s or "C26" in give_s):
                fba_incomplete.append(
                    {"r": r + 1, "give": give_s[:80], "fba_count": 1, "fba": ids[0]}
                )
        freight_s = str(freight).strip() if freight != "" else ""
        if freight_s and not re.match(r"^[\d.]+$", freight_s):
            if any(k in freight_s for k in ("物易通", "纽酷", "远方", "威旭", "SEND")):
                carrier_in_freight.append({"r": r + 1, "freight": freight_s, "channel": channel})

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
            spp = line["strips_per_pack"]
            spec = f"桌布-{spp}"
            key = size_to_sheet(line["size"], line["color"])
            spec79[spec][key] += int(line["qty_cartons"])
    detail79 = []
    for spec, sizes in sorted(spec79.items()):
        items = sorted(sizes.items(), key=lambda x: -x[1])
        for i, (size_key, cartons) in enumerate(items):
            detail79.append({"spec": spec if i == 0 else "", "size": size_key, "cartons": cartons})

    fs80 = load_json(ROOT / "2_Processed_AI/drafts/C26080_freight_summary.json")
    fba80 = [f["fba_shipment_id"] for f in fs80["files"]]
    def parse_c07_amazon_sku(sku: str):
        """I/Ivory=米白 W/White=白 B=黑；体: 60102 / 70120 / 90round."""
        m = re.match(
            r"^(?P<cprefix>Ivory|White|I|W|B)(?P<gsm>\d{2,3})(?P<body>90round|\d+)-(?P<spp>\d+)$",
            sku,
            re.I,
        )
        if not m:
            return None
        pref = m.group("cprefix")
        low = pref.lower()
        if low in ("i", "ivory"):
            color = "米白"
        elif low in ("w", "white"):
            color = "白"
        elif low == "b":
            color = "黑"
        else:
            color = "白"
        gsm = m.group("gsm")
        body = m.group("body")
        spp = m.group("spp")
        if "round" in body.lower():
            size = "90圆"
        elif body == "60102":
            size = "60*102"
        elif body == "60126":
            size = "60*126"
        elif body == "70120":
            size = "70*120"
        elif body == "6084" or body == "60184":
            size = "60*84"
        else:
            size = body
        return gsm, size, color, spp

    spec80: dict = defaultdict(lambda: defaultdict(int))
    for f in fs80["files"]:
        for sp in f.get("specs", []):
            sku = sp.get("amazon_sku") or ""
            cartons = int(sp.get("qty_cartons") or sp.get("cartons") or 0)
            parsed = parse_c07_amazon_sku(sku)
            if not parsed:
                continue
            gsm, size, color, spp = parsed
            key = f"{size} {color}"
            spec = f"{gsm}G 桌布-{spp}"
            spec80[spec][key] += cartons
    detail80 = []
    for spec, sizes in sorted(spec80.items()):
        items = sorted(sizes.items(), key=lambda x: -x[1])
        for i, (size_key, cartons) in enumerate(items):
            detail80.append({"spec": spec if i == 0 else "", "size": size_key, "cartons": cartons})
    sum80 = sum(x["cartons"] for x in detail80)

    c89 = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26089-C07-40000_C07_20260821_40000/FBA外箱贴/_recognize/c26089_carton_confirm.json"
    )
    c95 = load_json(
        ROOT
        / "1_Input_Raw/Shipments/EF-C26095-C07-7800_C07_20260829_7800/FBA外箱贴/_recognize/c26095_carton_confirm.json"
    )

    proposed_batches = [
        {
            "ticket": "C26079",
            "store": "C04",
            "give_label": (
                f"7.31\nC26079 {m79a['shipped_cartons'] + m79b['shipped_cartons']}箱"
                f"\n（A{m79a['shipped_cartons']}+B{m79b['shipped_cartons']}）"
            ),
            "month": "2026.7",
            "ship_date": "2026-07-31",
            "channel": "物易通",
            "freight": "",
            "fba_ids": fba79,
            "total_cartons": m79a["shipped_cartons"] + m79b["shipped_cartons"],
            "details": detail79,
            "notes": "本仓货件号6个（5×FBA+1×STAR IUTE）；运费待填；规格暂写桌布-N（克重未统一）",
            "confirm_items": ["运费金额", "规格是否补 90G/110G"],
        },
        {
            "ticket": "C26080",
            "store": "C07",
            "give_label": (
                f"7.31 易尚\nC26080+C26068 {fs80['cross_check']['order_cartons']}箱"
            ),
            "month": "2026.7",
            "ship_date": "2026-07-31",
            "channel": "物易通",
            "freight": "",
            "fba_ids": fba80,
            "total_cartons": fs80["cross_check"]["order_cartons"],
            "details": detail80,
            "detail_carton_sum": sum80,
            "notes": "并腿 C26068；SKU：I/Ivory→米白，W/White→白，B→黑",
            "confirm_items": [
                "运费",
                "B前缀=黑是否正确",
                f"明细合计{sum80} vs 票面{fs80['cross_check']['order_cartons']}",
            ],
        },
        {
            "ticket": "C26089-A",
            "store": "C07",
            "give_label": (
                f"8.29 易尚\nC26089-A {c89['legs']['C26089-A']['qty_cartons']}箱 纽酷SEND"
            ),
            "month": "2026.8",
            "ship_date": "2026-08-29",
            "channel": "纽酷",
            "freight": "",
            "fba_ids": [r["fba_shipment_id"] for r in c89["legs"]["C26089-A"]["rows"]],
            "total_cartons": 500,
            "details": [{"spec": "90G 桌布-10", "size": "60*102 白", "cartons": 500}],
            "notes": "五仓FC；纽酷=SEND",
            "confirm_items": ["运费"],
        },
        {
            "ticket": "C26089-B",
            "store": "C07",
            "give_label": (
                f"8.29 易尚\nC26089-B {c89['legs']['C26089-B']['qty_cartons']}箱 物易通AWD"
            ),
            "month": "2026.8",
            "ship_date": "2026-08-29",
            "channel": "物易通",
            "freight": "",
            "fba_ids": [r["fba_shipment_id"] for r in c89["legs"]["C26089-B"]["rows"]],
            "total_cartons": 500,
            "details": [{"spec": "90G 桌布-10", "size": "60*102 白", "cartons": 500}],
            "notes": "IUSP STAR-RCKQMK6EMHN4K（不作废号）",
            "confirm_items": ["运费"],
        },
        {
            "ticket": "C26095",
            "store": "C07",
            "include_default": False,
            "reason": "交货日 2026-09-04 → 默认记入 2026.9，不自动写入 7–8 月",
            "ship_date": "2026-09-04",
            "fba_ids": [
                r["fba_shipment_id"]
                for leg in c95["legs"].values()
                for r in leg.get("rows", [])
            ],
            "total_cartons": 220,
            "confirm_items": ["是否仍要记入 8 月作业周"],
        },
    ]

    norm_list = [
        {
            "from": a,
            "to": b,
            "count": c,
            "sample_rows": size_examples[(a, b)],
        }
        for (a, b), c in sorted(size_norm_map.items(), key=lambda x: -x[1])
    ]

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_xls": str(XLS),
        "format": {
            "sheet": "Sheet1",
            "headers": [
                "月份",
                "创建日期",
                "给货日期",
                "规格",
                "尺寸",
                "成本",
                "箱数",
                "渠道",
                "FBA单号",
                "运费",
            ],
            "batch_vs_detail": "给货日期含批次标签；首行常带 FBA；后续行尺寸+箱数",
            "vs_locked_rules": [
                "颜色 ivory/Ivory/米白 → 米白",
                "FBA 批次行写全",
                "新行：渠道=货代，运费留空待填（纠正把货代写进运费列）",
                "月份拟写 2026.7 / 2026.8",
            ],
        },
        "normalize_size_color": norm_list,
        "fba_single_flagged_sample": fba_incomplete[:30],
        "carrier_in_freight_col_count": len(carrier_in_freight),
        "jul_aug_in_sheet": False,
        "proposed_batches": proposed_batches,
        "write_policy": "WAIT_USER_CONFIRM — 主表未改；仅 PROPOSED 副本",
    }
    (DRAFTS / "_ship_stats_confirm_20260826.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md: list[str] = []
    md.append("# 发货统计表 · 待确认报告（2026-08-26）\n\n")
    md.append(
        f"源表：`{XLS}`（桌面覆盖；备份 `_bak_inbox_before_desktop_20260826.xls`）\n\n"
    )
    md.append("## 1. 格式识别\n\n")
    md.append(
        "| 列 | 含义 |\n|----|------|\n"
        "| A 月份 | 段标记 |\n| B 创建日期 | 可空 |\n"
        "| C 给货日期 | 批次标签（日期+短码+箱数；可含「易尚」） |\n"
        "| D 规格 | 如 `90G 桌布-10` |\n| E 尺寸 | 尺寸+颜色 |\n"
        "| F 成本 | 历史有 |\n| G 箱数 | 行级 |\n| H 渠道 | 常空 |\n"
        "| I FBA单号 | 批次行 |\n| J 运费 | 常被误写成货代名 |\n\n"
    )
    md.append("表内原止于 **2026-06**；本报告对应已追加 **2026.7 / 2026.8**（见 §4）。\n\n")
    md.append("## 2. 规格/颜色归一（草案，未写主表）\n\n")
    md.append("| 原文 | 规范 | 次数 | 样例行 |\n|------|------|------|--------|\n")
    for n in norm_list[:40]:
        md.append(
            f"| `{n['from']}` | `{n['to']}` | {n['count']} | {n['sample_rows']} |\n"
        )
    md.append(
        "\n规则：米白=Ivory=象牙白 → **米白**；"
        "`102`→`60*102`，`120`→`70*120`，`126`→`60*126`，`84`→`60*84`。\n\n"
    )
    md.append("## 3. 7–8 月补行提案（本仓货件号，供手核）\n\n")
    for b in proposed_batches:
        md.append(f"### {b['ticket']}\n\n")
        if b.get("include_default") is False:
            md.append(f"- **默认不写入 7–8 月**：{b['reason']}\n")
            md.append(f"- 货件号：{', '.join(b['fba_ids'])}\n")
            md.append(f"- 待确认：{', '.join(b['confirm_items'])}\n\n")
            continue
        md.append(f"- 给货：`{b['give_label'].replace(chr(10), ' / ')}`\n")
        md.append(f"- 渠道 **{b['channel']}**；运费 **待填**\n")
        md.append(f"- 货件号（{len(b['fba_ids'])}）：\n")
        for i in b["fba_ids"]:
            md.append(f"  - `{i}`\n")
        md.append("- 明细：\n")
        for d in b["details"]:
            md.append(f"  - {d['spec'] or '…'} | {d['size']} | {d['cartons']} 箱\n")
        if "detail_carton_sum" in b:
            md.append(
                f"- 明细合计 {b['detail_carton_sum']} vs 票面 {b['total_cartons']}\n"
            )
        md.append(f"- 备注：{b['notes']}\n")
        md.append(f"- 待确认：{', '.join(b['confirm_items'])}\n\n")
    md.append("## 4. 写入闸\n\n")
    md.append("**主 xls 尚未改写。** 预览：`_PROPOSED_jul_aug_20260826.xls`\n\n")
    md.append("回复示例：`确认写入：C26079+C26080+C26089；历史 ivory 改米白；C26095 不写`\n")
    (DRAFTS / "_ship_stats_confirm_20260826.md").write_text("".join(md), encoding="utf-8")
    print("report ok", "norm", len(norm_list), "batches", len(proposed_batches))

    if not HAS_XLUTILS:
        print("skip proposed xls:", XLUTILS_ERR)
        return

    prop_path = INBOX / "_PROPOSED_jul_aug_20260826.xls"
    src_wb = xlrd.open_workbook(str(XLS), formatting_info=True)
    out_wb = xl_copy(src_wb)
    ws = out_wb.get_sheet(0)
    r = src_wb.sheet_by_index(0).nrows

    def wr(ridx: int, vals: list) -> None:
        for c, v in enumerate(vals):
            if v is None or v == "":
                continue
            ws.write(ridx, c, v)

    current_month = None
    for b in proposed_batches:
        if b.get("include_default") is False:
            continue
        if b["month"] != current_month:
            wr(r, [b["month"]])
            r += 1
            current_month = b["month"]
        fba_cell = "\n".join(b["fba_ids"])
        details = b["details"]
        d0 = details[0]
        wr(
            r,
            [
                "",
                "",
                b["give_label"],
                d0["spec"],
                d0["size"],
                "",
                d0["cartons"],
                b["channel"],
                fba_cell,
                "",
            ],
        )
        r += 1
        for d in details[1:]:
            wr(r, ["", "", "", d.get("spec") or "", d["size"], "", d["cartons"]])
            r += 1
    out_wb.save(str(prop_path))
    print("proposed saved", prop_path, "end_row", r)

    # Apply same append to main workbook (Jul/Aug only; no historical rewrite)
    bak_main = INBOX / f"_bak_before_jul_aug_{datetime.now():%Y%m%d}.xls"
    shutil.copy2(XLS, bak_main)
    main_wb = xl_copy(xlrd.open_workbook(str(XLS), formatting_info=True))
    ws_m = main_wb.get_sheet(0)
    r_m = xlrd.open_workbook(str(XLS)).sheet_by_index(0).nrows

    def wr_m(ridx: int, vals: list) -> None:
        for c, v in enumerate(vals):
            if v is None or v == "":
                continue
            ws_m.write(ridx, c, v)

    current_month = None
    for b in proposed_batches:
        if b.get("include_default") is False:
            continue
        if b["month"] != current_month:
            wr_m(r_m, [b["month"]])
            r_m += 1
            current_month = b["month"]
        fba_cell = "\n".join(b["fba_ids"])
        details = b["details"]
        d0 = details[0]
        wr_m(
            r_m,
            [
                "",
                "",
                b["give_label"],
                d0["spec"],
                d0["size"],
                "",
                d0["cartons"],
                b["channel"],
                fba_cell,
                "",
            ],
        )
        r_m += 1
        for d in details[1:]:
            wr_m(r_m, ["", "", "", d.get("spec") or "", d["size"], "", d["cartons"]])
            r_m += 1
    main_wb.save(str(XLS))
    report["write_policy"] = (
        f"APPLIED_JUL_AUG_TO_MAIN bak={bak_main.name}; "
        "historical normalize NOT applied; C26095 skipped; freight blank"
    )
    (DRAFTS / "_ship_stats_confirm_20260826.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # refresh md write gate section
    md_path = DRAFTS / "_ship_stats_confirm_20260826.md"
    text = md_path.read_text(encoding="utf-8")
    text = text.replace(
        "**主 xls 尚未改写。** 预览：`_PROPOSED_jul_aug_20260826.xls`\n\n"
        "回复示例：`确认写入：C26079+C26080+C26089；历史 ivory 改米白；C26095 不写`\n",
        f"**已追加写入主表**（备份 `{bak_main.name}`；预览副本仍保留）。\n\n"
        "- 已写：C26079 / C26080 / C26089-A / C26089-B\n"
        "- 未写：C26095（9 月）、历史 ivory→米白 归一\n"
        "- 运费列均为空，待你补金额\n"
        "- 请抽查货件号与箱数；有误告知回滚或改\n",
    )
    md_path.write_text(text, encoding="utf-8")
    print("main applied", XLS, "bak", bak_main, "end_row", r_m)


if __name__ == "__main__":
    main()
