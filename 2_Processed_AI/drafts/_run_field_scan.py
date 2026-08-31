# -*- coding: utf-8 -*-
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
ORDER = ROOT / r"1_Input_Raw\Shipments\EF-C26079-C04-36460  桌布-2026.7.10\订单表\EF-C26079-C04-36460  桌布-2026.7.10.xls"
OUT_ORDER = ROOT / r"2_Processed_AI\drafts\_field_scan_order_C26079.md"
OUT_OUTBOUND = ROOT / r"2_Processed_AI\drafts\_field_scan_outbound_samples.md"
OUTBOUND_CANDIDATES = [
    ROOT / r"1_Input_Raw\Shipments\C04-2615-U_C04_20260624_TBD\出货表\C04-2615-U-2026.6.24.xlsx",
    ROOT / r"1_Input_Raw\Shipments\EF-C26037-C07_C07_20260517_400CTN\出货表\C07-2604-U-2026.5.17.xlsx",
]

DETAIL_MARKERS = re.compile(
    r"装箱明细|FNSKU|产品标签|条数/包|条数\s*/\s*包|fnsku",
    re.I,
)
SUMMARY_MARKERS = re.compile(r"尺寸|颜色|规格|合计|汇总|总条数|箱数", re.I)


def cell_str(v):
    if v is None:
        return ""
    if isinstance(v, float):
        if v == int(v):
            return str(int(v))
        return str(v)
    return str(v).strip()


def load_workbook(path):
    path = Path(path)
    if path.suffix.lower() == ".xls":
        import xlrd
        book = xlrd.open_workbook(str(path), formatting_info=False)
        sheets = []
        for si in range(book.nsheets):
            sh = book.sheet_by_index(si)
            rows = []
            for r in range(sh.nrows):
                row = []
                for c in range(sh.ncols):
                    row.append(sh.cell_value(r, c))
                rows.append(row)
            sheets.append({"name": sh.name, "rows": rows})
        return sheets
    import openpyxl
    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    sheets = []
    for name in wb.sheetnames:
        ws = wb[name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
        sheets.append({"name": name, "rows": rows})
    wb.close()
    return sheets


def trim_rows(rows, max_rows=80):
    if not rows:
        return []
    max_col = 0
    out = []
    for i, row in enumerate(rows[:max_rows]):
        vals = [cell_str(v) for v in row]
        while vals and vals[-1] == "":
            vals.pop()
        if vals:
            max_col = max(max_col, len(vals))
        out.append(vals)
    # pad for display
    for i, vals in enumerate(out):
        if len(vals) < max_col:
            out[i] = vals + [""] * (max_col - len(vals))
    return out, max_col


def grid_markdown(rows, max_rows=80):
    trimmed, max_col = trim_rows(rows, max_rows)
    if not trimmed:
        return "_（无数据）_\n"
    lines = []
    lines.append(f"行数展示: {len(trimmed)}（列宽至 {max_col}）\n")
    for ri, vals in enumerate(trimmed, start=1):
        parts = [f"R{ri}C{c+1}={v}" for c, v in enumerate(vals) if v != ""]
        if parts:
            lines.append(" | ".join(parts))
    return "\n".join(lines) + "\n"


def row_text(row):
    return " ".join(cell_str(v) for v in row if cell_str(v))


def find_section_boundaries(rows):
    """Return (upper_end_row_1based, lower_start_row_1based, marker_line)."""
    marker_rows = []
    for i, row in enumerate(rows):
        t = row_text(row)
        if DETAIL_MARKERS.search(t):
            marker_rows.append((i + 1, t[:120]))
    if marker_rows:
        start = marker_rows[0][0]
        return start - 1, start, marker_rows
    # fallback: first row with FNSKU-like token in any cell
    for i, row in enumerate(rows):
        for v in row:
            s = cell_str(v)
            if re.match(r"^X[A-Z0-9]{9,}$", s, re.I):
                return i, i + 1, [(i + 1, "FNSKU-like cell")]
    return None, None, []


def extract_meta(rows):
    meta = []
    for i, row in enumerate(rows[:25]):
        t = row_text(row)
        if not t:
            continue
        if any(k in t for k in ("订单", "合同", "日期", "公司", "品牌", "合计", "总", "EF-", "C04", "C07", "WIGENIUS", "Dressmaker", "畅选", "易尚")):
            meta.append({"row": i + 1, "text": t[:200]})
    return meta


def guess_data_rows(rows, start_1, end_1):
    """Extract dict rows from a section using header row heuristics."""
    if not start_1 or not end_1:
        return []
    section = rows[start_1 - 1 : end_1]
    if not section:
        return []
    header_idx = 0
    for i, row in enumerate(section[:15]):
        t = row_text(row)
        if SUMMARY_MARKERS.search(t) or DETAIL_MARKERS.search(t):
            header_idx = i
            break
    hdr = [cell_str(v) for v in section[header_idx]]
    records = []
    for row in section[header_idx + 1 :]:
        vals = [cell_str(v) for v in row]
        if not any(vals):
            continue
        if row_text(row).startswith("合计") or "总计" in row_text(row):
            continue
        rec = {}
        for j, h in enumerate(hdr):
            if h and j < len(vals) and vals[j]:
                rec[h] = vals[j]
        if not rec:
            # positional fallback
            nonempty = [v for v in vals if v]
            if len(nonempty) >= 2:
                rec["_cells"] = nonempty
        if rec:
            records.append(rec)
        if len(records) > 500:
            break
    return records


def size_color_from_rec(rec):
    keys = list(rec.keys())
    size = color = None
    for k, v in rec.items():
        if k.startswith("_"):
            continue
        kl = k.lower()
        if "尺寸" in k or "规格" in k or "size" in kl:
            size = v
        if "颜色" in k or "color" in kl:
            color = v
    if not size or not color:
        cells = rec.get("_cells") or [rec[k] for k in keys if not k.startswith("_")]
        if len(cells) >= 2:
            size = size or cells[0]
            color = color or cells[1]
    return size, color


def analyze_order():
    sheets = load_workbook(ORDER)
    md = []
    md.append("# 订单字段扫描 — EF-C26079-C04-36460\n")
    md.append(f"源文件: `{ORDER}`\n")
    md.append("## 1. 工作表名称\n")
    for s in sheets:
        md.append(f"- {s['name']}")
    md.append("")

    all_upper = []
    all_lower = []
    upper_sku = set()
    lower_lines = 0
    sizes = set()
    colors = set()
    total_strips = None

    for s in sheets:
        rows = s["rows"]
        md.append(f"## 2. 工作表 `{s['name']}` — 单元格网格\n")
        md.append(grid_markdown(rows, 80))

        upper_end, lower_start, markers = find_section_boundaries(rows)
        md.append(f"### 3. 上下半区边界（`{s['name']}`）\n")
        if markers:
            md.append("明细区标记行：\n")
            for r, t in markers:
                md.append(f"- 第 {r} 行: {t}")
        if upper_end and lower_start:
            md.append(f"\n**上半汇总区**: 约第 1–{upper_end} 行\n")
            md.append(f"**下半明细区**: 约第 {lower_start} 行起至表末\n")
        else:
            md.append("\n未能自动识别明细区标记；见上方网格人工对照。\n")

        md.append(f"### 4. 元数据 / 页眉字段（`{s['name']}`）\n")
        for m in extract_meta(rows):
            md.append(f"- R{m['row']}: {m['text']}")
        md.append("")

        if upper_end:
            upper_recs = guess_data_rows(rows, 1, upper_end)
            lower_recs = guess_data_rows(rows, lower_start, len(rows))
            all_upper.extend(upper_recs)
            all_lower.extend(lower_recs)
            for rec in upper_recs:
                sz, co = size_color_from_rec(rec)
                if sz and co:
                    upper_sku.add((sz, co))
                    sizes.add(sz)
                    colors.add(co)
            for rec in lower_recs:
                lower_lines += 1
                sz, co = size_color_from_rec(rec)
                if sz:
                    sizes.add(sz)
                if co:
                    colors.add(co)

            md.append(f"### 5. 上半汇总抽取（{len(upper_recs)} 行）\n")
            for rec in upper_recs[:40]:
                md.append(f"- {json.dumps(rec, ensure_ascii=False)}")
            if len(upper_recs) > 40:
                md.append(f"- … 另有 {len(upper_recs)-40} 行")
            md.append("")
            md.append(f"### 6. 下半明细抽取（{len(lower_recs)} 行）\n")
            for rec in lower_recs[:40]:
                md.append(f"- {json.dumps(rec, ensure_ascii=False)}")
            if len(lower_recs) > 40:
                md.append(f"- … 另有 {len(lower_recs)-40} 行")
            md.append("")

    # totals from meta rows last sheet
    for s in sheets:
        for row in s["rows"][:30]:
            t = row_text(row)
            m = re.search(r"(\d+)\s*条", t)
            if m and ("总" in t or "合计" in t):
                total_strips = m.group(1)

    md.append("## 7. 汇总统计\n")
    md.append(f"- 上半汇总 SKU（尺寸+颜色）: **{len(upper_sku)}**\n")
    md.append(f"- 下半明细行数: **{lower_lines}**\n")
    md.append(f"- 唯一尺寸数: {len(sizes)} — {sorted(sizes)[:30]}{'…' if len(sizes)>30 else ''}\n")
    md.append(f"- 唯一颜色数: {len(colors)} — {sorted(colors)[:30]}{'…' if len(colors)>30 else ''}\n")
    if total_strips:
        md.append(f"- 页眉/合计可读总条数: **{total_strips}**\n")

    OUT_ORDER.parent.mkdir(parents=True, exist_ok=True)
    OUT_ORDER.write_text("\n".join(md), encoding="utf-8")
    return {
        "upper_end": upper_end,
        "lower_start": lower_start,
        "upper_sku": len(upper_sku),
        "lower_lines": lower_lines,
        "meta_count": sum(len(extract_meta(s["rows"])) for s in sheets),
    }


def analyze_outbound_sample(path, max_sample_rows=10):
    path = Path(path)
    if not path.exists():
        return f"文件不存在: {path}\n"
    sheets = load_workbook(path)
    md = []
    md.append(f"\n---\n\n## 样本: `{path.name}`\n")
    md.append(f"完整路径: `{path}`\n")
    md.append("### 工作表\n")
    for sn in [x["name"] for x in sheets]:
        md.append(f"- {sn}")
    for s in sheets:
        rows = s["rows"]
        md.append(f"\n### `{s['name']}` 结构网格（前 40 行）\n")
        md.append(grid_markdown(rows, 40))
        # header-like cells in first 15 rows
        md.append("### 页眉/列标题类非空单元格（前 15 行）\n")
        header_cells = []
        for ri, row in enumerate(rows[:15], start=1):
            for ci, v in enumerate(row, start=1):
                sv = cell_str(v)
                if sv:
                    header_cells.append(f"R{ri}C{ci}={sv}")
        md.append("\n".join(header_cells[:80]))
        md.append("\n\n### 数据区样例行（启发式：跳过前 10 行后的前 10 条非空行）\n")
        sample = []
        for row in rows[10:]:
            if any(cell_str(v) for v in row):
                sample.append(row)
            if len(sample) >= max_sample_rows:
                break
        for ri, row in enumerate(sample, start=1):
            md.append(" | ".join(f"C{i+1}={cell_str(v)}" for i, v in enumerate(row) if cell_str(v)))
        # column fill heuristic on sample+next rows
        md.append("\n\n### 列填充 vs 静态（基于样例 20 行）\n")
        body = []
        for row in rows[10:30]:
            if any(cell_str(v) for v in row):
                body.append(row)
        if body:
            ncols = max(len(r) for r in body)
            for c in range(ncols):
                vals = [cell_str(r[c]) if c < len(r) else "" for r in body]
                nonempty = [v for v in vals if v]
                if not nonempty:
                    continue
                uniq = set(nonempty)
                kind = "静态/重复" if len(uniq) <= 2 and len(nonempty) >= 3 else "逐行变化"
                md.append(f"- 列 C{c+1}: {kind} — 样例: {list(uniq)[:5]}")
    return "\n".join(md)


def main():
    stats = analyze_order()
    md = ["# 出货表样本字段扫描\n", f"扫描范围: Shipments / 01_Order_Outbound / Templates / 3_Output_Final\n"]
    picked = []
    for p in OUTBOUND_CANDIDATES:
        if p.exists():
            picked.append(p)
        if len(picked) >= 2:
            break
    if len(picked) < 2:
        # fallback search
        for base in [ROOT / "1_Input_Raw" / "Shipments", ROOT / "1_Input_Raw" / "01_Order_Outbound"]:
            for f in base.rglob("*"):
                if f.suffix.lower() in (".xls", ".xlsx") and re.search(r"-U-", f.name):
                    if f not in picked:
                        picked.append(f)
                if len(picked) >= 2:
                    break
    md.append("## 选用的样本（最多 2 个）\n")
    for p in picked:
        md.append(f"- `{p}`")
    for p in picked[:2]:
        md.append(analyze_outbound_sample(p))
    OUT_OUTBOUND.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"order_stats": stats, "outbound": [str(p) for p in picked[:2]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
