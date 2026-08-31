# -*- coding: utf-8 -*-
"""产品标签：按订单行从源库只读复制到当票目录（不改源）。"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .canonical import load_schema, normalize_color, normalize_size

TZ = timezone(timedelta(hours=8))
EXCLUDE = {"desktop.ini", "Thumbs.db"}
SCRIPTS = Path(__file__).resolve().parent.parent
PROJECT = SCRIPTS.parent
DEFAULT_LABEL_SRC = PROJECT / "1_Input_Raw" / "00_Master_Reference" / "桌布标签"
INV_DIR = PROJECT / "2_Processed_AI" / "label_source_inventory"


def now_iso() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def inventory(root: Path) -> dict:
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name in EXCLUDE:
            continue
        rel = p.relative_to(root).as_posix()
        files.append({"rel": rel, "size": p.stat().st_size, "ext": p.suffix.lower()})
    by_ext = dict(Counter(f["ext"] for f in files))
    return {
        "taken_at": now_iso(),
        "root": str(root),
        "total_files": len(files),
        "by_ext": by_ext,
        "files": files,
        "fingerprint": hashlib.sha256(
            json.dumps([(f["rel"], f["size"]) for f in files], ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    }


def same_inv(a: dict, b: dict) -> bool:
    return a.get("fingerprint") == b.get("fingerprint") and a.get("total_files") == b.get(
        "total_files"
    )


def size_folder(size: Any, schema: dict | None = None) -> str:
    schema = schema or load_schema()
    fmap = (schema.get("size_folder_map") or {}).get("to_folder") or {}
    raw = str(size or "").strip()
    if raw in fmap:
        return fmap[raw]
    # try normalized / aliases
    for k, v in fmap.items():
        if k.lower() == raw.lower():
            return v
    ns = normalize_size(raw, schema) or raw
    if ns in fmap:
        return fmap[ns]
    # 60X102inch → 60x102
    m = re.match(r"(?i)(\d+)\s*[xX×*]\s*(\d+)", ns.replace("inch", ""))
    if m:
        return f"{int(m.group(1))}x{int(m.group(2))}"
    if "90" in ns and "圆" in ns:
        return "90圆"
    return ns.lower()


def brand_prefix(entity_code: str) -> str:
    return "C04-" if entity_code == "C04" else "C07-"


def pack_ok(rel: str, spp: int) -> bool:
    r = rel.replace("\\", "/")
    name = Path(rel).name.lower()
    return f"{int(spp)}条装" in r or f"{int(spp)}条" in Path(rel).name or f"{int(spp)}p" in name


def size_in_path(rel: str, folder: str) -> bool:
    r = rel.replace("\\", "/").lower()
    f = folder.lower()
    if f in r:
        return True
    # 102 / 60x102
    if f.replace("x", "") and any(tok in r for tok in f.split("x") if len(tok) >= 2):
        if "90" in f:
            return "90" in r and ("圆" in rel or "round" in r)
        # require both dims when x form
        if "x" in f:
            a, b = f.split("x", 1)
            return a in r and b in r
    return False


def color_ok(rel: str, color: str | None, schema: dict | None = None) -> bool:
    schema = schema or load_schema()
    canon = normalize_color(color, schema) or (color or "")
    name = Path(rel).name
    low = (rel + " " + name).lower()
    if canon == "米白":
        return any(
            x in rel or x.lower() in low
            for x in ("米白", "象牙", "ivory", "Ivory", "象牙白")
        )
    if canon == "白":
        if any(x in rel for x in ("米白", "象牙", "ivory", "Ivory")):
            return False
        return "白" in rel or "white" in low
    if canon == "黑":
        return "黑" in rel or "black" in low
    if canon == "蓝":
        return "蓝" in rel or "blue" in low
    return bool(canon) and (canon in rel or str(color or "") in rel)


def copy_product_labels(
    *,
    order_code: str,
    entity_code: str,
    lines: list[dict],
    dest_root: Path,
    label_source: Path | None = None,
    require_source_stable: bool = True,
) -> dict:
    """
    源只读复制 → dest_root/{order_code}标签/{N}条装/{尺寸短码}/{原名}.pdf
    """
    src = Path(label_source) if label_source else DEFAULT_LABEL_SRC
    if not src.is_dir():
        raise FileNotFoundError(f"label source missing: {src}")

    INV_DIR.mkdir(parents=True, exist_ok=True)
    schema = load_schema()
    before = inventory(src)
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    before_path = INV_DIR / f"before_{order_code}_{ts}.json"
    before_path.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")

    last_path = INV_DIR / "last_completed.json"
    if require_source_stable:
        if not last_path.exists():
            raise RuntimeError("last_completed.json missing — refuse copy without baseline")
        last = json.loads(last_path.read_text(encoding="utf-8"))
        if "fingerprint" not in last:
            last["fingerprint"] = hashlib.sha256(
                json.dumps(
                    [(f["rel"], f["size"]) for f in last.get("files") or []],
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
        if not same_inv(before, last):
            raise RuntimeError(
                f"label source drifted vs last_completed "
                f"(before={before['total_files']} last={last.get('total_files')})"
            )

    prefix = brand_prefix(entity_code)
    brand = "WIGENIUS" if entity_code == "C04" else "Dressmaker"
    src_files = [f["rel"] for f in before["files"] if f["rel"].replace("\\", "/").startswith(prefix)]
    # fallback: any under brand folder name fragment
    if not src_files:
        src_files = [
            f["rel"]
            for f in before["files"]
            if entity_code in f["rel"] or brand.lower() in f["rel"].lower()
        ]

    bundle = dest_root / f"{order_code}标签"
    bundle.mkdir(parents=True, exist_ok=True)

    design_lines = []
    copied = 0
    missing = []
    ambiguous = []
    files_out = []

    for line in lines:
        spp = int(float(line.get("strips_per_pack") or 0) or 0)
        if spp <= 0:
            continue
        folder = size_folder(line.get("size"), schema)
        color = line.get("color")
        cands = []
        for rel in src_files:
            if not pack_ok(rel, spp):
                continue
            if not size_in_path(rel, folder):
                continue
            if not color_ok(rel, color, schema):
                continue
            score = 10
            if "110克" in rel:
                score += 5
            if "150克" in rel:
                score += 1
            if "90G" in rel or "90克" in rel:
                score += 3
            cands.append({"rel": rel, "score": score})
        cands.sort(key=lambda x: (-x["score"], x["rel"]))

        status = "missing"
        chosen = None
        dest_rel = None
        if not cands:
            missing.append({"size": line.get("size"), "color": color, "strips_per_pack": spp})
        else:
            top = cands[0]["score"]
            top_cands = [c for c in cands if c["score"] == top]
            if len(top_cands) > 1:
                status = "ambiguous"
                ambiguous.append({"line": line, "cands": [c["rel"] for c in top_cands]})
            else:
                chosen = top_cands[0]["rel"]
                src_path = src / Path(chosen)
                dest_dir = bundle / f"{spp}条装" / folder
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / src_path.name
                if not dest_path.exists():
                    shutil.copy2(src_path, dest_path)
                dest_rel = dest_path.relative_to(dest_root).as_posix()
                status = "copied"
                copied += 1
                files_out.append(
                    {
                        "section_id": "product_label_pack",
                        "path": str(dest_path),
                        "file_name": dest_rel.replace("/", "__"),
                    }
                )

        design_lines.append(
            {
                **line,
                "size_folder": folder,
                "brand": brand,
                "source_rel": chosen,
                "dest_rel": dest_rel,
                "status": status,
                "candidates": cands[:5],
            }
        )

    after = inventory(src)
    after_path = INV_DIR / f"after_{order_code}_{ts}.json"
    after_path.write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")
    match_ok = same_inv(before, after)
    if not match_ok:
        raise RuntimeError("CRITICAL: label source changed during copy — abort")
    # refresh baseline only when stable
    last_path.write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "order_code": order_code,
        "entity_code": entity_code,
        "brand": brand,
        "layout": "产品标签/{EF}标签/{N}条装/{尺寸}/{原名}.pdf",
        "label_source": str(src),
        "copied": copied,
        "missing": missing,
        "ambiguous": ambiguous,
        "source_before": {
            "total_files": before["total_files"],
            "fingerprint": before["fingerprint"],
            "inventory_file": str(before_path),
        },
        "source_after": {
            "total_files": after["total_files"],
            "fingerprint": after["fingerprint"],
            "inventory_file": str(after_path),
            "unchanged": match_ok,
        },
        "lines": design_lines,
    }
    (bundle / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    files_out.append(
        {
            "section_id": "product_label_pack",
            "path": str(bundle / "_manifest.json"),
            "file_name": f"{order_code}标签__manifest.json",
        }
    )

    ok = copied > 0 and not missing and not ambiguous
    return {
        "ok": ok,
        "copied": copied,
        "missing": missing,
        "ambiguous": ambiguous,
        "files": files_out,
        "manifest": manifest,
        "bundle_dir": str(bundle),
    }
