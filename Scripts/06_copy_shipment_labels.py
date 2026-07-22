# -*- coding: utf-8 -*-
"""C26079 label rematch + copy. Label source read-only."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
LABEL_SRC = ROOT / r"1_Input_Raw\00_Master_Reference\桌布标签"
INV_DIR = ROOT / r"2_Processed_AI\label_source_inventory"
PROJ = ROOT / r"1_Input_Raw\Shipments\EF-C26079-C04-36460  桌布-2026.7.10"
ORDER = PROJ / r"订单表\EF-C26079-C04-36460  桌布-2026.7.10.xls"
DEST = PROJ / "产品标签"
ORDER_CODE = "EF-C26079-C04-36460"
LABEL_BUNDLE = DEST / f"{ORDER_CODE}标签"
EXCLUDE = {"desktop.ini", "Thumbs.db"}
TZ = timezone(timedelta(hours=8))


def now_iso() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def inventory(root: Path) -> dict:
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name in EXCLUDE:
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
        "exclude_names": list(EXCLUDE),
        "fingerprint": hashlib.sha256(
            json.dumps([(f["rel"], f["size"]) for f in files], ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    }


def same_inv(a: dict, b: dict) -> bool:
    return a.get("fingerprint") == b.get("fingerprint") and a.get("total_files") == b.get("total_files")


def norm_size(s: str) -> str:
    t = str(s).lower().replace(" ", "").replace("×", "x").replace("*", "x")
    t = t.replace("inch", "").replace("寸", "")
    if "round" in t or "圆" in str(s):
        return "90圆"
    t = re.sub(r"[^0-9x]", "", t)
    # 60x102 / 6x102
    if t in ("60102", "6x102", "60x102"):
        return "60x102"
    if t.startswith("60") and "102" in t:
        return "60x102"
    if "126" in t:
        return "60x126"
    if "120" in t or "70120" in t:
        return "70x120"
    if "84" in t:
        return "60x84"
    return t


def size_in_path(rel: str, size_key: str) -> bool:
    r = rel.lower().replace("\\", "/")
    if size_key == "60x102":
        return any(x in r for x in ("60x102", "6x102", "60×102", "/102"))
    if size_key == "60x126":
        return "126" in r
    if size_key == "70x120":
        return any(x in r for x in ("70x120", "70120", "120")) and "126" not in r
    if size_key == "90圆":
        return "90圆" in r or "90寸圆" in r or "90圆" in rel
    if size_key == "60x84":
        return "84" in r
    return size_key in r


def color_ok(rel: str, color: str) -> bool:
    name = Path(rel).name.lower()
    c = color.strip()
    if c in ("白", "白色"):
        return ("白" in name or "white" in name) and "米白" not in name and "象牙" not in name and "ivory" not in name
    if c in ("黑", "黑色"):
        return "黑" in name or "black" in name
    if c in ("米白", "象牙", "象牙白"):
        return any(x in name for x in ("米白", "象牙", "ivory", "象牙白"))
    if c in ("蓝", "蓝色", "金", "银"):
        return "蓝" in name or "blue" in name
    return c in name


def pack_ok(rel: str, spp: int) -> bool:
    r = rel.replace("\\", "/")
    return f"{int(spp)}条装" in r or f"{int(spp)}条" in Path(rel).name or f"{int(spp)}p" in Path(rel).name.lower()


def parse_order(path: Path) -> list[dict]:
    import xlrd

    book = xlrd.open_workbook(str(path))
    sh = book.sheet_by_index(0)
    header_row = None
    for i in range(sh.nrows):
        row = [str(sh.cell_value(i, j)).replace(" ", "") for j in range(sh.ncols)]
        if any("尺寸规格" in c for c in row):
            header_row = i
            break
    if header_row is None:
        raise RuntimeError("packing header not found")
    lines = []
    for i in range(header_row + 1, sh.nrows):
        size = str(sh.cell_value(i, 0)).strip()
        if not size or size.startswith("装"):
            continue
        color = str(sh.cell_value(i, 1)).strip()
        spp = sh.cell_value(i, 2)
        fnsku = str(sh.cell_value(i, 3)).strip()
        if not fnsku.startswith("X"):
            continue
        lines.append(
            {
                "size": size,
                "color": color,
                "strips_per_pack": int(float(spp)),
                "fnsku": fnsku,
                "packs_per_carton": int(float(sh.cell_value(i, 4))) if sh.cell_value(i, 4) != "" else None,
                "cartons": int(float(sh.cell_value(i, 5))) if sh.cell_value(i, 5) != "" else None,
                "total_strips": int(float(sh.cell_value(i, 6))) if sh.cell_value(i, 6) != "" else None,
            }
        )
    return lines


def main() -> int:
    INV_DIR.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")

    before = inventory(LABEL_SRC)
    before_path = INV_DIR / f"before_C26079_{ts}.json"
    before_path.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")

    last_path = INV_DIR / "last_completed.json"
    if not last_path.exists():
        print("ABORT: last_completed.json missing")
        return 2
    last = json.loads(last_path.read_text(encoding="utf-8"))
    # rebuild fingerprint if old file lacks it
    if "fingerprint" not in last:
        last["fingerprint"] = hashlib.sha256(
            json.dumps([(f["rel"], f["size"]) for f in last["files"]], ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    if not same_inv(before, last):
        print("ABORT: source drifted vs last_completed")
        print("before", before["total_files"], before["fingerprint"][:12])
        print("last", last["total_files"], last.get("fingerprint", "")[:12])
        # show small diff
        bset = {(f["rel"], f["size"]) for f in before["files"]}
        lset = {(f["rel"], f["size"]) for f in last["files"]}
        print("only_before", list(bset - lset)[:10])
        print("only_last", list(lset - bset)[:10])
        return 3

    src_files = [f["rel"] for f in before["files"] if f["rel"].startswith("C04-")]
    lines = parse_order(ORDER)
    design_lines = []
    copied = 0
    ambiguous = []
    missing = []

    for line in lines:
        size_key = norm_size(line["size"])
        spp = line["strips_per_pack"]
        color = line["color"]
        cands = []
        for rel in src_files:
            if not pack_ok(rel, spp):
                continue
            if not size_in_path(rel, size_key):
                continue
            if not color_ok(rel, color):
                continue
            # prefer 110 over 150
            score = 10
            if "110克" in rel:
                score += 5
            if "150克" in rel:
                score += 1
            cands.append({"rel": rel, "score": score})
        cands.sort(key=lambda x: (-x["score"], x["rel"]))
        # keep top score group
        if not cands:
            status = "missing"
            missing.append(line["fnsku"])
            chosen = None
        else:
            top = cands[0]["score"]
            top_cands = [c for c in cands if c["score"] == top]
            if len(top_cands) > 1:
                status = "ambiguous"
                ambiguous.append({"fnsku": line["fnsku"], "cands": [c["rel"] for c in top_cands]})
                chosen = None
            else:
                chosen = top_cands[0]["rel"]
                status = "copied_ready"

        dest_rel = None
        if chosen:
            src_path = LABEL_SRC / Path(chosen)
            pack_dir = f"{int(spp)}条装"
            size_dir = size_key  # already normalized e.g. 60x102 / 90圆
            dest_dir = LABEL_BUNDLE / pack_dir / size_dir
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / src_path.name  # keep source filename; no FNSKU in path
            if dest_path.exists() and dest_path.stat().st_size != src_path.stat().st_size:
                status = "name_collision"
                ambiguous.append({"fnsku": line["fnsku"], "cands": [chosen], "issue": "name_collision"})
                chosen_out = chosen
            else:
                if not dest_path.exists():
                    shutil.copy2(src_path, dest_path)
                dest_rel = dest_path.relative_to(DEST).as_posix()
                status = "copied"
                copied += 1
                chosen_out = chosen
        else:
            chosen_out = chosen

        design_lines.append(
            {
                **line,
                "size_key": size_key,
                "product_name_zh": "单面磨毛纤维桌布",
                "brand": "WIGENIUS",
                "fnsku_lock_key": f"WIGENIUS|{size_key}|{spp}|{line['color']}|单面磨毛纤维桌布",
                "candidates": cands[:5],
                "source_rel": chosen_out if chosen else None,
                "dest_rel": dest_rel,
                "status": status,
            }
        )

    after = inventory(LABEL_SRC)
    after_path = INV_DIR / f"after_C26079_{ts}.json"
    after_path.write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")
    match_ok = same_inv(before, after)
    if match_ok:
        (INV_DIR / "baseline_latest.json").write_text(
            json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (INV_DIR / "last_completed.json").write_text(
            json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        print("CRITICAL: source drifted after copy")

    summary = Counter(l["status"] for l in design_lines)
    design = {
        "order_code": "EF-C26079-C04-36460",
        "rules": "fnsku bidirectional; gram weight ignored for label match",
        "taken_at": now_iso(),
        "summary": dict(summary),
        "lines": design_lines,
    }
    (DEST / "_design_match.json").write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "order_code": ORDER_CODE,
        "label_bundle_dir": f"{ORDER_CODE}标签",
        "layout": "EF订单号标签/{N}条装/{尺寸}/原名.pdf",
        "project_folder": str(PROJ),
        "label_source": str(LABEL_SRC),
        "source_before": {
            "total_files": before["total_files"],
            "by_ext": before["by_ext"],
            "inventory_file": str(before_path),
            "fingerprint": before["fingerprint"],
        },
        "source_after": {
            "total_files": after["total_files"],
            "by_ext": after["by_ext"],
            "inventory_file": str(after_path),
            "fingerprint": after["fingerprint"],
            "match_before": match_ok,
        },
        "copied": copied,
        "summary": dict(summary),
        "ambiguous": ambiguous,
        "missing": missing,
        "lines": [
            {
                "fnsku": l["fnsku"],
                "size": l["size"],
                "color": l["color"],
                "strips_per_pack": l["strips_per_pack"],
                "source_rel": l["source_rel"],
                "dest_rel": l["dest_rel"],
                "status": l["status"],
            }
            for l in design_lines
        ],
    }
    (DEST / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("BEFORE", before["total_files"], before["fingerprint"][:16])
    print("AFTER", after["total_files"], after["fingerprint"][:16], "match_ok", match_ok)
    print("COPIED", copied, "SUMMARY", dict(summary))
    print("AMBIGUOUS", ambiguous)
    print("MISSING", missing)
    return 0 if match_ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
