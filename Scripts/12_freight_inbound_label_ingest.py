# -*- coding: utf-8 -*-
"""Freight inbound label ingest (货代入库贴).

Source: PDF returned by freight forwarder after user sends 下单表.
Flow: recognize → normalize → triple cross-check + page dedupe
      → (pass) merge one multipage PDF per warehouse
      → place under FBA外箱贴/{channel}/{wh}/{channel}_{wh}_入库贴_{N}箱.pdf

See Templates/Freight_Inbound_Label_Pipeline.md.

Usage:
  python Scripts/12_freight_inbound_label_ingest.py --project "<Shipments/...>"
  python Scripts/12_freight_inbound_label_ingest.py --project "..." --apply
  python Scripts/12_freight_inbound_label_ingest.py --project "..." --authority "<..._freight_customs_summary.json>"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = None  # type: ignore
    PdfWriter = None  # type: ignore

FC_SHIPMENT_RE = re.compile(r"\b(FBA[0-9A-Z]{8,12})\b", re.I)
STAR_SHIPMENT_RE = re.compile(r"\b(STAR-[0-9A-Z]+)\b", re.I)
AWD_HINT_RE = re.compile(
    r"\b(AWD|Amazon\s+Warehousing|Warehousing\s*&\s*Distribution|IUTE|IUSP|IUTJ)\b",
    re.I,
)
WH_CODE_RE = re.compile(r"\b([A-Z]{3}\d)\b")
# AWD / 3PL site codes (4 letters), e.g. IUTE — calibrated C26079 inbound sample 2026-07-24
WH_SITE4_RE = re.compile(r"\b(IUTE|IUSW|IUSP|IUTJ|HEA2)\b", re.I)
RECEIVING_WH_RE = re.compile(
    r"Receiving\s+Information\s*:\s*([A-Z]{3}\d|[A-Z]{4})\b",
    re.I,
)
# Forwarder filename: label_FBA19JT0K3PY_182.pdf / label_STAR-QG6…_140.pdf
LABEL_FN_RE = re.compile(
    r"label_(?P<ship>FBA[0-9A-Z]{8,12}|STAR-[0-9A-Z]+)_(?P<n>\d+)\.pdf$",
    re.I,
)
# Filename patterns from generated freight xlsx: "... AVP1 175箱.xlsx"
FREIGHT_FN_RE = re.compile(
    r"(?P<wh>[A-Z]{3}\d|[A-Z]{4}).*?(?P<cartons>\d+)\s*箱",
    re.I,
)
CARTON_N_RE = re.compile(r"[-_](\d+)箱\.pdf$", re.I)
SKIP_DIR_NAMES = {"_inbox", "_staging", "_recognize", "_PROMOTED", "_MERGE"}
# Warehouse-like: AVP1 / CLT2 or 4-letter AWD sites e.g. IUTE
WH_DIR_RE = re.compile(r"^[A-Z]{3}\d$|^[A-Z]{4}$")


@dataclass
class PageHit:
    source_file: str
    page_index: int
    channel: str
    confidence: float
    signals: list[str] = field(default_factory=list)
    shipment_id: str = ""
    warehouse_code: str = ""
    page_fingerprint: str = ""
    text_sample: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def collect_inbox_files(inbox: Path) -> list[Path]:
    if inbox.is_file():
        return [inbox] if inbox.suffix.lower() == ".pdf" else []
    files: list[Path] = []
    for p in sorted(inbox.rglob("*.pdf")):
        if p.is_file() and not p.name.startswith("~$"):
            files.append(p)
    return files


def classify_text(text: str) -> tuple[str, float, list[str], str, str]:
    """Calibrated 2026-07-24 on forwarder inbound labels (Receiving Information + FBA/STAR)."""
    signals: list[str] = []
    t = text or ""
    shipment = ""
    wh = ""

    m_star = STAR_SHIPMENT_RE.search(t)
    m_fba = FC_SHIPMENT_RE.search(t)
    if m_star:
        shipment = m_star.group(1).upper()
        signals.append("star_shipment")
    elif m_fba:
        shipment = m_fba.group(1).upper()
        signals.append("fba_shipment")

    m_recv = RECEIVING_WH_RE.search(t)
    if m_recv:
        wh = m_recv.group(1).upper()
        signals.append(f"receiving_info:{wh}")
    if not wh:
        m_wh = WH_CODE_RE.search(t)
        if m_wh:
            wh = m_wh.group(1).upper()
            signals.append(f"wh_code:{wh}")
    if not wh:
        m4 = WH_SITE4_RE.search(t)
        if m4:
            wh = m4.group(1).upper()
            signals.append(f"wh_site4:{wh}")

    awd = bool(AWD_HINT_RE.search(t)) or bool(m_star) or (wh in {"IUTE", "IUSW", "IUSP", "IUTJ"})
    if awd:
        signals.append("awd_signal")
        conf = 0.9 if shipment and wh else 0.5
        return "AWD", conf, signals, shipment, wh
    if shipment.startswith("FBA") or wh:
        conf = 0.9 if shipment and wh else 0.45
        return "FC", conf, signals, shipment, wh
    return "UNKNOWN", 0.15, signals or ["no_channel_signal"], shipment, wh


def hints_from_filename(path: Path) -> tuple[str, int]:
    m = LABEL_FN_RE.search(path.name)
    if not m:
        return "", 0
    return m.group("ship").upper(), int(m.group("n"))


def page_fingerprint(page) -> str:
    """Fingerprint from extracted text (carton index differs per page on forwarder labels)."""
    try:
        text = (page.extract_text() or "").encode("utf-8", errors="ignore")
    except Exception:
        text = b""
    return hashlib.sha256(text).hexdigest()[:16]


def scan_pdf(path: Path) -> list[PageHit]:
    if not PdfReader:
        return [
            PageHit(str(path), 0, "UNKNOWN", 0.0, ["pypdf_missing"], "", "", "", "")
        ]
    try:
        reader = PdfReader(str(path))
    except Exception as e:
        return [
            PageHit(str(path), 0, "UNKNOWN", 0.0, [f"pdf_open_fail:{e}"], "", "", "", "")
        ]
    fn_ship, fn_n = hints_from_filename(path)
    hits: list[PageHit] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        ch, conf, sig, ship, wh = classify_text(text)
        if not ship and fn_ship:
            ship = fn_ship
            sig = list(sig) + ["shipment_from_filename"]
            conf = max(conf, 0.8)
        if fn_n and len(reader.pages) == fn_n:
            sig = list(sig) + [f"filename_page_count_ok:{fn_n}"]
        fp = page_fingerprint(page)
        hits.append(
            PageHit(
                source_file=str(path),
                page_index=i,
                channel=ch,
                confidence=conf,
                signals=sig,
                shipment_id=ship,
                warehouse_code=wh,
                page_fingerprint=fp,
                text_sample=text[:400].replace("\n", " | "),
            )
        )
    return hits


def load_authority_json(path: Path | None) -> dict[str, dict]:
    """warehouse_code -> {fba_shipment_id, cartons, ...}."""
    by_wh: dict[str, dict] = {}
    if not path or not path.is_file():
        return by_wh
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data.get("files") or []:
        wh = (row.get("warehouse_code") or "").upper()
        if not wh:
            continue
        ship = (
            row.get("fba_shipment_id")
            or row.get("awd_shipment_id")
            or row.get("shipment_id")
            or ""
        ).upper()
        by_wh[wh] = {
            "shipment_id": ship,
            "cartons": int(row.get("cartons") or 0),
            "source": "authority_json",
            "freight_file": row.get("freight_file"),
        }
    return by_wh


def load_authority_paths(paths: list[Path]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for p in paths:
        for wh, row in load_authority_json(p).items():
            merged[wh] = row
    return merged


def collect_authority_candidates(project: Path, explicit: str) -> list[Path]:
    if explicit:
        p = Path(explicit)
        return [p] if p.is_file() else []
    drafts = ROOT / "2_Processed_AI" / "drafts"
    stem = ""
    meta = project / "PROJECT.json"
    if meta.is_file():
        try:
            stem = json.loads(meta.read_text(encoding="utf-8")).get("split_order_stem") or ""
        except Exception:
            stem = ""
    if not stem:
        m = re.search(r"(C\d{5})", project.name)
        stem = m.group(1) if m else ""
    out: list[Path] = []
    for p in sorted(drafts.glob("*freight_customs_summary.json")):
        if stem and stem in p.name:
            out.append(p)
    if not out:
        out = sorted(drafts.glob("*freight_customs_summary.json"))
    return out


def infer_authority_from_freight_dir(project: Path) -> dict[str, dict]:
    """Parse 货代入库贴下单表 filenames for wh + carton count."""
    freight_dir = project / "货代入库贴下单表"
    by_wh: dict[str, dict] = {}
    if not freight_dir.is_dir():
        return by_wh
    for p in freight_dir.glob("*.xlsx"):
        if p.name.startswith("~$") or ".pre_" in p.name:
            continue
        m = FREIGHT_FN_RE.search(p.stem)
        if not m:
            continue
        wh = m.group("wh").upper()
        # Prefer 4-letter sites like IUTE when present in name
        for token in re.findall(r"\b([A-Z]{4})\b", p.stem.upper()):
            if token not in {"AWD", "STAR", "FBA"} and not token.startswith("C26"):
                if "AWD" in p.stem.upper() or "IUTE" in p.stem.upper():
                    wh = token
                    break
        cartons = int(m.group("cartons"))
        by_wh[wh] = {
            "shipment_id": "",  # fill from carton tree / summary if available
            "cartons": cartons,
            "source": "freight_filename",
            "freight_file": str(p),
        }
    return by_wh


def infer_carton_tree_stats(project: Path) -> dict[str, dict]:
    """Scan FBA外箱贴 for page counts via filename _N箱 / -N箱.pdf.

    Supports channel tree FBA外箱贴/{FC|AWD|GWD}/{wh}/ and legacy flat
    FBA外箱贴/{wh}/ (default channel=FC).
    """
    fba = project / "FBA外箱贴"
    by_wh: dict[str, dict] = {}
    if not fba.is_dir():
        return by_wh

    def scan_wh_dir(wh_dir: Path, channel: str) -> None:
        wh = wh_dir.name.upper()
        pages = 0
        inbound_files: list[str] = []
        for pdf in wh_dir.rglob("*.pdf"):
            if "入库贴" in pdf.name:
                inbound_files.append(str(pdf))
                continue
            m = CARTON_N_RE.search(pdf.name)
            if m:
                pages += int(m.group(1))
            elif PdfReader:
                try:
                    pages += len(PdfReader(str(pdf)).pages)
                except Exception:
                    pass
        by_wh[wh] = {
            "channel": channel,
            "carton_pages": pages,
            "inbound_existing": inbound_files,
            "path": str(wh_dir),
        }

    for child in fba.iterdir():
        if not child.is_dir() or child.name.startswith("_") or child.name in SKIP_DIR_NAMES:
            continue
        name = child.name.upper()
        if name in {"FC", "AWD", "GWD"}:
            for wh_dir in child.iterdir():
                if wh_dir.is_dir() and not wh_dir.name.startswith("_"):
                    scan_wh_dir(wh_dir, name)
        elif WH_DIR_RE.match(name):
            # Legacy flat FC tree
            scan_wh_dir(child, "FC")
    return by_wh


def merge_authority(
    auth: dict[str, dict], freight: dict[str, dict], carton: dict[str, dict]
) -> dict[str, dict]:
    whs = set(auth) | set(freight) | set(carton)
    out: dict[str, dict] = {}
    for wh in sorted(whs):
        a = auth.get(wh) or {}
        f = freight.get(wh) or {}
        c = carton.get(wh) or {}
        cartons = int(a.get("cartons") or f.get("cartons") or c.get("carton_pages") or 0)
        ship = (a.get("shipment_id") or f.get("shipment_id") or "").upper()
        out[wh] = {
            "shipment_id": ship,
            "cartons": cartons,
            "channel": c.get("channel") or "",
            "carton_pages": int(c.get("carton_pages") or 0),
            "freight_file": a.get("freight_file") or f.get("freight_file"),
            "fba_path": c.get("path"),
        }
    return out


def group_pages(hits: list[PageHit]) -> dict[str, list[PageHit]]:
    by_wh: dict[str, list[PageHit]] = defaultdict(list)
    for h in hits:
        key = h.warehouse_code.upper() if h.warehouse_code else "_NO_WH"
        by_wh[key].append(h)
    return by_wh


def dedupe_check(pages: list[PageHit]) -> list[dict]:
    """Return list of duplicate issues; empty = ok."""
    issues: list[dict] = []
    seen: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for p in pages:
        if not p.page_fingerprint:
            continue
        seen[p.page_fingerprint].append((p.source_file, p.page_index))
    for fp, locs in seen.items():
        if len(locs) > 1:
            issues.append(
                {
                    "fingerprint": fp,
                    "locations": [{"file": f, "page_index": i} for f, i in locs],
                }
            )
    return issues


def cross_check_warehouse(
    wh: str, pages: list[PageHit], authority: dict
) -> dict:
    """Triple check + channel consistency."""
    result = {
        "warehouse_code": wh,
        "page_count": len(pages),
        "pass": False,
        "checks": {},
        "errors": [],
    }
    if wh == "_NO_WH":
        result["errors"].append("missing_warehouse_code_on_pages")
        return result

    auth = authority.get(wh)
    if not auth:
        result["errors"].append("no_authority_row_for_warehouse")
        return result

    # Dominant shipment / channel from pages
    ships = [p.shipment_id.upper() for p in pages if p.shipment_id]
    channels = [p.channel for p in pages if p.channel != "UNKNOWN"]
    page_ship = max(set(ships), key=ships.count) if ships else ""
    page_ch = max(set(channels), key=channels.count) if channels else "UNKNOWN"
    auth_ship = (auth.get("shipment_id") or "").upper()
    auth_cartons = int(auth.get("cartons") or 0)
    carton_pages = int(auth.get("carton_pages") or 0)

    # 1) shipment_id
    ship_ok = bool(page_ship) and bool(auth_ship) and page_ship == auth_ship
    if not auth_ship:
        result["errors"].append("authority_missing_shipment_id")
        ship_ok = False
    elif not page_ship:
        result["errors"].append("pages_missing_shipment_id")
        ship_ok = False
    elif page_ship != auth_ship:
        result["errors"].append(f"shipment_mismatch:page={page_ship}:auth={auth_ship}")
        ship_ok = False
    result["checks"]["shipment_id"] = {
        "page": page_ship,
        "authority": auth_ship,
        "ok": ship_ok,
    }

    # 2) warehouse (pages already grouped by wh; confirm auth has same)
    wh_ok = wh in authority
    result["checks"]["warehouse_code"] = {"page": wh, "authority": wh, "ok": wh_ok}

    # 3) page count == cartons (== carton label pages when available)
    n = len(pages)
    count_ok = auth_cartons > 0 and n == auth_cartons
    if carton_pages > 0 and n != carton_pages:
        result["errors"].append(
            f"page_count_vs_carton_tree:pages={n}:carton_tree={carton_pages}"
        )
        count_ok = False
    if auth_cartons <= 0:
        result["errors"].append("authority_cartons_missing")
        count_ok = False
    elif n != auth_cartons:
        result["errors"].append(f"page_count_vs_freight:pages={n}:freight={auth_cartons}")
        count_ok = False
    result["checks"]["page_count_eq_cartons"] = {
        "pages": n,
        "freight_cartons": auth_cartons,
        "carton_tree_pages": carton_pages,
        "ok": count_ok,
    }

    dups = dedupe_check(pages)
    dup_ok = len(dups) == 0
    if not dup_ok:
        result["errors"].append("duplicate_pages")
    result["checks"]["no_duplicate_pages"] = {"ok": dup_ok, "duplicates": dups}

    low_conf = [p for p in pages if p.confidence < 0.35 or p.channel == "UNKNOWN"]
    if low_conf:
        result["errors"].append(f"low_confidence_or_unknown_pages:{len(low_conf)}")

    result["channel"] = page_ch or auth.get("channel") or "UNKNOWN"
    result["pass"] = (
        ship_ok
        and wh_ok
        and count_ok
        and dup_ok
        and not low_conf
        and not result["errors"]
    )
    # Recompute pass strictly from checks (errors may include soft notes)
    result["pass"] = ship_ok and wh_ok and count_ok and dup_ok and len(low_conf) == 0
    return result


def merge_write(
    pages: list[PageHit],
    dest: Path,
) -> str | None:
    import shutil

    if not PdfReader or not PdfWriter:
        return "pypdf_missing"
    srcs = {p.source_file for p in pages}
    if len(srcs) == 1:
        src = Path(next(iter(srcs)))
        ordered = sorted(pages, key=lambda x: x.page_index)
        if [p.page_index for p in ordered] == list(range(len(ordered))):
            try:
                reader = PdfReader(str(src))
                if len(reader.pages) == len(ordered):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    return None
            except Exception as e:
                return f"copy_fail:{e}"
    by_src: dict[str, list[PageHit]] = defaultdict(list)
    for p in pages:
        by_src[p.source_file].append(p)
    writers_pages = []
    for src, plist in by_src.items():
        reader = PdfReader(src)
        for p in sorted(plist, key=lambda x: x.page_index):
            writers_pages.append((p.page_index, reader.pages[p.page_index], p))
    writers_pages.sort(key=lambda t: (t[2].source_file, t[2].page_index))
    writer = PdfWriter()
    for _, page, _ in writers_pages:
        writer.add_page(page)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        writer.write(f)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Freight inbound label ingest")
    ap.add_argument("--project", required=True, help="Shipment project folder")
    ap.add_argument(
        "--inbox",
        default="",
        help="Inbox file/folder (default: {project}/货代入库贴/_inbox)",
    )
    ap.add_argument(
        "--authority",
        default="",
        help="Optional single summary JSON; default merges all C##### freight summaries",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Write merged PDFs into FBA外箱贴 when checks pass",
    )
    args = ap.parse_args()

    project = Path(args.project)
    if not project.is_dir():
        print(f"project missing: {project}", file=sys.stderr)
        return 1

    inbound_root = project / "货代入库贴"
    inbox = Path(args.inbox) if args.inbox else inbound_root / "_inbox"
    recognize_dir = inbound_root / "_recognize"
    staging = inbound_root / "_staging"
    recognize_dir.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    if args.apply:
        staging.mkdir(parents=True, exist_ok=True)

    auth_paths = collect_authority_candidates(project, args.authority)
    authority = merge_authority(
        load_authority_paths(auth_paths),
        infer_authority_from_freight_dir(project),
        infer_carton_tree_stats(project),
    )

    files = collect_inbox_files(inbox)
    all_hits: list[PageHit] = []
    file_entries: list[dict] = []
    for fpath in files:
        hits = scan_pdf(fpath)
        all_hits.extend(hits)
        ships = sorted({h.shipment_id for h in hits if h.shipment_id})
        whs = sorted({h.warehouse_code for h in hits if h.warehouse_code})
        chs = sorted({h.channel for h in hits})
        file_entries.append(
            {
                "path": str(fpath),
                "page_count": len(hits),
                "channels": chs,
                "shipment_ids": ships,
                "warehouses": whs,
                "sample_page0": asdict(hits[0]) if hits else None,
            }
        )

    by_wh = group_pages(all_hits)
    warehouse_reports: list[dict] = []
    written: list[str] = []
    blocked = False

    for wh, pages in sorted(by_wh.items()):
        report = cross_check_warehouse(wh, pages, authority)
        warehouse_reports.append(report)
        if not report["pass"]:
            blocked = True
            continue
        if not args.apply:
            continue
        channel = report.get("channel") or authority.get(wh, {}).get("channel") or "FC"
        if channel not in {"FC", "AWD", "GWD"}:
            report["errors"].append("bad_channel_for_write")
            report["pass"] = False
            blocked = True
            continue
        n = len(pages)
        dest_dir = project / "FBA外箱贴" / channel / wh
        flat_dir = project / "FBA外箱贴" / wh
        if channel == "FC" and flat_dir.is_dir() and not (
            dest_dir.is_dir() and any(dest_dir.rglob("*.pdf"))
        ):
            dest_dir = flat_dir
        dest = dest_dir / f"{channel}_{wh}_入库贴_{n}箱.pdf"
        err = merge_write(pages, dest)
        if err:
            report["errors"].append(err)
            report["pass"] = False
            blocked = True
        else:
            report["written"] = str(dest)
            written.append(str(dest))

    out = {
        "generated_at": _now(),
        "project": str(project),
        "inbox": str(inbox),
        "apply": bool(args.apply),
        "authority_paths": [str(p) for p in auth_paths],
        "authority_warehouses": authority,
        "doc": "Templates/Freight_Inbound_Label_Pipeline.md",
        "inbox_file_count": len(files),
        "total_pages": len(all_hits),
        "files": file_entries,
        "warehouses": warehouse_reports,
        "written": written,
        "blocked": blocked or len(files) == 0,
        "notes": [],
        "layout_calibrated": {
            "at": "2026-07-24",
            "sample": "945箱入库贴(1).zip",
            "signals": [
                "Receiving Information: {WH}",
                "FBA… / STAR-…",
                "label_{ship}_{N}.pdf",
            ],
        },
    }
    if len(files) == 0:
        out["notes"].append("inbox_empty: place freight-returned PDFs under 货代入库贴/_inbox")
    if blocked and args.apply:
        out["notes"].append("apply_skipped_or_partial: fix cross-check errors before merge")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = recognize_dir / f"inbound_recognize_{stamp}.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (recognize_dir / "inbound_recognize_latest.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"report: {report_path}")
    print(
        f"inbox_files: {len(files)} pages: {len(all_hits)} "
        f"warehouses: {len(by_wh)} blocked: {out['blocked']}"
    )
    for wr in warehouse_reports:
        status = "PASS" if wr.get("pass") else "FAIL"
        print(
            f"  {status} {wr.get('warehouse_code')} pages={wr.get('page_count')} "
            f"errs={wr.get('errors')}"
        )
    if written:
        print("written:")
        for w in written:
            print(f"  {w}")
    if len(files) == 0:
        return 0
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
