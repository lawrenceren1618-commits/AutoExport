# -*- coding: utf-8 -*-
"""
16_split_mixed_carton_spec_folders.py

当规格夹外标包规与页内标记不一致（如夹名 6pack，页内同时 126-6 / 126-10），
把多页 PDF **物理拆分**到正确的「同仓×规格」夹（一规格一多页 PDF），
且 **PDF 文件名 = 规格夹名**（含正确箱数）。

沉淀：settled_knowledge_db.json
  → confirmed_defaults.carton_label_channels.page_mark_split_must_rewrite_folders
文档：Templates/Carton_Label_Channels.md

修复识别层 page_mark_split 只改 JSON、不改盘的问题。

用法:
  python Scripts/16_split_mixed_carton_spec_folders.py --project "1_Input_Raw/Shipments/..."
  python Scripts/16_split_mixed_carton_spec_folders.py --project "..." --apply
  python Scripts/16_split_mixed_carton_spec_folders.py --project "..." --apply --only-size 60X126inch --only-color 米白

默认 dry-run。--apply 才写盘；原混装夹改名为 `.mixed_bak_*` 保留。
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Scripts"))

from pypdf import PdfReader, PdfWriter  # noqa: E402

# reuse parsers from 08
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "parse08", ROOT / "Scripts" / "08_parse_fba_carton_labels.py"
)
_mod08 = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod08)

COLOR_FOLDER = {
    "白": "白色",
    "黑": "黑色",
    "蓝": "蓝色",
    "米白": "米白色",
}


def _now_tag() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")


def _size_folder_token(size_norm: str, raw_name: str) -> str:
    """Prefer inches spelling from original folder when present."""
    if re.search(r"60\s*[Xx×＊]\s*126\s*inches?", raw_name, re.I):
        return "60X126inches"
    if re.search(r"60\s*[Xx×＊]\s*102\s*inches?", raw_name, re.I):
        return "60X102inches"
    if "70X120" in size_norm:
        return "70X120inches"
    if "90" in size_norm and "round" in size_norm.lower():
        return "90inches Round"
    # fallback from norm 60X126inch → 60X126inches
    m = re.match(r"(\d+)X(\d+)inch$", size_norm, re.I)
    if m:
        return f"{m.group(1)}X{m.group(2)}inches"
    return size_norm


def _page_spp_list(pdf: Path) -> list[int | None]:
    """Per-page strips_per_pack from marks like 126-6; None if unmarked."""
    reader = PdfReader(str(pdf))
    out: list[int | None] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        found = None
        for m in re.finditer(r"\b(?:84|102|120|126|90)-(2|6|10)\b", t):
            found = int(m.group(1))
            break
        out.append(found)
    return out


def _target_folder_name(color: str, size_token: str, spp: int, cartons: int) -> str:
    color_disp = COLOR_FOLDER.get(color, color if color.endswith("色") else color + "色")
    # C26079 米白用 6pack / 10pack（单数 pack）
    return f"{color_disp} {size_token} {spp}pack-{cartons}箱"


def plan_splits(
    project: Path,
    *,
    only_size: str | None,
    only_color: str | None,
) -> list[dict]:
    fba = project / "FBA外箱贴"
    # support FC/ nested
    roots = []
    fc = fba / "FC"
    if fc.is_dir():
        roots.append(fc)
    roots.append(fba)

    plans: list[dict] = []
    seen_wh: set[str] = set()
    for root in roots:
        for wh in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name):
            if wh.name in ("FC", "AWD", "GWD", "_inbox", "_staging", "_recognize"):
                continue
            if wh.name in seen_wh and root == fba and fc.is_dir():
                continue
            seen_wh.add(wh.name)
            for d in sorted([p for p in wh.iterdir() if p.is_dir()], key=lambda p: p.name):
                if d.name.startswith(".mixed_bak_"):
                    continue
                parsed = _mod08._parse_spec(d.name)
                if only_color and parsed["color"] != only_color:
                    continue
                if only_size and parsed["size"] != only_size:
                    continue
                page_packs = _mod08._page_pack_marks(d)
                folder_cartons = parsed["qty_cartons"]
                pdfs = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]
                if len(page_packs) < 2:
                    continue
                if folder_cartons is None or sum(page_packs.values()) != folder_cartons:
                    continue
                # only act when folder label pack disagrees with multi marks
                if parsed["strips_per_pack"] in page_packs and len(page_packs) == 1:
                    continue
                size_tok = _size_folder_token(parsed["size"], d.name)
                targets = []
                for spp, n in sorted(page_packs.items()):
                    targets.append(
                        {
                            "strips_per_pack": spp,
                            "qty_cartons": n,
                            "folder_name": _target_folder_name(
                                parsed["color"], size_tok, spp, n
                            ),
                        }
                    )
                plans.append(
                    {
                        "warehouse": wh.name,
                        "wh_path": str(wh),
                        "src_folder": d.name,
                        "src_path": str(d),
                        "pdfs": [str(p) for p in pdfs],
                        "page_packs": page_packs,
                        "folder_label_packs": parsed["strips_per_pack"],
                        "targets": targets,
                        "color": parsed["color"],
                        "size": parsed["size"],
                    }
                )
    return plans


def apply_one(plan: dict, *, dry: bool) -> dict:
    src = Path(plan["src_path"])
    wh = Path(plan["wh_path"])
    pdfs = [Path(p) for p in plan["pdfs"]]
    if len(pdfs) != 1:
        return {"ok": False, "error": f"expect 1 pdf, got {len(pdfs)}", "plan": plan}

    pdf = pdfs[0]
    spp_per_page = _page_spp_list(pdf)
    if any(x is None for x in spp_per_page):
        return {"ok": False, "error": "unmarked pages", "pages": spp_per_page}

    buckets: dict[int, list[int]] = defaultdict(list)
    for i, spp in enumerate(spp_per_page):
        assert spp is not None
        buckets[spp].append(i)

    # verify counts
    for t in plan["targets"]:
        spp = t["strips_per_pack"]
        if len(buckets.get(spp, [])) != t["qty_cartons"]:
            return {
                "ok": False,
                "error": "page count mismatch",
                "spp": spp,
                "got": len(buckets.get(spp, [])),
                "want": t["qty_cartons"],
            }

    ops = []
    if dry:
        for t in plan["targets"]:
            ops.append({"create": t["folder_name"], "pages": t["qty_cartons"]})
        return {"ok": True, "dry": True, "ops": ops}

    reader = PdfReader(str(pdf))
    created = []
    for t in plan["targets"]:
        spp = t["strips_per_pack"]
        dest_dir = wh / t["folder_name"]
        if dest_dir.exists():
            return {"ok": False, "error": f"dest exists {dest_dir}"}
        dest_dir.mkdir(parents=True)
        writer = PdfWriter()
        for idx in buckets[spp]:
            writer.add_page(reader.pages[idx])
        out_pdf = dest_dir / f"{t['folder_name']}.pdf"
        with out_pdf.open("wb") as f:
            writer.write(f)
        created.append({"dir": str(dest_dir), "pdf": out_pdf.name})

    bak = wh / f".mixed_bak_{_now_tag()}_{src.name}"
    src.rename(bak)
    return {"ok": True, "dry": False, "created": created, "backup": str(bak)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only-size", default=None, help="e.g. 60X126inch")
    ap.add_argument("--only-color", default=None, help="e.g. 米白")
    ap.add_argument("--out-json", default=None)
    args = ap.parse_args()

    project = Path(args.project)
    if not project.is_absolute():
        project = ROOT / project
    if not project.is_dir():
        print("FAIL missing project", project)
        return 2

    plans = plan_splits(
        project, only_size=args.only_size, only_color=args.only_color
    )
    print(f"mixed_folders={len(plans)} apply={args.apply}")
    results = []
    for p in plans:
        print(
            f"  {p['warehouse']}/{p['src_folder']}  "
            f"label={p['folder_label_packs']} marks={p['page_packs']} → "
            + ", ".join(t["folder_name"] for t in p["targets"])
        )
        r = apply_one(p, dry=not args.apply)
        results.append({"plan": p, "result": r})
        if not r.get("ok"):
            print("    FAIL", r)
        else:
            print("    OK", "dry" if r.get("dry") else r.get("created"))

    report = {
        "project": str(project),
        "apply": args.apply,
        "count": len(plans),
        "results": results,
        "at": _now_tag(),
    }
    out = Path(args.out_json) if args.out_json else (
        ROOT / "2_Processed_AI" / "drafts" / f"split_mixed_carton_{_now_tag()}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out)
    fails = [x for x in results if not x["result"].get("ok")]
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
