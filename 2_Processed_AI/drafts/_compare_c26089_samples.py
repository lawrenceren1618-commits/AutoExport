# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
OUT = ROOT / "2_Processed_AI" / "drafts" / "_c26089_sample_compare.json"

SAMPLES = [
    ROOT / r"1_Input_Raw\Shipments\EF-C26079-C04-36460  桌布-2026.7.10\订单表\EF-C26079-C04-36460  桌布-2026.7.10.xls",
    ROOT / r"1_Input_Raw\01_Order_Outbound\EF-C26079-C04-36460  桌布-2026.7.10.xls",
    ROOT / r"1_Input_Raw\Shipments\EF-C26080-C07-11590_C07_20260731_13590\订单表\EF-C26080-C07- 11590 桌布-7.10改.xls",
    ROOT / r"1_Input_Raw\Shipments\EF-C26080-C07-11590_C07_20260731_13590\订单表\EF-C26068-C07-2000  桌布-2026.6.3 (3).xls",
]


def dump_xls(path: Path) -> dict:
    info: dict = {"path": str(path), "name": path.name, "exists": path.exists()}
    if not path.exists():
        return info
    info["size"] = path.stat().st_size
    # try xlrd first for .xls
    try:
        import xlrd

        book = xlrd.open_workbook(str(path), formatting_info=False)
        sh = book.sheet_by_index(0)
        cells = {}
        for r in range(min(sh.nrows, 45)):
            for c in range(min(sh.ncols, 12)):
                v = sh.cell_value(r, c)
                if v is None or (isinstance(v, str) and not v.strip()):
                    continue
                # excel A1
                col = ""
                n = c
                while True:
                    col = chr(n % 26 + 65) + col
                    n = n // 26 - 1
                    if n < 0:
                        break
                cells[f"{col}{r+1}"] = v
        info["engine"] = "xlrd"
        info["nrows"] = sh.nrows
        info["ncols"] = sh.ncols
        info["cells"] = cells
        return info
    except Exception as e:
        info["xlrd_error"] = str(e)

    try:
        import pandas as pd

        dfs = pd.read_excel(path, header=None, sheet_name=0)
        cells = {}
        for r in range(min(len(dfs), 45)):
            for c in range(min(dfs.shape[1], 12)):
                v = dfs.iat[r, c]
                if pd.isna(v):
                    continue
                if isinstance(v, str) and not v.strip():
                    continue
                col = ""
                n = c
                while True:
                    col = chr(n % 26 + 65) + col
                    n = n // 26 - 1
                    if n < 0:
                        break
                cells[f"{col}{r+1}"] = v
        info["engine"] = "pandas"
        info["cells"] = cells
        return info
    except Exception as e:
        info["pandas_error"] = str(e)

    try:
        from openpyxl import load_workbook

        wb = load_workbook(path)
        ws = wb.active
        cells = {}
        for row in ws.iter_rows(min_row=1, max_row=45, max_col=12):
            for cell in row:
                if cell.value is not None and str(cell.value).strip() != "":
                    cells[cell.coordinate] = cell.value
        info["engine"] = "openpyxl"
        info["cells"] = cells
        info["merges"] = [str(m) for m in ws.merged_cells.ranges]
        return info
    except Exception as e:
        info["openpyxl_error"] = str(e)
    return info


def main() -> None:
    result = {"samples": [dump_xls(p) for p in SAMPLES]}
    # also check blank template
    blank = ROOT / "Templates" / "order_blank_zh.xlsx"
    if blank.exists():
        from openpyxl import load_workbook

        wb = load_workbook(blank)
        ws = wb.active
        cells = {
            c.coordinate: c.value
            for row in ws.iter_rows(min_row=1, max_row=20, max_col=12)
            for c in row
            if c.value is not None and str(c.value).strip() != ""
        }
        result["blank_template"] = {
            "path": str(blank),
            "cells": cells,
            "merges": [str(m) for m in ws.merged_cells.ranges],
        }
    else:
        result["blank_template"] = {"exists": False}

    # assemble packs_per_carton path
    import sys

    sys.path.insert(0, str(ROOT / "Scripts"))
    from m1.assemble import assemble_order_lines, load_settled_products

    assembled = assemble_order_lines(
        entity_code="C07",
        order_code="EF-C26089-C07-40000",
        order_date="2026-08-10",
        qty_plan=[
            {
                "size": "60X102inch",
                "color": "白色",
                "qty_strips": 40000,
                "qty_cartons": 1000,
                "strips_per_pack": 10,
                "strips_per_carton": 40,
                "fnsku": "X004SJV9UF",
            }
        ],
        settled=load_settled_products(),
        master_rows=[],
        confirmed_resolutions={},
    )
    result["assemble_line_keys"] = list(assembled["lines"][0].keys()) if assembled.get("lines") else []
    result["assemble_line0"] = assembled.get("lines", [None])[0]
    result["assemble_pending"] = assembled.get("pending")

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("wrote", OUT)
    for s in result["samples"]:
        print("---", s.get("name"), "engine=", s.get("engine"), "exists=", s.get("exists"))
        cells = s.get("cells") or {}
        for k in ["A6", "B6", "C6", "D6", "E6", "F6", "G6", "A7", "A8", "A9", "B9", "A1", "D1"]:
            if k in cells:
                print(f"  {k}: {cells[k]!r}")
        # print first 25 cells
        for i, (k, v) in enumerate(cells.items()):
            if i >= 30:
                break
            print(f"  {k}: {v!r}")


if __name__ == "__main__":
    main()
