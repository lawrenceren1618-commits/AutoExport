# -*- coding: utf-8 -*-
"""Parse FBA外箱贴 → 仓头 / 箱规统计 / 拆单 batch 草稿.

Uses pypdf text extraction when available (FBA号形如 FBA19JT39521U000001 → 货件号 FBA19JT39521).

When folder label packs disagree with page marks (page_mark_split in JSON),
also run Scripts/16_split_mixed_carton_spec_folders.py --apply so PDFs are
physically split and renamed to match each spec folder (settled rule).

Usage:
  python Scripts/08_parse_fba_carton_labels.py --project "<Shipments/...>" \\
    --tracking-json drafts/tracking.json --write-batch
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore

FBA_CARTON_RE = re.compile(r"(FBA[0-9A-Z]{8,12})U\d{5,}", re.I)
FBA_PLAIN_RE = re.compile(r"\b(FBA[0-9A-Z]{8,12})\b", re.I)
TOTAL_CARTON_RE = re.compile(r"共\s*(\d+)\s*个纸箱")
COLOR_MAP = {
    "白": "白",
    "白色": "白",
    "黑": "黑",
    "黑色": "黑",
    "蓝": "蓝",
    "蓝色": "蓝",
    "米白": "米白",
    "米白色": "米白",
    "象牙": "米白",
    "象牙色": "米白",
    "象牙白": "米白",
    "象牙白色": "米白",
    "Ivory": "米白",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def _norm_size(name: str) -> str:
    if re.search(r"90\s*inches?\s*round", name, re.I) or re.search(r"90inches?\s*Round", name):
        return "90 inch round"
    t2 = name.replace("＊", "X").replace("×", "X").replace("*", "X").replace("ｘ", "X")
    m = re.search(r"(60|70)\s*[Xx]\s*(84|102|120|126)", t2)
    if m:
        a, b = m.group(1), m.group(2)
        if a == "70" and b == "120":
            return "70X120inch"
        return f"{a}X{b}inch"
    return name


def _parse_spec(folder_name: str) -> dict:
    cm = re.search(r"-(\d+)箱", folder_name)
    cartons = int(cm.group(1)) if cm else None
    pm = re.search(r"(\d+)\s*packs?", folder_name, re.I)
    packs = int(pm.group(1)) if pm else None
    cm2 = re.match(r"^(\D+?)\s+\d", folder_name)
    color_raw = cm2.group(1).strip() if cm2 else ""
    color = COLOR_MAP.get(color_raw, COLOR_MAP.get(color_raw.replace("色", ""), color_raw))
    return {
        "raw": folder_name,
        "color": color,
        "size": _norm_size(folder_name),
        "strips_per_pack": packs,
        "qty_cartons": cartons,
    }


def _unique_pdfs(wh: Path) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for f in wh.rglob("*"):
        if not f.is_file() or f.suffix.lower() != ".pdf":
            continue
        key = str(f.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _shipment_id_from_token(tok: str) -> str:
    tok = tok.upper()
    m = FBA_CARTON_RE.match(tok)
    if m:
        return m.group(1).upper()
    return tok.upper()


def _page_pack_marks(folder: Path) -> dict[int, int]:
    """Count pages marked like '126-6' / '126-10' / '120-6' inside PDFs.

    Returns {strips_per_pack: page_count}. Empty if pypdf missing or no marks.
    """
    if not PdfReader:
        return {}
    counts: Counter[int] = Counter()
    for f in folder.iterdir():
        if not f.is_file() or f.suffix.lower() != ".pdf":
            continue
        try:
            reader = PdfReader(str(f))
        except Exception:
            continue
        for page in reader.pages:
            t = page.extract_text() or ""
            for m in re.finditer(r"\b(?:84|102|120|126|90)-(2|6|10)\b", t):
                counts[int(m.group(1))] += 1
    return dict(counts)


def _enrich_spec(parsed: dict, rate: dict, carton_source: str) -> dict:
    key = (parsed["size"], parsed["color"], parsed["strips_per_pack"])
    if key in rate:
        r = rate[key]
        parsed["fnsku"] = r.get("fnsku")
        parsed["packs_per_carton"] = r.get("packs_per_carton")
        parsed["qty_strips"] = (parsed["qty_cartons"] or 0) * int(r.get("packs_per_carton") or 0) * int(
            parsed["strips_per_pack"] or 0
        )
    else:
        parsed["fnsku"] = None
        parsed["packs_per_carton"] = None
        parsed["qty_strips"] = None
    parsed["carton_source"] = carton_source
    return parsed


def _extract_wh_from_pdfs(pdfs: list[Path]) -> dict:
    hits: Counter[str] = Counter()
    pages = 0
    total_from_text: list[int] = []
    address_lines: list[str] = []
    sample = ""
    if not PdfReader:
        return {
            "fba_hits": {},
            "page_count": 0,
            "address_sample": "",
            "carton_total_text": None,
            "notes": ["pypdf 未安装，无法从 PDF 抽 FBA 号"],
        }
    for f in pdfs:
        try:
            reader = PdfReader(str(f))
            pages += len(reader.pages)
            for i, page in enumerate(reader.pages):
                t = page.extract_text() or ""
                if not sample and t.strip():
                    sample = t[:500]
                if i == 0:
                    for line in t.splitlines():
                        line = line.strip()
                        if not line or line in address_lines or len(address_lines) >= 8:
                            continue
                        if any(
                            k in line
                            for k in (
                                "Amazon",
                                "Ave",
                                "AVE",
                                "Rd",
                                "RD",
                                "DR",
                                "Township",
                                "CA ",
                                "PA ",
                                "IL ",
                                "NC ",
                                "AZ ",
                                "美国",
                            )
                        ):
                            address_lines.append(line)
                for m in FBA_CARTON_RE.finditer(t):
                    hits[m.group(1).upper()] += 1
                for m in TOTAL_CARTON_RE.findall(t):
                    total_from_text.append(int(m))
        except Exception:
            continue
    carton_total_text = (
        max(set(total_from_text), key=total_from_text.count) if total_from_text else None
    )
    return {
        "fba_hits": dict(hits.most_common(5)),
        "page_count": pages,
        "address_sample": " | ".join(address_lines[:6]) if address_lines else sample[:240],
        "carton_total_text": carton_total_text,
        "notes": [],
    }


def parse_project(project: Path, tracking: dict[str, str]) -> dict:
    fba_root = project / "FBA外箱贴"
    if not fba_root.is_dir():
        raise FileNotFoundError(f"missing {fba_root}")

    ledger_path = project / "拆单比对" / "split_ledger.json"
    plan_by_fnsku = []
    if ledger_path.is_file():
        led = json.loads(ledger_path.read_text(encoding="utf-8"))
        plan_by_fnsku = led.get("plan", {}).get("by_fnsku", [])

    rate = {
        (r["size"], r["color"], r["strips_per_pack"]): r for r in plan_by_fnsku
    }

    warehouses: list[dict] = []
    for wh in sorted([p for p in fba_root.iterdir() if p.is_dir()], key=lambda p: p.name):
        pdfs = _unique_pdfs(wh)
        meta = _extract_wh_from_pdfs(pdfs)
        ranked = sorted(meta["fba_hits"].items(), key=lambda kv: (-kv[1], kv[0]))
        fba_id = ranked[0][0] if ranked else ""
        for cand, _ in ranked:
            if cand in tracking:
                fba_id = cand
                break

        specs: list[dict] = []
        for d in sorted([p for p in wh.iterdir() if p.is_dir()], key=lambda p: p.name):
            parsed = _parse_spec(d.name)
            n_pdf = len([f for f in d.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"])
            folder_cartons = parsed["qty_cartons"] if parsed["qty_cartons"] is not None else n_pdf
            page_packs = _page_pack_marks(d)
            # 文件夹外标可能误标包规：页内多种 N条装且页数=箱数时，按页拆分
            if len(page_packs) >= 2 and sum(page_packs.values()) == (folder_cartons or 0):
                for spp, n_ctn in sorted(page_packs.items()):
                    row = {
                        "raw": parsed["raw"],
                        "color": parsed["color"],
                        "size": parsed["size"],
                        "strips_per_pack": spp,
                        "qty_cartons": n_ctn,
                        "pdf_files": n_pdf,
                        "folder_label_packs": parsed["strips_per_pack"],
                        "correction": "page_mark_split",
                    }
                    specs.append(_enrich_spec(row, rate, "page_mark_split"))
                continue
            if len(page_packs) == 1:
                only_spp = next(iter(page_packs))
                if parsed["strips_per_pack"] and only_spp != parsed["strips_per_pack"]:
                    parsed["folder_label_packs"] = parsed["strips_per_pack"]
                    parsed["strips_per_pack"] = only_spp
                    parsed["correction"] = "page_mark_override"
                    carton_source = "page_mark_override"
                else:
                    carton_source = "folder_name" if parsed["qty_cartons"] is not None else "pdf_count"
            else:
                carton_source = "folder_name" if parsed["qty_cartons"] is not None else "pdf_count"
            parsed["qty_cartons"] = folder_cartons
            parsed["pdf_files"] = n_pdf
            specs.append(_enrich_spec(parsed, rate, carton_source))

        qty_cartons = sum(s["qty_cartons"] or 0 for s in specs)
        qty_strips = sum(s["qty_strips"] or 0 for s in specs)
        warehouses.append(
            {
                "warehouse_code": wh.name,
                "fba_shipment_id": fba_id,
                "tracking_id": tracking.get(fba_id, ""),
                "fba_hits": dict(ranked[:5]),
                "pdf_count": len(pdfs),
                "page_count": meta["page_count"],
                "qty_cartons": qty_cartons,
                "qty_strips": qty_strips,
                "carton_total_text": meta["carton_total_text"],
                "warehouse_address": meta["address_sample"],
                "specs": specs,
                "notes": meta["notes"],
            }
        )

    # aggregate
    agg_fn: dict[tuple, dict] = {}
    for w in warehouses:
        for s in w["specs"]:
            key = (s["size"], s["color"], s["strips_per_pack"], s.get("fnsku"))
            slot = agg_fn.setdefault(
                key,
                {
                    "size": s["size"],
                    "color": s["color"],
                    "strips_per_pack": s["strips_per_pack"],
                    "fnsku": s.get("fnsku"),
                    "packs_per_carton": s.get("packs_per_carton"),
                    "qty_cartons": 0,
                    "qty_strips": 0,
                },
            )
            slot["qty_cartons"] += s["qty_cartons"] or 0
            slot["qty_strips"] += s["qty_strips"] or 0

    by_fnsku = list(agg_fn.values())
    by_sc: dict[tuple, dict] = {}
    for r in by_fnsku:
        k = (r["size"], r["color"])
        slot = by_sc.setdefault(k, {"size": r["size"], "color": r["color"], "qty_strips": 0, "qty_cartons": 0})
        slot["qty_strips"] += r["qty_strips"] or 0
        slot["qty_cartons"] += r["qty_cartons"] or 0

    plan_keys = {(r["size"], r["color"], r["strips_per_pack"]) for r in plan_by_fnsku}
    fba_keys = {(r["size"], r["color"], r["strips_per_pack"]) for r in by_fnsku}
    missing_specs = sorted(plan_keys - fba_keys)
    extra_delta = []
    for r in by_fnsku:
        key = (r["size"], r["color"], r["strips_per_pack"])
        plan = rate.get(key)
        if plan and r["qty_cartons"] != plan.get("qty_cartons"):
            extra_delta.append(
                {
                    "size": r["size"],
                    "color": r["color"],
                    "strips_per_pack": r["strips_per_pack"],
                    "fnsku": r.get("fnsku"),
                    "fba_cartons": r["qty_cartons"],
                    "plan_cartons": plan.get("qty_cartons"),
                    "delta": r["qty_cartons"] - int(plan.get("qty_cartons") or 0),
                }
            )

    result = {
        "version": "1.0",
        "parsed_at": _now(),
        "project": str(project),
        "order_code": "EF-C26079-C04-36460",
        "split_leg_id": "C26079-A",
        "warehouses": warehouses,
        "tracking_provided": tracking,
        "total_cartons": sum(w["qty_cartons"] for w in warehouses),
        "total_strips": sum(w["qty_strips"] for w in warehouses),
        "total_pdfs": sum(w["pdf_count"] for w in warehouses),
        "total_pages": sum(w["page_count"] for w in warehouses),
        "by_fnsku": by_fnsku,
        "by_size_color": list(by_sc.values()),
        "plan_compare": {
            "plan_cartons": sum(int(r.get("qty_cartons") or 0) for r in plan_by_fnsku),
            "plan_strips": sum(int(r.get("qty_strips") or 0) for r in plan_by_fnsku),
            "missing_specs_in_fba": [
                {"size": a, "color": b, "strips_per_pack": c} for a, b, c in missing_specs
            ],
            "carton_deltas_vs_plan": extra_delta,
        },
        "warnings": [],
    }
    result["warnings"] = _warnings(result)
    return result


def _warnings(result: dict) -> list[str]:
    notes: list[str] = []
    mapped = {w["fba_shipment_id"] for w in result["warehouses"] if w["fba_shipment_id"]}
    for fba, tr in result["tracking_provided"].items():
        if fba not in mapped:
            notes.append(f"追踪码已提供但未识别到 FBA: {fba} → {tr}")
    for w in result["warehouses"]:
        if not w["fba_shipment_id"]:
            notes.append(f"仓 {w['warehouse_code']} 未识别 FBA 号")
        elif not w["tracking_id"]:
            notes.append(f"仓 {w['warehouse_code']} FBA={w['fba_shipment_id']} 无匹配追踪码")
        if w.get("carton_total_text") and w["carton_total_text"] != w["qty_cartons"]:
            notes.append(
                f"仓 {w['warehouse_code']}: 文件夹箱数={w['qty_cartons']} ≠ PDF文案共N箱={w['carton_total_text']}"
            )
        if w.get("page_count") and w["page_count"] != w["qty_cartons"]:
            notes.append(
                f"仓 {w['warehouse_code']}: 页数={w['page_count']} vs 文件夹箱数={w['qty_cartons']}"
            )
    pc = result["plan_compare"]
    if pc["missing_specs_in_fba"]:
        notes.append(
            "外箱贴缺少计划规格: "
            + ", ".join(
                f"{x['size']}/{x['color']}/{x['strips_per_pack']}条装"
                for x in pc["missing_specs_in_fba"]
            )
        )
    for d in pc["carton_deltas_vs_plan"]:
        notes.append(
            f"箱数与计划不符: {d['size']}/{d['color']}/{d['strips_per_pack']}条 "
            f"FBA={d['fba_cartons']} 计划={d['plan_cartons']} Δ={d['delta']}"
        )
    if result["total_cartons"] != pc["plan_cartons"]:
        notes.append(
            f"总箱数 FBA={result['total_cartons']} 计划={pc['plan_cartons']} "
            f"Δ={result['total_cartons'] - pc['plan_cartons']}"
        )
    return notes


def build_batch(result: dict, project: Path) -> dict:
    return {
        "batch_no": 1,
        "split_leg_id": result["split_leg_id"],
        "ship_date": "2026-07-31",
        "outbound_short": "C04-2616",
        "note": "从 FBA外箱贴 解析；追踪码已填；60X126米白 文件夹外标误为6pack，已按页内126-6/126-10拆分为30+40箱",
        "shipped_strips": result["total_strips"],
        "shipped_cartons": result["total_cartons"],
        "by_size_color": result["by_size_color"],
        "by_fnsku": [
            {
                "size": r["size"],
                "color": r["color"],
                "strips_per_pack": r["strips_per_pack"],
                "fnsku": r.get("fnsku"),
                "packs_per_carton": r.get("packs_per_carton"),
                "qty_strips": r["qty_strips"],
                "qty_cartons": r["qty_cartons"],
            }
            for r in result["by_fnsku"]
        ],
        "warehouses": [
            {
                "warehouse_code": w["warehouse_code"],
                "fba_shipment_id": w["fba_shipment_id"],
                "tracking_id": w["tracking_id"],
                "warehouse_address": w.get("warehouse_address"),
                "cartons": w["qty_cartons"],
                "strips": w["qty_strips"],
            }
            for w in result["warehouses"]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--tracking-json")
    ap.add_argument("--out")
    ap.add_argument("--write-batch", action="store_true")
    args = ap.parse_args()
    project = Path(args.project)
    tracking: dict[str, str] = {}
    if args.tracking_json:
        tracking = json.loads(Path(args.tracking_json).read_text(encoding="utf-8"))
    result = parse_project(project, tracking)
    out = (
        Path(args.out)
        if args.out
        else ROOT / "2_Processed_AI" / "drafts" / "C26079-A_fba_recognize.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(
        f"total_cartons={result['total_cartons']} strips={result['total_strips']} "
        f"pdfs={result['total_pdfs']} pages={result['total_pages']}"
    )
    for w in result["warehouses"]:
        print(
            f"{w['warehouse_code']}: cartons={w['qty_cartons']} strips={w['qty_strips']} "
            f"FBA={w['fba_shipment_id']} track={w['tracking_id']}"
        )
    for n in result["warnings"]:
        print(f"WARN: {n}")

    if args.write_batch:
        batch = build_batch(result, project)
        batch_path = project / "拆单比对" / "C26079-A_manifest.json"
        batch_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote batch {batch_path}")
        headers_path = ROOT / "2_Processed_AI" / "drafts" / "C26079-A_warehouse_headers.json"
        headers_path.write_text(
            json.dumps(
                {
                    "order_code": result["order_code"],
                    "split_leg_id": result["split_leg_id"],
                    "rows": batch["warehouses"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote headers {headers_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
