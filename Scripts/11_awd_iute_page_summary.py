# -*- coding: utf-8 -*-
"""Extract AWD carton label fields per page, compare to B pending, stage by SKU folder.

Usage:
  python Scripts/11_awd_iute_page_summary.py --project "<Shipments/...>"
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]

COLOR_NORM = {
    "ivory": "米白",
    "米白": "米白",
    "象牙白": "米白",
    "white": "白",
    "白": "白",
    "白色": "白",
}

B_PENDING = [
    {"size": "60X126inch", "color": "白", "strips_per_pack": 10, "expected_cartons": 50},
    {"size": "70X120inch", "color": "白", "strips_per_pack": 6, "expected_cartons": 50},
    {"size": "70X120inch", "color": "米白", "strips_per_pack": 6, "expected_cartons": 40},
]

BOX_RE = re.compile(r"Box\s+(\d+)\s+of\s+(\d+)", re.I)
SKU_RE = re.compile(
    r"SKU:\s*(.+?)\s+Units:\s*(\d+)",
    re.I | re.S,
)
FNSKU_RE = re.compile(r"FNSKU:\s*(\S+)", re.I)
PO_RE = re.compile(r"PO ID:\s*([^,\n]+)", re.I)
SHIP_RE = re.compile(r"ShipmentID:\s*(\S+)", re.I)
DEST_RE = re.compile(
    r"目的地：\s*(.+?)(?:\n|SSCC:|PO ID:|$)",
    re.S,
)
AWD_DEST_FALLBACK = re.compile(
    r"AWD:\s*(.+?)\|\s*(IUTE[^\n|]+)",
    re.S,
)
PACK_RE = re.compile(r"(\d+)\s*pack", re.I)
SIZE_IN_SKU_RE = re.compile(r"(60|70)\s*[Xx]\s*(102|120|126)", re.I)
COLOR_IN_SKU_RE = re.compile(r"^\s*(Ivory|White|米白|白|象牙白)\b", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def norm_color(raw: str) -> str:
    key = raw.strip().lower()
    for k, v in COLOR_NORM.items():
        if key == k.lower() or raw.strip() == k:
            return v
    if "ivory" in key or "象牙" in raw:
        return "米白"
    if "white" in key or raw.strip() in ("白", "白色"):
        return "白"
    return raw.strip()


def norm_size_from_text(text: str) -> str:
    t = text.replace("×", "X").replace("*", "X").replace("inches", "inch")
    m = SIZE_IN_SKU_RE.search(t)
    if not m:
        return text.strip()
    a, b = m.group(1), m.group(2)
    if a == "70" and b == "120":
        return "70X120inch"
    return f"{a}X{b}inch"


def parse_sku_line(sku_raw: str) -> dict:
    sku_raw = re.sub(r"\s+", " ", sku_raw.replace("\n", " ")).strip()
    cm = COLOR_IN_SKU_RE.match(sku_raw)
    color_raw = cm.group(1) if cm else ""
    color = norm_color(color_raw)
    size = norm_size_from_text(sku_raw)
    pm = PACK_RE.search(sku_raw)
    strips = int(pm.group(1)) if pm else None
    return {
        "sku_line": sku_raw,
        "color": color,
        "size": size,
        "strips_per_pack": strips,
    }


def parse_page_text(text: str, *, source_file: str, page_index: int) -> dict:
    t = text or ""
    box_n = box_total = None
    bm = BOX_RE.search(t)
    if bm:
        box_n, box_total = int(bm.group(1)), int(bm.group(2))

    sku_line = units = None
    sm = SKU_RE.search(t)
    if sm:
        sku_line = re.sub(r"\s+", " ", sm.group(1).replace("\n", " ")).strip()
        units = int(sm.group(2))

    fnsku = None
    fm = FNSKU_RE.search(t)
    if fm:
        fnsku = fm.group(1).upper()

    po_id = PO_RE.search(t)
    shipment_id = SHIP_RE.search(t)
    dest = ""
    dm = DEST_RE.search(t)
    if dm:
        dest = re.sub(r"\s+", " ", dm.group(1).replace("\n", " | ")).strip()
    else:
        am = AWD_DEST_FALLBACK.search(t)
        if am:
            dest = f"{am.group(1).strip()} | {am.group(2).strip()}"

    spec = parse_sku_line(sku_line or "")
    return {
        "source_file": source_file,
        "page_index": page_index,
        "page_number": page_index + 1,
        "box_n": box_n,
        "box_total": box_total,
        "box_label": f"Box {box_n} of {box_total}" if box_n and box_total else None,
        "sku_line": sku_line,
        "product_title": sku_line,
        "fnsku": fnsku,
        "units": units,
        "shipment_id": shipment_id.group(1) if shipment_id else "",
        "po_id": po_id.group(1).strip() if po_id else "",
        "destination_line": dest,
        "color": spec["color"],
        "size": spec["size"],
        "strips_per_pack": spec["strips_per_pack"],
    }


def aggregate(pages: list[dict]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for p in pages:
        key = (p.get("size"), p.get("color"), p.get("strips_per_pack"), p.get("fnsku"))
        if key not in groups:
            groups[key] = {
                "size": p.get("size"),
                "color": p.get("color"),
                "strips_per_pack": p.get("strips_per_pack"),
                "fnsku": p.get("fnsku"),
                "carton_count": 0,
                "box_numbers": [],
                "sku_line_sample": p.get("sku_line"),
            }
        groups[key]["carton_count"] += 1
        if p.get("box_n"):
            groups[key]["box_numbers"].append(p["box_n"])
    out = []
    for g in groups.values():
        g["box_numbers"] = sorted(g["box_numbers"])
        out.append(g)
    out.sort(key=lambda x: (x.get("size") or "", x.get("color") or "", x.get("strips_per_pack") or 0))
    return out


def compare_b_pending(aggregated: list[dict]) -> dict:
    actual_map = {
        (a["size"], a["color"], a["strips_per_pack"]): a for a in aggregated
    }
    rows = []
    mismatches = []
    for exp in B_PENDING:
        key = (exp["size"], exp["color"], exp["strips_per_pack"])
        act = actual_map.get(key)
        actual_n = act["carton_count"] if act else 0
        fnsku = act.get("fnsku") if act else None
        delta = actual_n - exp["expected_cartons"]
        match = delta == 0
        row = {
            **exp,
            "actual_cartons": actual_n,
            "fnsku": fnsku,
            "delta": delta,
            "match": match,
        }
        rows.append(row)
        if not match:
            mismatches.append(row)
    extra_keys = set(actual_map.keys()) - {
        (e["size"], e["color"], e["strips_per_pack"]) for e in B_PENDING
    }
    for key in sorted(extra_keys):
        act = actual_map[key]
        mismatches.append(
            {
                "size": key[0],
                "color": key[1],
                "strips_per_pack": key[2],
                "expected_cartons": 0,
                "actual_cartons": act["carton_count"],
                "fnsku": act.get("fnsku"),
                "delta": act["carton_count"],
                "match": False,
                "note": "unexpected_sku_in_pdf",
            }
        )
    return {"comparison_rows": rows, "mismatches": mismatches, "all_match": len(mismatches) == 0}


def folder_name_for_page(p: dict) -> str:
    n = p.get("strips_per_pack") or "?"
    return f"{p.get('color')}_{p.get('size')}_{n}条装"


def box_pdf_name(p: dict) -> str:
    bn, bt = p.get("box_n"), p.get("box_total")
    fnsku = p.get("fnsku") or "NOFNSKU"
    if bn and bt:
        return f"AWD_Box_{bn:03d}_of_{bt}_{fnsku}.pdf"
    return f"AWD_page_{p.get('page_number', 0):04d}_{fnsku}.pdf"


def find_staged_page(no_wh: Path, page_number: int) -> Path | None:
    pat = f"*_p{page_number:04d}_*.pdf"
    hits = list(no_wh.glob(pat))
    return hits[0] if hits else None


def reorganize_staging(pages: list[dict], no_wh: Path, awd_staging: Path) -> list[dict]:
    iute_root = awd_staging / "IUTE"
    moves: list[dict] = []
    for p in pages:
        src = find_staged_page(no_wh, p["page_number"])
        rel_folder = f"IUTE/{folder_name_for_page(p)}"
        dest_dir = iute_root / folder_name_for_page(p)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / box_pdf_name(p)
        if src and src.is_file():
            shutil.copy2(src, dest)
            action = "copied_from_no_wh"
            src_path = str(src)
        else:
            action = "missing_staged_source"
            src_path = ""
        moves.append(
            {
                "page_number": p["page_number"],
                "source_staged": src_path,
                "dest": str(dest),
                "folder": rel_folder,
                "action": action,
            }
        )
    return moves


def render_md(report: dict) -> str:
    lines = [
        "# C26079-B AWD 外箱贴逐页识别",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 源 PDF：`{report['source_pdf']}`",
        f"- 总页数：{report['page_count']}",
        f"- 落盘：`_recognize/C26079-B_AWD_page_summary.json`",
        f"- 分拣：`_staging/AWD/IUTE/{{color}}_{{size}}_{{N}}条装/`（未 promote 至 `FBA外箱贴/AWD/`）",
        "",
        "## B 待贴对照",
        "",
        "| size | color | strips/pack | 期望箱 | 实际箱 | FNSKU | Δ | OK |",
        "|------|-------|-------------|--------|--------|-------|---|-----|",
    ]
    for r in report["comparison"]["comparison_rows"]:
        ok = "✓" if r["match"] else "✗"
        lines.append(
            f"| {r['size']} | {r['color']} | {r['strips_per_pack']} | "
            f"{r['expected_cartons']} | {r['actual_cartons']} | {r.get('fnsku') or '-'} | "
            f"{r['delta']:+d} | {ok} |"
        )
    lines.append("")
    if report["comparison"]["mismatches"]:
        lines.append("## 差异")
        for m in report["comparison"]["mismatches"]:
            lines.append(f"- {m}")
    else:
        lines.append("## 差异")
        lines.append("- 无：PDF 聚合与 B pending 三项完全一致。")
    lines.append("")
    lines.append("## 聚合（size × color × strips × FNSKU）")
    lines.append("")
    for a in report["aggregated"]:
        lines.append(
            f"- **{a['color']} {a['size']} {a['strips_per_pack']}条装** — "
            f"{a['carton_count']} 箱，FNSKU `{a.get('fnsku')}`，"
            f"箱号 {a['box_numbers'][0]}–{a['box_numbers'][-1]}"
        )
    lines.append("")
    lines.append("## 元数据（首箱）")
    p0 = report["pages"][0] if report["pages"] else {}
    lines.append(f"- PO ID：`{p0.get('po_id', '')}`")
    lines.append(f"- ShipmentID：`{p0.get('shipment_id', '')}`")
    lines.append(f"- 目的地：{p0.get('destination_line', '')[:200]}")
    return "\n".join(lines)


def print_comparison_table(comparison: dict) -> None:
    print("\n=== B pending vs PDF aggregate ===")
    print(f"{'size':<14} {'color':<4} {'pack':>4} {'expect':>6} {'actual':>6} {'FNSKU':<12} {'delta':>5} OK")
    print("-" * 72)
    for r in comparison["comparison_rows"]:
        ok = "YES" if r["match"] else "NO"
        print(
            f"{r['size']:<14} {r['color']:<4} {r['strips_per_pack']:>4} "
            f"{r['expected_cartons']:>6} {r['actual_cartons']:>6} "
            f"{(r.get('fnsku') or '-'):<12} {r['delta']:>+5} {ok}"
        )
    if comparison["mismatches"]:
        print("\nMISMATCHES:")
        for m in comparison["mismatches"]:
            print(" ", m)
    else:
        print("\nAll B pending lines match PDF counts.")


def run(project: Path) -> dict:
    if not PdfReader:
        raise RuntimeError("pypdf required: pip install pypdf")

    fba = project / "FBA外箱贴"
    inbox = fba / "_inbox"
    pdfs = sorted(inbox.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDF in {inbox}")
    source_pdf = pdfs[0]
    for cand in pdfs:
        if "140" in cand.name or "C26078" in cand.name:
            source_pdf = cand
            break

    reader = PdfReader(str(source_pdf))
    pages: list[dict] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(parse_page_text(text, source_file=str(source_pdf), page_index=i))

    aggregated = aggregate(pages)
    comparison = compare_b_pending(aggregated)

    no_wh = fba / "_staging" / "AWD" / "_no_wh"
    awd_staging = fba / "_staging" / "AWD"
    staging_ops = reorganize_staging(pages, no_wh, awd_staging) if no_wh.is_dir() else []

    report = {
        "generated_at": _now(),
        "project": str(project),
        "source_pdf": str(source_pdf),
        "page_count": len(pages),
        "pages": pages,
        "aggregated": aggregated,
        "comparison": comparison,
        "b_pending": B_PENDING,
        "staging": {
            "reorganized_to": str(awd_staging / "IUTE"),
            "inbox_preserved": True,
            "promoted_to_final_awd": False,
            "operations": staging_ops,
            "missing_sources": sum(1 for o in staging_ops if o["action"] != "copied_from_no_wh"),
        },
    }

    recognize = fba / "_recognize"
    recognize.mkdir(parents=True, exist_ok=True)
    out_json = recognize / "C26079-B_AWD_page_summary.json"
    out_md = recognize / "C26079-B_AWD_page_summary.md"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(report), encoding="utf-8")
    report["output_json"] = str(out_json)
    report["output_md"] = str(out_md)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project",
        required=True,
        help="Shipment project folder",
    )
    args = ap.parse_args()
    project = Path(args.project)
    if not project.is_dir():
        print(f"Missing project: {project}", file=sys.stderr)
        return 1
    report = run(project)
    print(f"wrote {report['output_json']}")
    print(f"wrote {report['output_md']}")
    print_comparison_table(report["comparison"])
    print(f"\nStaging: copied {len(report['staging']['operations']) - report['staging']['missing_sources']} "
          f"pages to {report['staging']['reorganized_to']}")
    if report["staging"]["missing_sources"]:
        print(f"WARNING: {report['staging']['missing_sources']} pages missing _no_wh source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
