# -*- coding: utf-8 -*-
"""Inspect 发货统计.xls merged cells + XF via xlrd formatting_info=True."""
from __future__ import annotations

import json
from pathlib import Path

import xlrd

INBOX = Path(r"D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\00_Master_Reference\发货统计\_inbox")
OUT = Path(r"D:\.cursor\Cursor-projects\AutoExport\2_Processed_AI\drafts\_inspect_ship_stats_merges_20260826.json")

HORZ = {
    0: "GENERAL",
    1: "LEFT",
    2: "CENTER",
    3: "RIGHT",
    4: "FILL",
    5: "JUSTIFY",
    6: "CENTER_ACROSS",
    7: "DISTRIBUTED",
}
VERT = {0: "TOP", 1: "CENTER", 2: "BOTTOM", 3: "JUSTIFY", 4: "DISTRIBUTED"}
BORD = {
    0: "NONE",
    1: "THIN",
    2: "MEDIUM",
    3: "DASHED",
    4: "DOTTED",
    5: "THICK",
    6: "DOUBLE",
    7: "HAIR",
    8: "MEDIUM_DASHED",
    9: "DASH_DOT",
    10: "MEDIUM_DASH_DOT",
    11: "DASH_DOT_DOT",
    12: "MEDIUM_DASH_DOT_DOT",
    13: "SLANTED_DASH_DOT",
}


def cell_txt(sh, r, c):
    if c >= sh.ncols:
        return ""
    v = sh.cell_value(r, c)
    t = sh.cell_type(r, c)
    if t == xlrd.XL_CELL_NUMBER:
        if float(v).is_integer():
            return str(int(v))
        return str(v)
    if v is None:
        return ""
    return str(v)


def xf_info(book, sh, r, c):
    try:
        xf_idx = sh.cell_xf_index(r, c)
        xf = book.xf_list[xf_idx]
        a = xf.alignment
        b = xf.border
        return {
            "xf_idx": xf_idx,
            "horz": HORZ.get(a.hor_align, a.hor_align),
            "vert": VERT.get(a.vert_align, a.vert_align),
            "wrap": bool(a.text_wrapped),
            "border": {
                "left": BORD.get(b.left_line_style, b.left_line_style),
                "right": BORD.get(b.right_line_style, b.right_line_style),
                "top": BORD.get(b.top_line_style, b.top_line_style),
                "bottom": BORD.get(b.bottom_line_style, b.bottom_line_style),
            },
        }
    except Exception as e:  # noqa: BLE001
        return {"err": str(e)}


def merges_for_row(merges, r0):
    out = []
    for rlo, rhi, clo, chi in merges:
        if rlo <= r0 < rhi:
            out.append(
                {
                    "rlo": rlo,
                    "rhi": rhi,
                    "clo": clo,
                    "chi": chi,
                    "span_rows": rhi - rlo,
                    "span_cols": chi - clo,
                }
            )
    return sorted(out, key=lambda x: (x["clo"], x["rlo"]))


def inspect_file(path: Path, targets=("C26064", "C26052", "C26079", "C26080")):
    book = xlrd.open_workbook(str(path), formatting_info=True)
    sh = book.sheet_by_index(0)
    hdr = [cell_txt(sh, 0, c) for c in range(min(sh.ncols, 12))]
    merges = list(sh.merged_cells)

    hits = []
    for r in range(sh.nrows):
        for c in range(min(sh.ncols, 12)):
            t = cell_txt(sh, r, c)
            for tg in targets:
                if tg in t:
                    hits.append({"row": r, "col": c, "target": tg, "text": t})

    batches = {}
    for tg in ("C26064", "C26052"):
        rows = [h["row"] for h in hits if h["target"] == tg and h["col"] == 2]
        if not rows:
            # also search any col
            rows = [h["row"] for h in hits if h["target"] == tg]
        if not rows:
            batches[tg] = None
            continue
        r0 = min(rows)
        # find 给货日期 (col 2) merge covering r0
        date_merge = None
        for rlo, rhi, clo, chi in merges:
            if clo <= 2 < chi and rlo <= r0 < rhi:
                date_merge = (rlo, rhi, clo, chi)
                break
        if date_merge:
            rlo, rhi, clo, chi = date_merge
            detail_end = rhi
        else:
            rlo, rhi = r0, r0 + 1
            detail_end = min(sh.nrows, r0 + 12)

        col_merges = {}
        for cname, cidx in (("给货日期", 2), ("规格", 3), ("尺寸", 4), ("箱数", 5), ("FBA单号", 8), ("运费", 9)):
            found = []
            for mrlo, mrhi, mclo, mchi in merges:
                if mclo <= cidx < mchi and mrlo <= r0 < mrhi:
                    found.append(
                        {
                            "rlo": mrlo,
                            "rhi": mrhi,
                            "clo": mclo,
                            "chi": mchi,
                            "span_rows": mrhi - mrlo,
                            "span_cols": mchi - mclo,
                            "top_text": cell_txt(sh, mrlo, mclo),
                        }
                    )
            col_merges[cname] = found

        detail = []
        for r in range(rlo if date_merge else r0, detail_end):
            row = {
                "row": r,
                "vals": [cell_txt(sh, r, c) for c in range(min(11, sh.ncols))],
            }
            if r == (rlo if date_merge else r0):
                row["xf"] = {str(c): xf_info(book, sh, r, c) for c in (2, 3, 4, 5, 8, 9)}
            detail.append(row)

        # all merges overlapping batch rows
        batch_merges = []
        for mrlo, mrhi, mclo, mchi in merges:
            if not (mrhi <= rlo or mrlo >= detail_end):
                batch_merges.append(
                    {
                        "rlo": mrlo,
                        "rhi": mrhi,
                        "clo": mclo,
                        "chi": mchi,
                        "span_rows": mrhi - mrlo,
                        "span_cols": mchi - mclo,
                        "top_text": cell_txt(sh, mrlo, mclo)[:200],
                    }
                )
        batch_merges.sort(key=lambda x: (x["clo"], x["rlo"]))

        batches[tg] = {
            "start_row": r0,
            "date_merge": {
                "rlo": rlo,
                "rhi": rhi,
                "clo": clo if date_merge else 2,
                "chi": chi if date_merge else 3,
                "span_rows": rhi - rlo,
            }
            if date_merge
            else None,
            "给货日期_text": cell_txt(sh, rlo if date_merge else r0, 2),
            "col_merges": col_merges,
            "all_batch_merges": batch_merges,
            "detail_rows": detail,
            "fba_all_in_one_merged_cell": bool(
                col_merges.get("FBA单号")
                and col_merges["FBA单号"][0]["span_rows"] >= (rhi - rlo if date_merge else 1)
                and "\n" in (col_merges["FBA单号"][0].get("top_text") or "")
                or (
                    col_merges.get("FBA单号")
                    and col_merges["FBA单号"][0]["span_rows"] == (rhi - rlo if date_merge else 1)
                )
            ),
        }

    # sample merges around rows 290-305 regardless
    around = []
    for mrlo, mrhi, mclo, mchi in merges:
        if mrlo < 310 and mrhi > 285:
            around.append(
                {
                    "rlo": mrlo,
                    "rhi": mrhi,
                    "clo": mclo,
                    "chi": mchi,
                    "span_rows": mrhi - mrlo,
                    "span_cols": mchi - mclo,
                    "top_text": cell_txt(sh, mrlo, mclo)[:150],
                }
            )
    around.sort(key=lambda x: (x["rlo"], x["clo"]))

    # also dump a few header XF
    header_xf = {str(c): xf_info(book, sh, 0, c) for c in range(min(11, sh.ncols))}

    return {
        "path": str(path),
        "sheet": sh.name,
        "nrows": sh.nrows,
        "ncols": sh.ncols,
        "header": hdr,
        "total_merges": len(merges),
        "hits": hits[:40],
        "batches": batches,
        "merges_around_285_310": around,
        "header_xf": header_xf,
    }


def main():
    report = {}
    for name in ("2026年发货记录.xls", "_bak_before_jul_aug_20260826.xls"):
        p = INBOX / name
        print("OPEN", p, "exists", p.exists())
        if not p.exists():
            report[name] = {"error": "missing"}
            continue
        report[name] = inspect_file(p)
        print(
            name,
            "nrows",
            report[name]["nrows"],
            "merges",
            report[name]["total_merges"],
            "hits",
            len(report[name]["hits"]),
        )
        for tg, b in report[name]["batches"].items():
            if not b:
                print(" ", tg, "NOT FOUND")
                continue
            print(
                " ",
                tg,
                "start",
                b["start_row"],
                "date_merge",
                b["date_merge"],
                "date_text",
                repr(b["给货日期_text"])[:80],
            )
            for cn, ms in b["col_merges"].items():
                if ms:
                    m = ms[0]
                    print(
                        "   ",
                        cn,
                        f"rows {m['rlo']}:{m['rhi']} cols {m['clo']}:{m['chi']} span_r={m['span_rows']}",
                        "text",
                        repr(m["top_text"])[:60],
                    )

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
