# -*- coding: utf-8 -*-
"""
发货记录补丁（2026-08-28）：
1. 追加 C26095（9 月 · Gate CONFIRMED split_ledger）
2. 2026+ 桌布行：沉淀库可唯一匹配时填 M 列包/箱

不写运费（物易通腿仍待你补金额）。
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import xlrd

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
INBOX = ROOT / "1_Input_Raw/00_Master_Reference/发货统计/_inbox"
OUT = INBOX / "2026年发货记录.xls"
DRAFT = ROOT / "2_Processed_AI/drafts"
SETTLED = ROOT / "Scripts/settled_knowledge_db.json"
DIMS = ROOT / "Scripts/ship_stats_size_dims.json"
SPLIT = ROOT / "1_Input_Raw/Shipments/EF-C26095-C07-7800_C07_20260829_7800/拆单比对/split_ledger.json"

COL_MONTH, COL_CREATE = 0, 1
COL_GIVE, COL_GSM = 2, 3
COL_SPEC, COL_SIZE, COL_COST = 4, 5, 6
COL_CARTONS, COL_CHANNEL = 7, 8
COL_FBA, COL_FREIGHT, COL_NOTE = 9, 10, 11
COL_PACK = 12
NUM_COLS = 13


def load_v3():
    name = "ship_stats_clean_v3_20260828"
    spec = importlib.util.spec_from_file_location(name, DRAFT / "_ship_stats_clean_v3_20260828.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def size_short(size: str, color: str) -> str:
    s = str(size).replace("inch", "").replace(" ", "")
    if "round" in s.lower() or "圆" in s:
        return "90圆" + color if "90" in s else "60圆" + color
    m = re.match(r"(\d+)X(\d+)", s, re.I)
    if m:
        return f"{m.group(2)}{color}"
    return f"{s}{color}"


def read_out_rows(sh) -> list:
    v3 = load_v3()
    rows: list[v3.RowOut] = []
    for r in range(2, sh.nrows):
        vals = [sh.cell_value(r, c) if c < sh.ncols else "" for c in range(NUM_COLS)]
        if not any(str(x).strip() for x in vals):
            rows.append(v3.RowOut(src_r=r + 1, is_separator=True))
            continue
        rows.append(
            v3.RowOut(
                month=vals[COL_MONTH],
                create=vals[COL_CREATE],
                give=vals[COL_GIVE],
                gsm=vals[COL_GSM],
                spec=vals[COL_SPEC],
                size=vals[COL_SIZE],
                cost=vals[COL_COST],
                cartons=vals[COL_CARTONS],
                channel=vals[COL_CHANNEL],
                fba=vals[COL_FBA],
                freight=vals[COL_FREIGHT],
                note=vals[COL_NOTE],
                pack_per_ctn=vals[COL_PACK],
                src_r=r + 1,
                in_scope=True,
                is_tablecloth=bool(str(vals[COL_SPEC]).strip().isdigit() or str(vals[COL_SIZE]).strip()),
            )
        )
    return rows


def has_c26095(rows) -> bool:
    for row in rows:
        if "C26095" in str(row.give):
            return True
    return False


def append_c26095(rows, v3) -> list[str]:
    ledger = json.loads(SPLIT.read_text(encoding="utf-8"))
    changes = []
    if has_c26095(rows):
        changes.append("skip: C26095 already present")
        return changes

    a = ledger["batches"][0]
    b = ledger["batches"][1]
    wh_a = a["warehouses"][0]
    wh_b = b["warehouses"][0]

    def spec_rows(batch, leg_id, month_first=False):
        out = []
        first = True
        for item in batch["by_fnsku"]:
            sz = size_short(item["size"], item["color"])
            ppc = item["packs_per_carton"]
            if first:
                give = f"9.4 易尚\n{leg_id} {batch['shipped_cartons']}箱"
                out.append(
                    v3.RowOut(
                        month="2026.9" if month_first else "",
                        give=give,
                        gsm=90,
                        spec=str(item["strips_per_pack"]),
                        size=sz,
                        cartons=item["qty_cartons"],
                        channel=batch["freight_forwarder"],
                        fba=wh_a["fba_shipment_id"] if leg_id.endswith("-A") else wh_b["fba_shipment_id"],
                        freight="",
                        pack_per_ctn=ppc,
                        in_scope=True,
                        is_tablecloth=True,
                        changes=[f"append {leg_id}"],
                    )
                )
                first = False
            else:
                out.append(
                    v3.RowOut(
                        give="",
                        gsm=90,
                        spec=str(item["strips_per_pack"]),
                        size=sz,
                        cartons=item["qty_cartons"],
                        pack_per_ctn=ppc,
                        in_scope=True,
                        is_tablecloth=True,
                        changes=[f"append {leg_id} detail"],
                    )
                )
        return out

    rows.extend(spec_rows(a, "C26095-A", month_first=True))
    rows.extend(spec_rows(b, "C26095-B"))
    changes.append("appended C26095-A/B (4 spec lines)")
    return changes


def parse_size_color(size: str) -> tuple[str, str]:
    s = str(size).strip()
    m = re.match(r"^(90圆|60圆)(.*)$", s)
    if m:
        return m.group(1), m.group(2) or "白"
    m = re.match(r"^(84|102|126|120)(.*)$", s)
    if m:
        return m.group(1), m.group(2) or "白"
    return s, ""


def lookup_ppc(settled: dict, dims: dict, strips: int, size: str, gsm) -> int | None:
    short, color = parse_size_color(size)
    entry = dims.get("short_to_dims", {}).get(short)
    if not entry:
        return None
    full = entry["order_full"]
    gw = f"{int(float(gsm))}G" if gsm not in ("", None) else "90G"
    hits = []
    for row in settled.get("packing_standards", []):
        if row.get("strips_per_pack") != strips:
            continue
        if row.get("size") != full:
            continue
        if row.get("gram_weight", "90G") not in (gw, "90G", "110G") and gw not in ("90G", "110G"):
            continue
        hits.append(row["packs_per_carton"])
    uniq = sorted(set(hits))
    return uniq[0] if len(uniq) == 1 else None


def fill_pack_per_ctn(rows, settled, dims) -> tuple[int, list]:
    filled = 0
    skipped = []
    for row in rows:
        if row.is_separator:
            continue
        if row.pack_per_ctn not in ("", None, 0):
            continue
        spec = str(row.spec).strip()
        size = str(row.size).strip()
        if not spec.isdigit() or not size:
            continue
        if not str(row.gsm).strip() and spec in ("6", "2"):
            skipped.append({"size": size, "spec": spec, "reason": "6/2条无沉淀库行"})
            continue
        ppc = lookup_ppc(settled, dims, int(spec), size, row.gsm)
        if ppc:
            row.pack_per_ctn = ppc
            row.changes.append(f"ppc<-settled {ppc}")
            filled += 1
        else:
            skipped.append({"size": size, "spec": spec, "gsm": row.gsm, "reason": "no_unique_ppc"})
    return filled, skipped


def main():
    v3 = load_v3()
    if not OUT.exists():
        raise SystemExit(f"missing {OUT}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(OUT, INBOX / f"_bak_before_c26095_ppc_{ts}.xls")

    sh = xlrd.open_workbook(str(OUT)).sheet_by_index(0)
    rows = read_out_rows(sh)

    settled = json.loads(SETTLED.read_text(encoding="utf-8"))
    dims = json.loads(DIMS.read_text(encoding="utf-8"))

    log = {"append": append_c26095(rows, v3)}
    filled, skipped = fill_pack_per_ctn(rows, settled, dims)
    log["ppc_filled"] = filled
    log["ppc_skipped"] = skipped[:50]
    log["ppc_skipped_count"] = len(skipped)

    wb = v3.write_sheet(rows)
    tmp = INBOX / f"_tmp_patch_c26095_ppc_{ts}.xls"
    wb.save(str(tmp))
    shutil.copy2(tmp, OUT)

    report = DRAFT / f"_ship_stats_patch_c26095_ppc_report_{ts}.json"
    report.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"out: {OUT}")
    print(f"report: {report}")
    print(json.dumps(log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
