# -*- coding: utf-8 -*-
"""
发货记录 v2 清洗：从备份重建，插入 C 列克重，仅 2026+ 桌布行做规格/尺寸归一。
非桌布（阁楼秸秆等）原样保留；全表居中+细框线；批次级合并。
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import xlrd
import xlwt

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
INBOX = ROOT / "1_Input_Raw/00_Master_Reference/发货统计/_inbox"
SRC = INBOX / "_bak_before_freight_clean_20260828_100853.xls"
OUT = INBOX / "2026年发货记录.xls"
DRAFT = ROOT / "2_Processed_AI/drafts"

STY_WRAP = xlwt.easyxf(
    "align: wrap on, vert centre, horiz centre;"
    "borders: left thin, right thin, top thin, bottom thin"
)
STY_CELL = xlwt.easyxf(
    "align: wrap off, vert centre, horiz centre;"
    "borders: left thin, right thin, top thin, bottom thin"
)
STY_SEP = xlwt.easyxf(
    "pattern: pattern solid, fore_colour pale_blue;"
    "borders: left thin, right thin, top thin, bottom thin;"
    "align: wrap off, vert centre, horiz centre"
)

# 新列布局（0-based）
COL_MONTH, COL_CREATE, COL_GSM = 0, 1, 2
COL_GIVE, COL_SPEC, COL_SIZE = 3, 4, 5
COL_COST, COL_CARTONS, COL_CHANNEL = 6, 7, 8
COL_FBA, COL_FREIGHT, COL_NOTE = 9, 10, 11
COL_PACK_PER_CTN = 12
NUM_COLS = 13

NON_TABLECLOTH = ("秸秆", "阁", "桌旗", "假发", "楼梯", "游戏", "餐垫", "头套", "混合")
COLOR_ALIASES = {
    "ivory": "米白", "lory": "米白", "象牙白": "米白", "象牙": "米白",
}
NIUKU_KW = ("纽酷", "纽台", "SEND", "后台扣款")
CARRIERS = ("物易通", "纽酷", "纽台", "远方", "威旭", "德邦", "飞特")


@dataclass
class RowOut:
    month: object = ""
    create: object = ""
    gsm: object = ""
    give: object = ""
    spec: object = ""
    size: object = ""
    cost: object = ""
    cartons: object = ""
    channel: object = ""
    fba: object = ""
    freight: object = ""
    note: object = ""
    pack_per_ctn: object = ""
    src_r: int = 0
    in_scope: bool = False
    is_tablecloth: bool = False
    is_separator: bool = False
    changes: list[str] = field(default_factory=list)


def parse_freight(val):
    s = str(val).strip() if val != "" else ""
    if not s:
        return "", None
    if re.match(r"^[\d.]+$", s):
        return s, float(s)
    if re.match(r"^[\d.]+\+[\d.]+$", s):
        return s, sum(float(x) for x in s.split("+"))
    return s, None


def is_tablecloth_spec(spec: str) -> bool:
    s = str(spec).strip()
    if not s:
        return False
    if any(k in s for k in NON_TABLECLOTH):
        return False
    if "桌布" in s:
        return True
    if re.match(r"^(90|110|150|180)\s*G", s, re.I):
        return True
    if re.match(r"^(90|110|150|180)G", s, re.I):
        return True
    return False


def in_scope(month_carry: str, give: str, spec: str) -> bool:
    if "2026" in str(month_carry):
        return True
    g = str(give)
    if re.search(r"C26[0-9]{2,}", g):
        return True
    if "2026" in g:
        return True
    return False


def extract_gsm_spec(spec: str) -> tuple[str, int | None]:
    s = str(spec).strip()
    if not s:
        return s, None
    lines = s.split("\n")
    head, tail = lines[0].strip(), "\n".join(lines[1:]).strip()

    def _head(h: str):
        for pat in (
            r"^(90|110|150|180)\s*G\s*(.+)$",
            r"^(90|110|150|180)G(.+)$",
            r"^(90|110|150|180)克(.+)$",
        ):
            m = re.match(pat, h, re.I)
            if m:
                return m.group(2).strip(), int(m.group(1))
        return h, None

    head, gsm = _head(head)
    out = head if not tail else f"{head}\n{tail}"
    return out, gsm


def spec_to_strips(spec: str) -> str:
    """桌布-6 -> 6；保留非桌布原文。"""
    s = str(spec).strip()
    if not s:
        return s
    m = re.search(r"桌布-(\d+)", s)
    if m:
        return m.group(1)
    m2 = re.match(r"^(\d+)$", s)
    if m2:
        return s
    return s


def norm_color_suffix(rest: str) -> str:
    r = str(rest).strip()
    for a, c in sorted(COLOR_ALIASES.items(), key=lambda x: -len(x[0])):
        if a.lower() in r.lower():
            return c
    return r


def normalize_tablecloth_size(size: str) -> tuple[str, bool]:
    """仅桌布尺寸简写；返回 (new_size, changed)."""
    s = str(size).strip()
    if not s:
        return s, False
    orig = s

    if re.match(r"^90\s*圆", s):
        color = re.sub(r"^90\s*圆\s*", "", s).strip()
        ns = "90圆" + norm_color_suffix(color)
        return ns, ns != orig

    if re.match(r"^60\s*圆", s):
        color = re.sub(r"^60\s*圆\s*", "", s).strip()
        ns = "60圆" + norm_color_suffix(color)
        return ns, ns != orig

    m = re.match(r"^60\s*[\*x×]\s*(\d+)\s*(.*)$", s, re.I)
    if m:
        ns = f"{m.group(1)}{norm_color_suffix(m.group(2))}"
        return ns, ns != orig

    m = re.match(r"^(\d+)\s*(.*)$", s)
    if m and m.group(1) in ("84", "102", "126", "120"):
        ns = f"{m.group(1)}{norm_color_suffix(m.group(2))}"
        return ns, ns != orig

    # 102象牙白 等
    for alias in ("象牙白", "象牙", "lory", "Ivory", "ivory"):
        if alias.lower() in s.lower():
            ns = re.sub(alias, "米白", s, flags=re.I)
            ns = norm_color_suffix(ns) if ns == s else ns
            if re.match(r"^\d+", ns):
                m = re.match(r"^(\d+)(.*)$", ns)
                if m:
                    ns = f"{m.group(1)}{norm_color_suffix(m.group(2))}"
            return ns, ns != orig

    return s, False


def is_niuku(channel: str, freight_raw: str) -> bool:
    ch, fr = str(channel).strip(), str(freight_raw).strip()
    return any(k in ch for k in NIUKU_KW) or any(k in fr for k in ("纽酷", "纽台"))


def read_src_rows() -> list[RowOut]:
    sh = xlrd.open_workbook(str(SRC), formatting_info=True).sheet_by_index(0)
    month_carry = ""
    out: list[RowOut] = []
    last_spec_by_give: dict[str, str] = {}

    for r in range(2, sh.nrows):
        old = [sh.cell_value(r, c) for c in range(min(11, sh.ncols))]
        if not any(str(x).strip() for x in old):
            out.append(RowOut(src_r=r + 1, is_separator=True))
            continue

        month = old[0] if str(old[0]).strip() else month_carry
        if str(old[0]).strip():
            month_carry = str(old[0]).strip()

        give = old[2]
        spec_raw = str(old[3]).strip()
        give_key = str(give).strip()

        if spec_raw:
            last_spec_by_give[give_key] = spec_raw
        effective_spec = spec_raw or last_spec_by_give.get(give_key, "")
        tbl = is_tablecloth_spec(effective_spec)
        scoped = in_scope(month_carry, give_key, effective_spec)

        row = RowOut(
            month=old[0],
            create=old[1],
            give=give,
            spec=old[3],
            size=old[4],
            cost=old[5],
            cartons=old[6],
            channel=old[7],
            fba=old[8],
            freight=old[9],
            note=old[10] if len(old) > 10 else "",
            src_r=r + 1,
            in_scope=scoped,
            is_tablecloth=tbl,
        )

        if scoped and tbl and spec_raw:
            body, gsm = extract_gsm_spec(spec_raw)
            strips = spec_to_strips(body)
            if gsm is not None:
                row.gsm = gsm
            if strips != spec_raw:
                row.spec = strips
                row.changes.append(f"spec {spec_raw!r}->{strips!r}")
            ns, chg = normalize_tablecloth_size(str(old[4]))
            if chg:
                row.size = ns
                row.changes.append(f"size {old[4]!r}->{ns!r}")

        if scoped:
            ch = str(row.channel).strip()
            fr_s, fr_n = parse_freight(row.freight)
            if not ch and fr_s and fr_n is None and any(k in fr_s for k in CARRIERS):
                row.channel = fr_s
                row.freight = ""
                row.changes.append(f"channel<-freight {fr_s}")
            if is_niuku(ch or str(row.channel), fr_s):
                row.freight = 0
                if "freight->0" not in "".join(row.changes):
                    row.changes.append("freight->0 niuku")

        out.append(row)
    return out


def is_separator_row(row: RowOut) -> bool:
    if row.is_separator:
        return True
    return not any(
        str(getattr(row, k)).strip()
        for k in ("give", "spec", "size", "cartons", "fba", "freight", "channel")
    ) and not str(row.month).strip()


def compute_merges(rows: list[RowOut], start_row: int = 2) -> list[tuple]:
    """Return list of (r1,r2,c1,c2,value,style,is_sep)."""
    merges: list[tuple] = []
    n = len(rows)
    if not n:
        return merges

    def rv(i: int) -> RowOut:
        return rows[i]

    # month separators (pair rows)
    i = 0
    while i < n:
        if is_separator_row(rv(i)):
            j = i
            while j < n and is_separator_row(rv(j)):
                j += 1
            if j - i >= 1:
                merges.append((start_row + i, start_row + j - 1, 0, NUM_COLS - 1, "", STY_SEP, True))
            i = j
            continue
        i += 1

    # month column
    i = 0
    while i < n:
        if is_separator_row(rv(i)):
            i += 1
            continue
        m = str(rv(i).month).strip()
        if not m:
            i += 1
            continue
        j = i + 1
        while j < n and not str(rv(j).month).strip() and not is_separator_row(rv(j)):
            j += 1
        if j - i > 1:
            merges.append((start_row + i, start_row + j - 1, COL_MONTH, COL_MONTH, m, STY_CELL, False))
        i = j

    # batch blocks by give
    i = 0
    while i < n:
        if is_separator_row(rv(i)):
            i += 1
            continue
        g = str(rv(i).give).strip()
        if not g:
            i += 1
            continue
        j = i + 1
        while j < n:
            if is_separator_row(rv(j)):
                break
            gj = str(rv(j).give).strip()
            if gj:
                break
            j += 1
        end = j
        if end - 1 > i:
            for col, key in (
                (COL_GIVE, "give"),
                (COL_FBA, "fba"),
                (COL_FREIGHT, "freight"),
                (COL_CHANNEL, "channel"),
            ):
                val = getattr(rv(i), key)
                sty = STY_WRAP if col in (COL_GIVE, COL_FBA) else STY_CELL
                merges.append((start_row + i, start_row + end - 1, col, col, val, sty, False))

        p = i
        while p < end:
            sp = str(rv(p).spec).strip()
            gsm = rv(p).gsm
            q = p + 1
            while q < end:
                if str(rv(q).spec).strip():
                    break
                q += 1
            if q - p > 1 and sp:
                merges.append((start_row + p, start_row + q - 1, COL_SPEC, COL_SPEC, sp, STY_CELL, False))
                if gsm != "":
                    merges.append((start_row + p, start_row + q - 1, COL_GSM, COL_GSM, gsm, STY_CELL, False))
            p = q if q > p else p + 1
        i = end

    return merges


def write_sheet(rows: list[RowOut]) -> xlwt.Workbook:
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Sheet1")

    ws.write(0, COL_MONTH, "月份", STY_CELL)
    ws.write(0, COL_CREATE, "创建日期", STY_CELL)
    ws.write(0, COL_GSM, "克重", STY_CELL)
    ws.write(0, COL_GIVE, "给货日期", STY_CELL)
    ws.write(0, COL_SPEC, "发货产品", STY_CELL)
    ws.write(1, COL_SPEC, "规格", STY_CELL)
    ws.write(1, COL_SIZE, "尺寸", STY_CELL)
    ws.write(1, COL_COST, "成本", STY_CELL)
    ws.write(0, COL_CARTONS, "箱数", STY_CELL)
    ws.write(0, COL_CHANNEL, "渠道", STY_CELL)
    ws.write(0, COL_FBA, "FBA单号", STY_CELL)
    ws.write(0, COL_FREIGHT, "运费", STY_CELL)
    ws.write(
        0,
        COL_NOTE,
        "备注----畅选美国站货件授权日期为2025.7.14，追溯授权前90天，也就是4.14号之前创建的货件都不能通发货单提取成本运费，要通过期初成本计算",
        STY_CELL,
    )
    ws.write(0, COL_PACK_PER_CTN, "包/箱", STY_CELL)

    merges = compute_merges(rows)
    covered: set[tuple[int, int]] = set()
    for r1, r2, c1, c2, _val, _sty, _sep in merges:
        for rr in range(r1, r2 + 1):
            for cc in range(c1, c2 + 1):
                covered.add((rr, cc))

    start = 2
    for i, row in enumerate(rows):
        r = start + i
        if row.is_separator:
            continue
        vals = [
            row.month, row.create, row.gsm, row.give, row.spec, row.size,
            row.cost, row.cartons, row.channel, row.fba, row.freight,
            row.note, row.pack_per_ctn,
        ]
        for c, v in enumerate(vals):
            if (r, c) in covered:
                continue
            sty = STY_WRAP if c in (COL_GIVE, COL_FBA) else STY_CELL
            ws.write(r, c, v, sty)

    for r1, r2, c1, c2, val, sty, _sep in merges:
        if r1 == r2 and c1 == c2:
            ws.write(r1, c1, val, sty)
        else:
            ws.write_merge(r1, r2, c1, c2, val, sty)

    return wb


def cross_check(rows: list[RowOut]) -> dict:
    issues = []
    for row in rows:
        spec = str(row.spec)
        size = str(row.size)
        if any(k in spec for k in NON_TABLECLOTH) and ("60圆" in size or size == "60圆"):
            issues.append({
                "type": "non_tablecloth_round",
                "r": row.src_r,
                "spec": spec,
                "size": size,
                "msg": "非桌布尺寸被写成60圆",
            })
        if row.in_scope and row.is_tablecloth and row.changes:
            pass
        if row.in_scope and is_niuku(str(row.channel), str(row.freight)) and row.freight not in (0, 0.0, "0"):
            fr, fn = parse_freight(row.freight)
            if fn not in (0, None):
                issues.append({
                    "type": "niuku_nonzero_freight",
                    "r": row.src_r,
                    "give": row.give,
                    "freight": row.freight,
                })
    return {
        "issues": issues,
        "scoped_rows": sum(1 for r in rows if r.in_scope),
        "tablecloth_scoped": sum(1 for r in rows if r.in_scope and r.is_tablecloth),
        "changed_rows": [r for r in rows if r.changes],
    }


def main():
    if not SRC.exists():
        raise SystemExit(f"missing backup {SRC}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if OUT.exists():
        shutil.copy2(OUT, INBOX / f"_bak_before_v2_rebuild_{ts}.xls")

    rows = read_src_rows()
    report = cross_check(rows)
    report_path = DRAFT / f"_ship_stats_clean_v2_report_{ts}.json"
    report_path.write_text(
        json.dumps(
            {
                **report,
                "changed_rows": [
                    {"src_r": r.src_r, "give": r.give, "spec": r.spec, "size": r.size, "changes": r.changes}
                    for r in rows if r.changes
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if report["issues"]:
        print("BLOCKERS:", len(report["issues"]))
        for x in report["issues"]:
            print(x)
        raise SystemExit("cross-check failed; not writing OUT")

    wb = write_sheet(rows)
    tmp = INBOX / f"_tmp_write_v2_{ts}.xls"
    wb.save(str(tmp))
    shutil.copy2(tmp, OUT)

    print(f"source: {SRC.name}")
    print(f"out: {OUT}")
    print(f"report: {report_path}")
    print(f"scoped: {report['scoped_rows']} tablecloth_scoped: {report['tablecloth_scoped']}")
    print(f"changed: {len([r for r in rows if r.changes])}")


if __name__ == "__main__":
    main()
