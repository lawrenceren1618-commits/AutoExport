# -*- coding: utf-8 -*-
"""Amazon carton-label ingest (unified):

Purpose of split AND merge is the same: AI field recognition + factory batch labeling.
Difference is layout/channel (FC vs AWD vs GWD): one recognize → confirm-fields-by-layout
flow, then separate → merge same warehouse+spec into one multipage PDF → organize.

See Templates/Carton_Label_Channels.md §0 and §3.

Channels: FC (fulfillment center), AWD, GWD (reserved), UNKNOWN.

Usage (after user uploads samples):
  python Scripts/10_carton_label_ingest.py --project "<Shipments/...>" --inbox "<path-to-uploads>"
  python Scripts/10_carton_label_ingest.py --project "..." --inbox "..." --apply
      # without --apply: write only under FBA外箱贴/_staging + _recognize report

Clean / convert run only when heuristics say needed.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = None  # type: ignore
    PdfWriter = None  # type: ignore

# --- channel signals (AWD/GWD to be enriched from first real samples) ---
FC_SHIPMENT_RE = re.compile(r"\b(FBA[0-9A-Z]{8,12})\b", re.I)
FC_CARTON_RE = re.compile(r"(FBA[0-9A-Z]{8,12})U\d{5,}", re.I)
# Placeholders: tighten after AWD sample calibration
AWD_HINT_RE = re.compile(
    r"\b(AWD|Amazon\s+Warehousing|Warehousing\s*&\s*Distribution|AMXL\s*AWD)\b",
    re.I,
)
GWD_HINT_RE = re.compile(r"\b(GWD)\b", re.I)
WH_CODE_RE = re.compile(r"\b([A-Z]{3}\d)\b")


@dataclass
class PageHit:
    source_file: str
    page_index: int  # 0-based
    channel: str
    confidence: float
    signals: list[str] = field(default_factory=list)
    shipment_id: str = ""
    warehouse_code: str = ""
    text_sample: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def need_clean(path: Path) -> list[str]:
    """Return reasons to clean; empty = skip clean."""
    reasons: list[str] = []
    if path.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".zip"}:
        reasons.append(f"unusual_suffix:{path.suffix}")
    if path.stat().st_size == 0:
        reasons.append("empty_file")
    if re.search(r"[\x00-\x08]", path.name):
        reasons.append("binary_junk_in_filename")
    return reasons


def need_convert(path: Path) -> list[str]:
    """Return reasons to convert; empty = skip convert (use as-is)."""
    reasons: list[str] = []
    suf = path.suffix.lower()
    if suf in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        reasons.append("raster_image_needs_pdf_or_ocr")
    if suf in {".zip", ".rar", ".7z"}:
        reasons.append("archive_needs_extract")
    if suf in {".doc", ".docx", ".xls", ".xlsx"}:
        reasons.append("office_doc_not_carton_pdf")
    return reasons


def classify_text(text: str) -> tuple[str, float, list[str], str, str]:
    """Return channel, confidence, signals, shipment_id, warehouse_code."""
    signals: list[str] = []
    t = text or ""
    shipment = ""
    wh = ""

    m_cart = FC_CARTON_RE.search(t)
    m_fba = FC_SHIPMENT_RE.search(t)
    if m_cart:
        shipment = m_cart.group(1).upper()
        signals.append("fc_carton_token")
    elif m_fba:
        shipment = m_fba.group(1).upper()
        signals.append("fc_shipment_token")

    m_wh = WH_CODE_RE.search(t)
    if m_wh:
        wh = m_wh.group(1).upper()
        signals.append(f"wh_code:{wh}")

    awd = bool(AWD_HINT_RE.search(t))
    gwd = bool(GWD_HINT_RE.search(t))
    if awd:
        signals.append("awd_keyword")
    if gwd:
        signals.append("gwd_keyword")

    # Decision: AWD/GWD keywords win over bare FBA-looking tokens when present
    if gwd and not awd:
        return "GWD", 0.55 if shipment or wh else 0.4, signals, shipment, wh
    if awd:
        conf = 0.7 if ("awd_keyword" in signals) else 0.5
        return "AWD", conf, signals, shipment, wh
    if shipment.startswith("FBA") or "fc_carton_token" in signals:
        conf = 0.85 if "fc_carton_token" in signals else 0.65
        return "FC", conf, signals, shipment, wh
    if wh and "Amazon" in t:
        return "FC", 0.45, signals + ["amazon_plus_wh_weak"], shipment, wh
    return "UNKNOWN", 0.2, signals or ["no_channel_signal"], shipment, wh


def scan_pdf(path: Path) -> list[PageHit]:
    if not PdfReader:
        return [
            PageHit(
                str(path),
                0,
                "UNKNOWN",
                0.0,
                ["pypdf_missing"],
                "",
                "",
                "",
            )
        ]
    hits: list[PageHit] = []
    try:
        reader = PdfReader(str(path))
    except Exception as e:
        return [
            PageHit(str(path), 0, "UNKNOWN", 0.0, [f"pdf_open_fail:{e}"], "", "", "")
        ]
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        ch, conf, sig, ship, wh = classify_text(text)
        hits.append(
            PageHit(
                source_file=str(path),
                page_index=i,
                channel=ch,
                confidence=conf,
                signals=sig,
                shipment_id=ship,
                warehouse_code=wh,
                text_sample=text[:400].replace("\n", " | "),
            )
        )
    return hits


def split_and_stage(
    path: Path,
    hits: list[PageHit],
    staging: Path,
    *,
    apply_write: bool,
) -> list[dict]:
    """Split pages into staging/{channel}/{wh|unknown}/page_XXXX.pdf."""
    out_meta: list[dict] = []
    if not PdfReader or not PdfWriter:
        return [{"error": "pypdf_missing", "file": str(path)}]
    if not apply_write:
        for h in hits:
            out_meta.append({**asdict(h), "staged_path": None, "dry_run": True})
        return out_meta

    reader = PdfReader(str(path))
    for h in hits:
        ch = h.channel if h.channel in {"FC", "AWD", "GWD"} else "UNKNOWN"
        wh = h.warehouse_code or "_no_wh"
        dest_dir = staging / ch / wh
        dest_dir.mkdir(parents=True, exist_ok=True)
        stem = path.stem[:40]
        dest = dest_dir / f"{stem}_p{h.page_index + 1:04d}_{h.shipment_id or 'noship'}.pdf"
        writer = PdfWriter()
        writer.add_page(reader.pages[h.page_index])
        with dest.open("wb") as f:
            writer.write(f)
        out_meta.append({**asdict(h), "staged_path": str(dest), "dry_run": False})
    return out_meta


def collect_inbox_files(inbox: Path) -> list[Path]:
    if inbox.is_file():
        return [inbox]
    files: list[Path] = []
    for p in sorted(inbox.rglob("*")):
        if p.is_file() and not p.name.startswith("~$"):
            files.append(p)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description="Carton label channel ingest")
    ap.add_argument("--project", required=True, help="Shipment project folder")
    ap.add_argument("--inbox", required=True, help="Uploaded raw labels file or folder")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually split PDFs into FBA外箱贴/_staging (default: recognize report only)",
    )
    args = ap.parse_args()
    project = Path(args.project)
    inbox = Path(args.inbox)
    if not project.is_dir():
        print(f"project missing: {project}", file=sys.stderr)
        return 1
    if not inbox.exists():
        print(f"inbox missing: {inbox}", file=sys.stderr)
        return 1

    fba_root = project / "FBA外箱贴"
    staging = fba_root / "_staging"
    recognize_dir = fba_root / "_recognize"
    recognize_dir.mkdir(parents=True, exist_ok=True)
    if args.apply:
        staging.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "generated_at": _now(),
        "project": str(project),
        "inbox": str(inbox),
        "apply": bool(args.apply),
        "doc": "Templates/Carton_Label_Channels.md",
        "files": [],
        "channel_counts": {},
        "notes": [
            "AWD/GWD keyword list is provisional until first sample calibration",
            "Clean/convert skipped when heuristics return no reasons",
        ],
    }

    for fpath in collect_inbox_files(inbox):
        entry: dict = {
            "path": str(fpath),
            "clean_reasons": need_clean(fpath),
            "convert_reasons": need_convert(fpath),
            "clean_executed": False,
            "convert_executed": False,
            "pages": [],
        }
        # Optional steps: only flag; heavy OCR/convert left for when sample needs it
        if entry["clean_reasons"]:
            report["notes"].append(f"clean_suggested:{fpath.name}:{entry['clean_reasons']}")
        if entry["convert_reasons"]:
            report["notes"].append(f"convert_suggested:{fpath.name}:{entry['convert_reasons']}")
            entry["pages"] = [
                asdict(
                    PageHit(
                        str(fpath),
                        0,
                        "UNKNOWN",
                        0.0,
                        ["skipped_pending_convert"],
                        "",
                        "",
                        "",
                    )
                )
            ]
            report["files"].append(entry)
            continue

        if fpath.suffix.lower() != ".pdf":
            entry["pages"] = [
                asdict(
                    PageHit(
                        str(fpath),
                        0,
                        "UNKNOWN",
                        0.0,
                        ["non_pdf_no_convert_needed_flag_false"],
                        "",
                        "",
                        "",
                    )
                )
            ]
            report["files"].append(entry)
            continue

        hits = scan_pdf(fpath)
        staged = split_and_stage(fpath, hits, staging, apply_write=args.apply)
        entry["pages"] = staged
        for h in hits:
            report["channel_counts"][h.channel] = report["channel_counts"].get(h.channel, 0) + 1
        report["files"].append(entry)

    out_json = recognize_dir / f"ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_lines = [
        "# 外箱贴渠道识别报告",
        "",
        f"- 时间：{report['generated_at']}",
        f"- inbox：`{inbox}`",
        f"- apply 拆分归纳：{'是 → _staging' if args.apply else '否（仅识别）'}",
        f"- 渠道页数统计：{report['channel_counts']}",
        "",
        "## 文件",
        "",
    ]
    for fe in report["files"]:
        md_lines.append(f"### `{Path(fe['path']).name}`")
        md_lines.append(f"- clean: {fe['clean_reasons'] or '跳过'}")
        md_lines.append(f"- convert: {fe['convert_reasons'] or '跳过'}")
        chs = {}
        for p in fe.get("pages") or []:
            c = p.get("channel", "?")
            chs[c] = chs.get(c, 0) + 1
        md_lines.append(f"- pages by channel: {chs}")
        md_lines.append("")
    out_md = out_json.with_suffix(".md")
    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print("channel_counts:", report["channel_counts"])
    if not args.apply:
        print("dry-run only; re-run with --apply to split into FBA外箱贴/_staging/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
