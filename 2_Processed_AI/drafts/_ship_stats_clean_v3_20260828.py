# -*- coding: utf-8 -*-
"""
发货记录 v3：列序=给货日期|克重|规格；发货产品合并(规格/尺寸/成本)；
仅 2026+ 桌布归一；票号 C26xxx 归入给货日期；C26079=90克。
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
STY_FBA = xlwt.easyxf(
    "align: wrap on, vert centre, horiz left;"
    "borders: left thin, right thin, top thin, bottom thin"
)
STY_SEP = xlwt.easyxf(
    "pattern: pattern solid, fore_colour pale_blue;"
    "borders: left thin, right thin, top thin, bottom thin;"
    "align: wrap off, vert centre, horiz centre"
)

# A月份 B创建 C给货 D克重 E规格 F尺寸 G成本 H箱数 I渠道 JFBA K运费 L备注 M包/箱
COL_MONTH, COL_CREATE = 0, 1
COL_GIVE, COL_GSM = 2, 3
COL_SPEC, COL_SIZE, COL_COST = 4, 5, 6
COL_CARTONS, COL_CHANNEL = 7, 8
COL_FBA, COL_FREIGHT, COL_NOTE = 9, 10, 11
COL_PACK_PER_CTN = 12
NUM_COLS = 13

# xlwt col width: units = 1/256 character width
COL_WIDTHS = [1800, 2200, 4800, 1400, 1200, 2200, 1800, 1400, 2400, 4200, 2200, 9000, 1400]

NON_TABLECLOTH = ("秸秆", "阁", "桌旗", "假发", "楼梯", "游戏", "餐垫", "头套", "混合")
COLOR_ALIASES = {"ivory": "米白", "lory": "米白", "象牙白": "米白", "象牙": "米白"}
NIUKU_KW = ("纽酷", "纽台", "SEND", "后台扣款")
CARRIERS = ("物易通", "纽酷", "纽台", "远方", "威旭", "德邦", "飞特")
KNOWN_BATCH_GSM = {"C26079": 90, "C26080": 90}


@dataclass
class RowOut:
    month: object = ""
    create: object = ""
    give: object = ""
    gsm: object = ""
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


def in_scope(month_carry: str, give: str) -> bool:
    if "2026" in str(month_carry):
        return True
    if re.search(r"C26[0-9]{2,}", str(give)):
        return True
    if "2026" in str(give):
        return True
    return False


def parse_gsm_head(head: str) -> tuple[str, int | None]:
    for pat in (
        r"^(90|110|150|180)\s*G\s*(.+)$",
        r"^(90|110|150|180)G(.+)$",
        r"^(90|110|150|180)克(.+)$",
    ):
        m = re.match(pat, head.strip(), re.I)
        if m:
            return m.group(2).strip(), int(m.group(1))
    return head.strip(), None


def promote_ticket_to_give(spec: str, give: str) -> tuple[str, str]:
    """规格内 C26xxx 行 → 给货日期（对齐 C26079-A 写法）。"""
    lines = str(spec).split("\n")
    head = lines[0]
    give_s = str(give).strip()
    for line in lines[1:]:
        m = re.search(r"(C26\d{2,})", line)
        if m and m.group(1) not in give_s:
            give_s = f"{give_s}\n{m.group(1)}" if give_s else m.group(1)
    return head, give_s


def spec_to_strips(spec_body: str) -> str:
    s = str(spec_body).strip()
    if not s:
        return s
    m = re.search(r"桌布-(\d+)", s)
    if m:
        return m.group(1)
    if re.match(r"^\d+$", s):
        return s
    return s


def norm_color_suffix(rest: str) -> str:
    r = str(rest).strip()
    for a, c in sorted(COLOR_ALIASES.items(), key=lambda x: -len(x[0])):
        if a.lower() in r.lower():
            return c
    return r


def normalize_tablecloth_size(size: str) -> tuple[str, bool]:
    s = str(size).strip()
    if not s:
        return s, False
    orig = s
    if re.match(r"^90\s*圆", s, re.I):
        ns = "90圆" + norm_color_suffix(re.sub(r"^90\s*圆\s*", "", s, flags=re.I).strip())
        return ns, ns != orig
    if re.match(r"^60\s*圆", s, re.I):
        ns = "60圆" + norm_color_suffix(re.sub(r"^60\s*圆\s*", "", s, flags=re.I).strip())
        return ns, ns != orig
    m = re.match(r"^60\s*[\*x×]\s*(\d+)\s*(.*)$", s, re.I)
    if m:
        ns = f"{m.group(1)}{norm_color_suffix(m.group(2))}"
        return ns, ns != orig
    m = re.match(r"^(\d+)\s*(.*)$", s)
    if m and m.group(1) in ("84", "102", "126", "120"):
        ns = f"{m.group(1)}{norm_color_suffix(m.group(2))}"
        return ns, ns != orig
    # 120Ivory / 102lory 无空格
    m = re.match(r"^(\d+)([A-Za-z\u4e00-\u9fff].+)$", s)
    if m and m.group(1) in ("84", "102", "126", "120"):
        ns = f"{m.group(1)}{norm_color_suffix(m.group(2))}"
        return ns, ns != orig
    for alias in ("象牙白", "象牙", "lory", "Ivory", "ivory"):
        if alias.lower() in s.lower():
            ns = re.sub(alias, "米白", s, flags=re.I)
            m2 = re.match(r"^(\d+)\s*(.*)$", ns.strip())
            if m2 and m2.group(1) in ("84", "102", "126", "120"):
                ns = f"{m2.group(1)}{norm_color_suffix(m2.group(2))}"
            else:
                m3 = re.match(r"^(\d+)(.+)$", ns.strip())
                if m3 and m3.group(1) in ("84", "102", "126", "120"):
                    ns = f"{m3.group(1)}{norm_color_suffix(m3.group(2))}"
            return ns, ns != orig
    return s, False


def should_normalize_size(month_carry: str, scoped: bool, effective_spec: str, size: str) -> bool:
    if any(k in str(effective_spec) for k in NON_TABLECLOTH):
        return False
    size_scope = scoped or month_carry in ("6", "6.0")
    if not size_scope or not str(size).strip():
        return False
    if is_tablecloth_spec(effective_spec):
        return True
    # 6 月块：无规格续行但尺寸形如桌布
    if month_carry in ("6", "6.0"):
        return bool(re.search(r"lory|ivory|60\s*[\*x×]|^\d+圆", str(size), re.I))
    return False


def is_niuku(channel: str, freight_raw: str) -> bool:
    ch, fr = str(channel).strip(), str(freight_raw).strip()
    return any(k in ch for k in NIUKU_KW) or any(k in fr for k in ("纽酷", "纽台"))


def read_src_rows() -> list[RowOut]:
    sh = xlrd.open_workbook(str(SRC), formatting_info=True).sheet_by_index(0)
    month_carry = ""
    out: list[RowOut] = []
    last_spec_by_give: dict[str, str] = {}
    group_spec_carry = ""
    batch_scoped = False

    for r in range(2, sh.nrows):
        old = [sh.cell_value(r, c) for c in range(min(11, sh.ncols))]
        if not any(str(x).strip() for x in old):
            out.append(RowOut(src_r=r + 1, is_separator=True))
            continue

        if str(old[0]).strip():
            month_carry = str(old[0]).strip()

        give = old[2]
        spec_raw = str(old[3]).strip()
        give_key = str(give).strip()
        if spec_raw:
            last_spec_by_give[give_key] = spec_raw
            if is_tablecloth_spec(spec_raw):
                group_spec_carry = spec_raw
            else:
                group_spec_carry = ""
        effective_spec = spec_raw or group_spec_carry or last_spec_by_give.get(give_key, "")
        tbl = is_tablecloth_spec(effective_spec)
        if str(give).strip():
            batch_scoped = in_scope(month_carry, give_key)
        scoped = batch_scoped

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
            head, new_give = promote_ticket_to_give(spec_raw, give)
            if new_give != str(give).strip():
                row.give = new_give
                row.changes.append(f"give<-ticket {new_give!r}")
            body, gsm = parse_gsm_head(head)
            strips = spec_to_strips(body)
            if gsm is not None:
                row.gsm = gsm
            if strips != spec_raw:
                row.spec = strips
                row.changes.append(f"spec {spec_raw!r}->{strips!r}")

        if should_normalize_size(month_carry, scoped, effective_spec, str(old[4])):
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

    apply_batch_gsm(out)
    return out


def apply_batch_gsm(rows: list[RowOut]) -> None:
    """批次内已知票号补克重（如 C26079=90）。"""
    i = 0
    n = len(rows)
    while i < n:
        if is_separator_row(rows[i]):
            i += 1
            continue
        g0 = str(rows[i].give).strip()
        if not g0:
            i += 1
            continue
        j = i + 1
        while j < n:
            if is_separator_row(rows[j]):
                break
            if str(rows[j].give).strip():
                break
            j += 1
        blob = " ".join(str(rows[k].give) for k in range(i, j))
        for ticket, gsm in KNOWN_BATCH_GSM.items():
            if ticket in blob:
                for k in range(i, j):
                    if rows[k].is_tablecloth and str(rows[k].gsm).strip() == "":
                        rows[k].gsm = gsm
                        rows[k].changes.append(f"gsm={gsm} ({ticket})")
        i = j


def is_separator_row(row: RowOut) -> bool:
    if row.is_separator:
        return True
    return not any(
        str(getattr(row, k)).strip()
        for k in ("give", "spec", "size", "cartons", "fba", "freight", "channel")
    ) and not str(row.month).strip()


def compute_merges(rows: list[RowOut], start_row: int = 2) -> list[tuple]:
    merges: list[tuple] = []
    n = len(rows)
    if not n:
        return merges

    def rv(i: int) -> RowOut:
        return rows[i]

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
            if str(rv(j).give).strip():
                break
            j += 1
        end = j
        if end - 1 > i:
            for col, key, sty in (
                (COL_GIVE, "give", STY_WRAP),
                (COL_FBA, "fba", STY_FBA),
                (COL_FREIGHT, "freight", STY_CELL),
                (COL_CHANNEL, "channel", STY_CELL),
            ):
                merges.append((start_row + i, start_row + end - 1, col, col, getattr(rv(i), key), sty, False))

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


def line_count(*texts: object) -> int:
    m = 1
    for t in texts:
        s = str(t).strip()
        if s:
            m = max(m, s.count("\n") + 1)
    return m


def write_sheet(rows: list[RowOut]) -> xlwt.Workbook:
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Sheet1")

    for c, w in enumerate(COL_WIDTHS):
        ws.col(c).width = w

    ws.write_merge(0, 1, COL_MONTH, COL_MONTH, "月份", STY_CELL)
    ws.write_merge(0, 1, COL_CREATE, COL_CREATE, "创建日期", STY_CELL)
    ws.write_merge(0, 1, COL_GIVE, COL_GIVE, "给货日期", STY_CELL)
    ws.write_merge(0, 1, COL_GSM, COL_GSM, "克重", STY_CELL)
    ws.write_merge(0, 0, COL_SPEC, COL_COST, "发货产品", STY_CELL)
    ws.write(1, COL_SPEC, "规格", STY_CELL)
    ws.write(1, COL_SIZE, "尺寸", STY_CELL)
    ws.write(1, COL_COST, "成本", STY_CELL)
    ws.write_merge(0, 1, COL_CARTONS, COL_CARTONS, "箱数", STY_CELL)
    ws.write_merge(0, 1, COL_CHANNEL, COL_CHANNEL, "渠道", STY_CELL)
    ws.write_merge(0, 1, COL_FBA, COL_FBA, "FBA单号", STY_CELL)
    ws.write_merge(0, 1, COL_FREIGHT, COL_FREIGHT, "运费", STY_CELL)
    ws.write_merge(0, 1, COL_PACK_PER_CTN, COL_PACK_PER_CTN, "包/箱", STY_CELL)
    ws.write(
        0,
        COL_NOTE,
        "备注----畅选美国站货件授权日期为2025.7.14，追溯授权前90天，也就是4.14号之前创建的货件都不能通发货单提取成本运费，要通过期初成本计算",
        STY_WRAP,
    )

    merges = compute_merges(rows)
    covered: set[tuple[int, int]] = set()
    for r1, r2, c1, c2, _v, _s, _sep in merges:
        for rr in range(r1, r2 + 1):
            for cc in range(c1, c2 + 1):
                covered.add((rr, cc))

    start = 2
    for i, row in enumerate(rows):
        r = start + i
        if row.is_separator:
            ws.row(r).height = 360
            continue
        vals = [
            row.month, row.create, row.give, row.gsm, row.spec, row.size,
            row.cost, row.cartons, row.channel, row.fba, row.freight,
            row.note, row.pack_per_ctn,
        ]
        for c, v in enumerate(vals):
            if (r, c) in covered:
                continue
            if c == COL_FBA:
                sty = STY_FBA
            elif c in (COL_GIVE, COL_NOTE):
                sty = STY_WRAP
            else:
                sty = STY_CELL
            ws.write(r, c, v, sty)
        ws.row(r).height = max(320, 320 * line_count(row.give, row.fba))

    for r1, r2, c1, c2, val, sty, _sep in merges:
        if r1 == r2 and c1 == c2:
            ws.write(r1, c1, val, sty)
        else:
            ws.write_merge(r1, r2, c1, c2, val, sty)
        if c1 == COL_FBA:
            h = max(320, 320 * line_count(val))
            for rr in range(r1, r2 + 1):
                ws.row(rr).height = max(ws.row(rr).height, h // max(1, r2 - r1 + 1))

    ws.row(0).height = 420
    ws.row(1).height = 360

    # 冻结窗格：第三行 B 列（保留 2 行表头 + A 列月份）
    ws.set_panes_frozen(True)
    ws.set_horz_split_pos(2)
    ws.set_vert_split_pos(1)
    ws.set_remove_splits(True)

    return wb


def cross_check(rows: list[RowOut]) -> dict:
    issues = []
    tickets = []
    for row in rows:
        blob = f"{row.give} {row.spec} {row.fba}"
        if "C26032" in blob:
            tickets.append({"src_r": row.src_r, "give": row.give, "spec": row.spec})
        spec, size = str(row.spec), str(row.size)
        if any(k in spec for k in NON_TABLECLOTH) and "60圆" in size:
            issues.append({"type": "non_tablecloth_round", "r": row.src_r, "spec": spec, "size": size})
        if "C26079" in blob and row.is_tablecloth and str(row.gsm).strip() not in ("90", "90.0"):
            if str(row.spec).strip().isdigit():
                issues.append({"type": "c26079_gsm", "r": row.src_r, "gsm": row.gsm, "spec": row.spec})
    if not tickets:
        issues.append({"type": "missing_C26032", "msg": "给货日期/规格中未找到 C26032"})
    return {
        "issues": issues,
        "c26032": tickets,
        "scoped_rows": sum(1 for r in rows if r.in_scope),
        "changed_rows": len([r for r in rows if r.changes]),
    }


def main():
    if not SRC.exists():
        raise SystemExit(f"missing backup {SRC}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if OUT.exists():
        shutil.copy2(OUT, INBOX / f"_bak_before_v3_{ts}.xls")

    rows = read_src_rows()
    report = cross_check(rows)
    report_path = DRAFT / f"_ship_stats_clean_v3_report_{ts}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if any(i.get("type") != "niuku" for i in report["issues"]):
        blockers = [i for i in report["issues"] if i["type"] not in ("niuku_nonzero_freight",)]
        if blockers:
            print("BLOCKERS:", blockers)
            raise SystemExit("cross-check failed")

    wb = write_sheet(rows)
    tmp = INBOX / f"_tmp_write_v3_{ts}.xls"
    wb.save(str(tmp))
    shutil.copy2(tmp, OUT)

    print(f"out: {OUT}")
    print(f"report: {report_path}")
    print(f"C26032: {report['c26032']}")
    print(f"changed: {report['changed_rows']}")


if __name__ == "__main__":
    main()
