# -*- coding: utf-8 -*-
"""17_reorg_carton_by_spec.py

After 10_carton_label_ingest + promote: group flat _p#### pages under
FBA外箱贴/{channel}/{warehouse}/ into per-spec folders and merge one multipage PDF.

AWD folder: {color}_{size}_{N}条装/
PDF name:   AWD_{wh}_{folder}_{cartons}箱.pdf
Inbound (*入库贴*) stays at warehouse root.
Flat pages → FBA外箱贴/_flat_pages/{channel}/{warehouse}/flat_*/
正式仓夹只留一规格一多页 PDF 与入库贴。散页不进贴标包，只供页数交叉核对。

Usage:
  python Scripts/17_reorg_carton_by_spec.py --project "1_Input_Raw/Shipments/..."
  python Scripts/17_reorg_carton_by_spec.py --project "..." --channel AWD --warehouse IUTJ

Doc: Templates/Carton_Label_Channels.md §2.1
Rule: .cursor/rules/shipment-pipeline-order.mdc (P-CARTON)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
FNSKU_RE = re.compile(r"FNSKU:\s*([A-Z0-9]+)", re.I)
PAGE_RE = re.compile(r"_p(\d{4})_", re.I)


def size_token(size: str) -> str:
    s = (size or "").replace(" ", "").replace("×", "X").replace("*", "X")
    if "90" in s and "round" in s.lower():
        return "90inchround"
    m = re.match(r"(\d+)[Xx](\d+)inch", s, re.I)
    if m:
        return f"{m.group(1)}X{m.group(2)}inch"
    return s


def folder_name(color: str, size: str, spp: int) -> str:
    return f"{color}_{size_token(size)}_{int(spp)}条装"


def fnsku_map(proj: Path) -> dict[str, dict]:
    pj = json.loads((proj / "PROJECT.json").read_text(encoding="utf-8"))
    m: dict[str, dict] = {}
    for ln in pj.get("lines") or []:
        fn = str(ln.get("fnsku") or "").upper().strip()
        if not fn:
            continue
        m[fn] = {
            "color": ln.get("color"),
            "size": ln.get("size"),
            "strips_per_pack": int(ln.get("strips_per_pack") or 0),
            "qty_cartons": int(ln.get("qty_cartons") or 0),
            "fnsku": fn,
        }
    return m


def extract_fnsku(pdf: Path) -> str | None:
    try:
        reader = PdfReader(str(pdf))
        if not reader.pages:
            return None
        text = reader.pages[0].extract_text() or ""
    except Exception:
        return None
    m = FNSKU_RE.search(text)
    return m.group(1).upper() if m else None


def reorganize(proj: Path, channel: str, warehouse: str) -> dict:
    wh_dir = proj / "FBA外箱贴" / channel / warehouse
    item: dict = {"project": proj.name, "path": str(wh_dir), "channel": channel, "warehouse": warehouse}
    if not wh_dir.is_dir():
        item["status"] = "missing_warehouse_dir"
        return item

    fmap = fnsku_map(proj)
    pages = sorted(
        [p for p in wh_dir.glob("*.pdf") if PAGE_RE.search(p.name) or "_p" in p.name.lower()],
        key=lambda p: p.name,
    )
    pages = [p for p in pages if "入库贴" not in p.name]
    item["flat_pages_n"] = len(pages)
    if not pages:
        item["status"] = "no_flat_pages"
        item["dirs"] = [x.name for x in wh_dir.iterdir() if x.is_dir() and not x.name.startswith(".")]
        return item

    groups: dict[str, list[Path]] = defaultdict(list)
    unknown: list[str] = []
    for pdf in pages:
        fn = extract_fnsku(pdf)
        if not fn or fn not in fmap:
            unknown.append(f"{pdf.name}:fnsku={fn}")
            continue
        meta = fmap[fn]
        key = folder_name(meta["color"], meta["size"], meta["strips_per_pack"])
        groups[key].append(pdf)

    item["unknown_n"] = len(unknown)
    item["unknown_sample"] = unknown[:15]
    item["groups"] = {k: len(v) for k, v in groups.items()}
    if unknown:
        item["status"] = "BLOCKED_unknown_pages"
        return item

    mismatches = []
    for key, pdfs in groups.items():
        color, size, spp_part = key.split("_", 2)
        spp = int(re.match(r"(\d+)", spp_part).group(1))
        plan_ctn = None
        for meta in fmap.values():
            if (
                meta["color"] == color
                and size_token(meta["size"]) == size
                and meta["strips_per_pack"] == spp
            ):
                plan_ctn = meta["qty_cartons"]
                break
        if plan_ctn is not None and plan_ctn != len(pdfs):
            mismatches.append({"folder": key, "pages": len(pdfs), "plan_cartons": plan_ctn})
    item["mismatches"] = mismatches
    if mismatches:
        item["status"] = "BLOCKED_carton_count_mismatch"
        return item

    bak = (
        proj
        / "FBA外箱贴"
        / "_flat_pages"
        / channel
        / warehouse
        / f"flat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    bak.mkdir(parents=True, exist_ok=True)
    written = []
    prefix = "AWD" if channel.upper() == "AWD" else channel.upper()
    for key, pdfs in sorted(groups.items()):
        dest_dir = wh_dir / key
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_pdf = dest_dir / f"{prefix}_{warehouse}_{key}_{len(pdfs)}箱.pdf"
        writer = PdfWriter()
        for pdf in sorted(pdfs, key=lambda p: p.name):
            reader = PdfReader(str(pdf))
            for page in reader.pages:
                writer.add_page(page)
            shutil.move(str(pdf), str(bak / pdf.name))
        with out_pdf.open("wb") as f:
            writer.write(f)
        written.append(str(out_pdf.relative_to(proj)))

    item["written"] = written
    item["bak"] = str(bak.relative_to(proj))
    item["status"] = "ok"
    return item


def main() -> int:
    ap = argparse.ArgumentParser(description="Reorg carton pages into per-spec folders")
    ap.add_argument("--project", required=True)
    ap.add_argument("--channel", default="AWD")
    ap.add_argument("--warehouse", default="IUTJ")
    args = ap.parse_args()
    proj = Path(args.project)
    if not proj.is_absolute():
        proj = ROOT / proj
    result = reorganize(proj, args.channel.upper(), args.warehouse.upper())
    out = ROOT / "2_Processed_AI" / "drafts" / f"_reorg_carton_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(out), "status": result.get("status"), "groups": result.get("groups"), "written_n": len(result.get("written") or [])}, ensure_ascii=True))
    return 0 if result.get("status") in ("ok", "no_flat_pages") else 2


if __name__ == "__main__":
    raise SystemExit(main())
