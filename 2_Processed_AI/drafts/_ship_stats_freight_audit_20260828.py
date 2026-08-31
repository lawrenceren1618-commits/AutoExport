# -*- coding: utf-8 -*-
"""Audit + clean 2026年发货记录.xls: freight, size/color normalize, archive."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import xlrd
from xlutils.copy import copy as xl_copy

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
INBOX = ROOT / "1_Input_Raw/00_Master_Reference/发货统计/_inbox"
XLS = INBOX / "2026年发货记录.xls"
DRAFT = ROOT / "2_Processed_AI/drafts"

# 简化尺寸：短码 = 长边 inch；宽由 canonical 映射
SIZE_SHORT_TO_DIMS = {
    "84": (60, 84),
    "102": (60, 102),
    "126": (60, 126),
    "120": (70, 120),
    "90圆": (90, 90),  # diameter
    "60圆": (60, 60),
}

COLOR_ALIASES = {
    "ivory": "米白",
    "lory": "米白",
    "象牙白": "米白",
    "象牙": "米白",
    "米白": "米白",
    "白": "白",
    "黑": "黑",
}

NIUKU_KEYWORDS = ("纽酷", "纽台", "SEND", "send", "后台扣款")
CARRIER_NAMES = ("物易通", "纽酷", "纽台", "远方", "威旭", "纽台扣款")


def parse_freight(val) -> tuple[str, float | None]:
    s = str(val).strip() if val != "" else ""
    if not s:
        return "", None
    if re.match(r"^[\d.]+$", s):
        return s, float(s)
    if re.match(r"^[\d.]+\+[\d.]+$", s):
        parts = [float(x) for x in s.split("+")]
        return s, sum(parts)
    return s, None


def normalize_size_color(raw: str) -> tuple[str, list[str]]:
    """Return (normalized_size_color, change_notes)."""
    notes: list[str] = []
    s = str(raw).strip()
    if not s:
        return s, notes
    orig = s

    # round: 60 圆 白 / 90圆 白 / 60 inch
    m = re.match(r"^60\s*(?:圆|inch)\s*(.*)$", s, re.I)
    if m:
        color = m.group(1).strip() or ""
        s = "60圆" + _norm_color_suffix(color)
        if s != orig:
            notes.append(f"size {orig!r} -> {s!r}")
        return s, notes

    m = re.match(r"^90\s*圆\s*(.*)$", s)
    if m:
        color = m.group(1).strip()
        s = "90圆" + _norm_color_suffix(color)
        if s != orig:
            notes.append(f"size {orig!r} -> {s!r}")
        return s, notes

    # 60*102 白 / 60x102白 / 102象牙白
    m = re.match(r"^60\s*[\*x×]\s*(\d+)\s*(.*)$", s, re.I)
    if m:
        short = m.group(1)
        color = m.group(2).strip()
        s = f"{short}{_norm_color_suffix(color)}"
        if s != orig:
            notes.append(f"size {orig!r} -> {s!r}")
        return s, notes

    # 102 lory / 102象牙白 / 102 白 / 102白
    m = re.match(r"^(\d+)\s*(.*)$", s)
    if m:
        short = m.group(1)
        rest = m.group(2).strip()
        if short in ("84", "102", "126", "120"):
            s = f"{short}{_norm_color_suffix(rest)}"
            if s != orig:
                notes.append(f"size {orig!r} -> {s!r}")
            return s, notes

    # fallback color only in string
    for alias, canon in COLOR_ALIASES.items():
        if alias.lower() in s.lower() and alias != "米白":
            s2 = re.sub(re.escape(alias), "米白", s, flags=re.I)
            if s2 != s:
                notes.append(f"color in {orig!r} -> {s2!r}")
                s = s2
    return s, notes


def _norm_color_suffix(rest: str) -> str:
    if not rest:
        return ""
    r = rest.strip()
    for alias, canon in sorted(COLOR_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias.lower() in r.lower():
            return canon
    return r


def extract_gsm_and_spec(spec: str) -> tuple[str, int | None, list[str]]:
    """Extract gsm to side column; normalize spec to 桌布-N."""
    notes: list[str] = []
    s = str(spec).strip()
    if not s:
        return s, None, notes
    orig = s
    gsm = None
    lines = s.split("\n")
    first = lines[0].strip()
    tail = "\n".join(lines[1:]).strip()

    def _parse_head(head: str) -> tuple[str, int | None]:
        m = re.match(r"^(90|110|150|180)\s*G\s*(.+)$", head, re.I)
        if m:
            return m.group(2).strip(), int(m.group(1))
        m0 = re.match(r"^(90|110|150|180)G(.+)$", head, re.I)
        if m0:
            return m0.group(2).strip(), int(m0.group(1))
        m2 = re.match(r"^(90|110|150|180)克(.+)$", head)
        if m2:
            return m2.group(2).strip(), int(m2.group(1))
        return head, None

    first, gsm = _parse_head(first)
    s = first if not tail else f"{first}\n{tail}"
    if s != orig and gsm is not None:
        notes.append(f"spec {orig!r} -> {s!r} (gsm={gsm})")
    return s, gsm, notes


def normalize_spec_gsm(spec: str) -> tuple[str, list[str]]:
    s, _gsm, notes = extract_gsm_and_spec(spec)
    return s, notes


def is_niuku_row(channel: str, freight: str) -> bool:
    ch = str(channel).strip()
    fr = str(freight).strip()
    return any(k in ch for k in NIUKU_KEYWORDS) or any(k in fr for k in NIUKU_KEYWORDS)


def audit(wb) -> dict:
    sh = wb.sheet_by_index(0)
    report = {
        "headers": {c: str(sh.cell_value(0, c)) for c in range(sh.ncols)},
        "subheaders": {c: str(sh.cell_value(1, c)) for c in range(sh.ncols)},
        "freight_filled": [],
        "carrier_in_freight": [],
        "niuku_rows": [],
        "size_changes": [],
        "spec_changes": [],
        "extra_cols": {},
        "rows_total": 0,
    }
    for r in range(2, sh.nrows):
        cells = [sh.cell_value(r, c) for c in range(sh.ncols)]
        if not any(str(x).strip() for x in cells[:11]):
            continue
        report["rows_total"] += 1
        month, create, give, spec, size, cost, cartons, channel, fba, freight = cells[:10]
        freight_s, freight_num = parse_freight(freight)
        channel_s = str(channel).strip()

        if freight_num and freight_num > 0:
            report["freight_filled"].append(
                {"r": r + 1, "give": give, "spec": spec, "size": size, "cartons": cartons,
                 "channel": channel_s, "freight": freight}
            )
        if freight_s and freight_num is None and any(k in freight_s for k in CARRIER_NAMES):
            report["carrier_in_freight"].append(
                {"r": r + 1, "give": give, "freight": freight_s, "channel": channel_s}
            )
        if is_niuku_row(channel_s, freight_s):
            report["niuku_rows"].append(
                {"r": r + 1, "give": give, "channel": channel_s, "freight": freight,
                 "should_be_zero": True}
            )

        ns, nnotes = normalize_size_color(size)
        if nnotes:
            report["size_changes"].append({"r": r + 1, "from": size, "to": ns, "notes": nnotes})
        nsp, spnotes = normalize_spec_gsm(spec)
        if spnotes:
            report["spec_changes"].append({"r": r + 1, "from": spec, "to": nsp, "notes": spnotes})

        for i, v in enumerate(cells[11:], start=11):
            if str(v).strip():
                report["extra_cols"].setdefault(str(i), []).append({"r": r + 1, "v": v})

    return report


def apply_clean(src_path: Path, dst_path: Path, report: dict) -> dict:
    rb = xlrd.open_workbook(str(src_path), formatting_info=True)
    rs = rb.sheet_by_index(0)
    wb = xl_copy(rb)
    ws = wb.get_sheet(0)

    # New side columns (L/M): 克重 / 包/箱
    ws.write(0, 11, "克重")
    ws.write(1, 11, "克重")
    ws.write(0, 12, "包/箱")
    ws.write(1, 12, "包/箱")

    applied = {
        "niuku_zeroed": [],
        "freight_moved_to_channel": [],
        "size": [],
        "spec": [],
        "gsm_extracted": [],
    }

    for r in range(2, rs.nrows):
        cells = [rs.cell_value(r, i) for i in range(rs.ncols)]
        if not any(str(x).strip() for x in cells[:11]):
            continue

        channel_s = str(cells[7]).strip()
        freight_s, freight_num = parse_freight(cells[9])
        fr_raw = str(cells[9]).strip()

        # channel: move carrier name out of freight col
        new_channel = channel_s
        if not new_channel and freight_s and freight_num is None:
            if any(k in freight_s for k in CARRIER_NAMES):
                new_channel = freight_s
                applied["freight_moved_to_channel"].append({"r": r + 1, "channel": freight_s})
        ws.write(r, 7, new_channel)

        # freight: SEND/后台扣款 -> 0; carrier text -> empty pending amount
        new_freight = cells[9]
        if freight_num is None and any(k in fr_raw for k in CARRIER_NAMES):
            if is_niuku_row(new_channel or fr_raw, fr_raw):
                new_freight = 0
                applied["niuku_zeroed"].append({"r": r + 1, "reason": "niuku_send"})
            else:
                new_freight = ""
        elif is_niuku_row(new_channel, fr_raw):
            new_freight = 0
            applied["niuku_zeroed"].append({"r": r + 1, "reason": "niuku_send"})
        ws.write(r, 9, new_freight)

        # size normalize
        ns, size_notes = normalize_size_color(cells[4])
        if size_notes:
            applied["size"].append({"r": r + 1, "from": cells[4], "to": ns})
            ws.write(r, 4, ns)

        # spec normalize + gsm extract
        nsp, gsm, spec_notes = extract_gsm_and_spec(cells[3])
        if spec_notes:
            applied["spec"].append({"r": r + 1, "from": cells[3], "to": nsp, "gsm": gsm})
            ws.write(r, 3, nsp)
        if gsm is not None:
            existing_gsm = str(cells[11]).strip() if len(cells) > 11 else ""
            if not existing_gsm:
                ws.write(r, 11, gsm)
                applied["gsm_extracted"].append({"r": r + 1, "gsm": gsm, "spec": nsp})

    wb.save(str(dst_path))
    return applied


def build_normalize_plan(wb) -> dict:
    import collections

    sh = wb.sheet_by_index(0)
    channels: collections.Counter = collections.Counter()
    sizes: collections.Counter = collections.Counter()
    specs_with_gsm = []
    need_size_norm = []
    send_rows = []
    c26_freight = []

    for r in range(2, sh.nrows):
        cells = [sh.cell_value(r, c) for c in range(sh.ncols)]
        if not any(str(x).strip() for x in cells[:11]):
            continue
        ch = str(cells[7]).strip()
        if ch:
            channels[ch] += 1
        size = str(cells[4]).strip()
        if size:
            sizes[size] += 1
        spec = str(cells[3]).strip()
        if re.search(r"^(90|110|150|180)\s*G", spec, re.I):
            specs_with_gsm.append({"r": r + 1, "spec": spec, "size": size})
        ns, notes = normalize_size_color(size)
        if notes and size:
            need_size_norm.append({"r": r + 1, "from": size, "to": ns, "notes": notes})
        if any(k in ch for k in ("后台扣款", "纽酷", "纽台", "SEND")):
            send_rows.append(
                {"r": r + 1, "give": cells[2], "channel": ch, "freight": cells[9], "spec": spec, "size": size}
            )
        give = str(cells[2])
        if "C260" in give or "C26" in give:
            c26_freight.append(
                {"r": r + 1, "give": give, "channel": ch, "freight": cells[9], "size": size, "cartons": cells[6]}
            )

    return {
        "channels": dict(channels),
        "send_rows": send_rows,
        "c26_freight": c26_freight,
        "specs_with_gsm_count": len(specs_with_gsm),
        "specs_with_gsm_sample": specs_with_gsm[:30],
        "need_size_norm_count": len(need_size_norm),
        "need_size_norm": need_size_norm,
        "unique_sizes": dict(sizes),
    }


def main():
    import sys

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rb = xlrd.open_workbook(str(XLS), formatting_info=True)
    plan = build_normalize_plan(rb)
    plan_path = DRAFT / f"_ship_stats_normalize_plan_{ts}.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"plan: {plan_path}")
    print(f"send_rows: {len(plan['send_rows'])}")
    print(f"c26_freight: {len(plan['c26_freight'])}")
    print(f"need_size_norm: {plan['need_size_norm_count']}")

    if "--apply" not in sys.argv:
        report = audit(rb)
        audit_path = DRAFT / f"_ship_stats_freight_audit_{ts}.json"
        audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"audit: {audit_path}")
        print("dry-run only; pass --apply to write cleaned xls")
        return

    bak = INBOX / f"_bak_before_freight_clean_{ts}.xls"
    shutil.copy2(XLS, bak)
    print(f"backup: {bak}")

    report = audit(rb)
    out_json = DRAFT / f"_ship_stats_freight_audit_{ts}.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    tmp = INBOX / f"_tmp_write_freight_clean_{ts}.xls"
    applied = apply_clean(XLS, tmp, report)
    shutil.copy2(tmp, XLS)

    applied_json = DRAFT / f"_ship_stats_freight_applied_{ts}.json"
    applied_json.write_text(json.dumps(applied, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"audit: {out_json}")
    print(f"applied: {applied_json}")
    print(f"rows: {report['rows_total']}")
    print(f"freight_filled: {len(report['freight_filled'])}")
    print(f"carrier_in_freight: {len(report['carrier_in_freight'])}")
    print(f"niuku_rows: {len(report['niuku_rows'])}")
    print(f"size_changes: {len(report['size_changes'])}")
    print(f"spec_changes: {len(report['spec_changes'])}")
    print(f"applied niuku_zeroed: {len(applied['niuku_zeroed'])}")
    print(f"applied size: {len(applied['size'])}")
    print(f"applied spec: {len(applied['spec'])}")
    print(f"applied freight_moved: {len(applied['freight_moved_to_channel'])}")


if __name__ == "__main__":
    main()
