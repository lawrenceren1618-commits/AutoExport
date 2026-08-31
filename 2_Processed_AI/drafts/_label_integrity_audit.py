# -*- coding: utf-8 -*-
"""Read-only label source integrity audit. Does not modify source."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
SRC = ROOT / "1_Input_Raw" / "00_Master_Reference" / "桌布标签"
LAST = ROOT / "2_Processed_AI" / "label_source_inventory" / "last_completed.json"
OUT = ROOT / "2_Processed_AI" / "label_source_inventory" / f"integrity_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

PDF_MAGIC = b"%PDF"
EOF_MARKERS = (b"%%EOF", b"%%eof")


def inventory(root: Path) -> list[dict]:
    files = []
    if not root.exists():
        return files
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        ext = p.suffix.lower()
        try:
            size = p.stat().st_size
        except OSError as e:
            files.append(
                {
                    "rel": rel,
                    "ext": ext,
                    "size": None,
                    "error": f"stat:{e}",
                    "ok": False,
                }
            )
            continue
        files.append({"rel": rel, "ext": ext, "size": size, "path": str(p)})
    return files


def check_pdf(path: Path, size: int) -> dict:
    result = {
        "ok": True,
        "issues": [],
        "header": None,
        "has_eof": False,
        "sha256_8": None,
    }
    if size == 0:
        result["ok"] = False
        result["issues"].append("zero_byte")
        return result
    if size < 64:
        result["ok"] = False
        result["issues"].append("tiny_file")
    try:
        with path.open("rb") as f:
            head = f.read(16)
            result["header"] = head[:8].hex()
            if not head.startswith(PDF_MAGIC):
                result["ok"] = False
                result["issues"].append(f"bad_magic:{head[:8]!r}")
            # read whole for hash + eof (label PDFs are small ~50-170KB)
            f.seek(0)
            data = f.read()
        result["sha256_8"] = hashlib.sha256(data).hexdigest()[:8]
        # EOF near end (allow trailing whitespace/NUL)
        tail = data[-2048:] if len(data) > 2048 else data
        if any(m in tail for m in EOF_MARKERS):
            result["has_eof"] = True
        else:
            result["ok"] = False
            result["issues"].append("missing_%%EOF")
        # truncated stream heuristic: linearize /ObjStm ok; check xref-ish
        if b"startxref" not in data and b"/Root" not in data:
            result["ok"] = False
            result["issues"].append("no_startxref_or_root")
        # try pypdf if available
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(path, strict=False)
            n = len(reader.pages)
            result["pages"] = n
            if n < 1:
                result["ok"] = False
                result["issues"].append("zero_pages")
        except ImportError:
            result["parser"] = "pypdf_unavailable"
            try:
                import PyPDF2  # type: ignore

                reader = PyPDF2.PdfReader(str(path), strict=False)
                n = len(reader.pages)
                result["pages"] = n
                if n < 1:
                    result["ok"] = False
                    result["issues"].append("zero_pages")
            except ImportError:
                result["parser"] = "none"
            except Exception as e:
                result["ok"] = False
                result["issues"].append(f"PyPDF2:{type(e).__name__}:{e}")
        except Exception as e:
            result["ok"] = False
            result["issues"].append(f"pypdf:{type(e).__name__}:{e}")
    except OSError as e:
        result["ok"] = False
        result["issues"].append(f"read:{e}")
    return result


def brand_of(rel: str) -> str:
    return rel.split("/", 1)[0] if "/" in rel else rel


def main() -> int:
    print("SRC exists:", SRC.exists(), flush=True)
    print("SRC:", SRC, flush=True)
    cur = inventory(SRC)
    by_ext = Counter(f.get("ext") or "" for f in cur)
    pdfs = [f for f in cur if f.get("ext") == ".pdf"]
    print(f"total_files={len(cur)} by_ext={dict(by_ext)}", flush=True)

    bad = []
    ok_count = 0
    for f in pdfs:
        path = Path(f["path"])
        chk = check_pdf(path, f["size"] or 0)
        f["check"] = {k: v for k, v in chk.items() if k != "ok"}
        f["ok"] = chk["ok"]
        if chk["ok"]:
            ok_count += 1
        else:
            bad.append(
                {
                    "rel": f["rel"],
                    "size": f["size"],
                    "issues": chk["issues"],
                    "header": chk.get("header"),
                    "pages": chk.get("pages"),
                }
            )
        # drop absolute path from export
        del f["path"]

    # compare last_completed
    drift = {"missing_now": [], "extra_now": [], "size_changed": []}
    last_meta = None
    if LAST.exists():
        last = json.loads(LAST.read_text(encoding="utf-8"))
        last_meta = {
            "taken_at": last.get("taken_at"),
            "total_files": last.get("total_files"),
            "fingerprint": last.get("fingerprint"),
        }
        last_map = {x["rel"]: x["size"] for x in last.get("files", [])}
        now_map = {f["rel"]: f["size"] for f in pdfs}
        for rel, sz in last_map.items():
            if rel not in now_map:
                drift["missing_now"].append(rel)
            elif now_map[rel] != sz:
                drift["size_changed"].append(
                    {"rel": rel, "was": sz, "now": now_map[rel]}
                )
        for rel, sz in now_map.items():
            if rel not in last_map:
                drift["extra_now"].append({"rel": rel, "size": sz})

    # fingerprint like label_copy
    lines = []
    for f in sorted(pdfs, key=lambda x: x["rel"].lower()):
        lines.append(f"{f['rel']}|{f['size']}")
    fp = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    by_brand = Counter(brand_of(f["rel"]) for f in pdfs)

    report = {
        "taken_at": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
        "root": str(SRC),
        "total_files": len(cur),
        "by_ext": dict(by_ext),
        "pdf_ok": ok_count,
        "pdf_bad": len(bad),
        "by_brand": dict(by_brand),
        "fingerprint": fp,
        "last_completed": last_meta,
        "drift_vs_last_completed": drift,
        "bad_files": bad,
        "note": "read-only audit; source not modified",
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "taken_at", "total_files", "by_ext", "pdf_ok", "pdf_bad",
        "by_brand", "fingerprint", "last_completed"
    )}, ensure_ascii=False, indent=2), flush=True)
    print("--- bad_files ---", flush=True)
    print(json.dumps(bad, ensure_ascii=False, indent=2), flush=True)
    print("--- drift ---", flush=True)
    print(json.dumps(drift, ensure_ascii=False, indent=2), flush=True)
    print("OUT:", OUT, flush=True)
    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(main())
