# -*- coding: utf-8 -*-
"""Export output packs (copy-only): 完整存档 + 工厂贴标包 + 微信发送 zip.

See Templates/Colleague_Pack_Export.md.

Usage:
  python Scripts/13_export_output_packs.py --project "<Shipments/...>"
  python Scripts/13_export_output_packs.py --project "..." --out "<3_Output_Final/...>"
  python Scripts/13_export_output_packs.py --project "..." --no-zip
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = ROOT / "Scripts" / "freight_forwarder_profiles.json"
SEND_INBOUND_NOTE = "SEND外箱贴已含入库贴.txt"
SEND_INBOUND_NOTE_BODY = (
    "本腿货代为亚马逊 SEND 承运人（如纽酷）。\n"
    "外箱贴 PDF 已从后台下载且已含入库贴，无需单独货代回传入库贴。\n"
    "见 Scripts/freight_forwarder_profiles.json 与 Templates/Freight_Inbound_Label_Pipeline.md §0.1\n"
)

SKIP_NAMES = {
    "_inbox",
    "_staging",
    "_recognize",
    "_PROMOTED",
    "_MERGE",
    "desktop.ini",
    "Thumbs.db",
}
CHANNEL_DIRS = {"FC", "AWD", "GWD"}
WH_DIR_RE = re.compile(r"^[A-Z]{3}\d$|^[A-Z]{4}$")
CARTON_N_RE = re.compile(r"(\d+)\s*箱")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        rel_parts = path.parts
    for part in rel_parts:
        if part in SKIP_NAMES:
            return True
        if part.startswith("_") and part != "_pack_manifest.json":
            return True
        # page_mark_split backups / hidden work folders
        if part.startswith(".mixed_bak_") or (
            part.startswith(".") and part not in {".", ".."}
        ):
            return True
        if part.endswith(".pre_backup") or part.endswith(".bak"):
            return True
    if path.name in SKIP_NAMES:
        return True
    if path.name.startswith("~$"):
        return True
    return False


def copy_tree_filtered(src: Path, dest: Path, *, counts: dict, key: str) -> int:
    n = 0
    if not src.exists():
        return 0
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        counts[key] = counts.get(key, 0) + 1
        return 1
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        if should_skip(p, src):
            continue
        rel = p.relative_to(src)
        if any(
            part in SKIP_NAMES
            or (part.startswith("_") and part != "_pack_manifest.json")
            or part.startswith(".mixed_bak_")
            or (part.startswith(".") and part not in {".", ".."})
            for part in rel.parts[:-1]
        ):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        n += 1
    counts[key] = counts.get(key, 0) + n
    return n


def fba_wh_path(project: Path, channel: str, wh: str) -> Path:
    """Prefer FBA外箱贴/{channel}/{wh}; legacy FC uses FBA外箱贴/{wh}."""
    nested = project / "FBA外箱贴" / channel / wh
    if nested.is_dir() and any(nested.rglob("*.pdf")):
        return nested
    flat = project / "FBA外箱贴" / wh
    if channel == "FC" and flat.is_dir() and any(flat.rglob("*.pdf")):
        return flat
    return nested if nested.is_dir() else flat


def detect_legs(project: Path) -> list[dict]:
    """Channel trees + legacy flat FC warehouses under FBA外箱贴/.

    If PROJECT.json has legs{} (multi FC batches / co-ship), prefer that.
    """
    meta: dict = {}
    proj_meta = project / "PROJECT.json"
    if proj_meta.is_file():
        try:
            meta = json.loads(proj_meta.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    # Additive: explicit multi-leg map (e.g. two FC legs C26080-A/B)
    legs_meta = meta.get("legs")
    if isinstance(legs_meta, dict) and legs_meta:
        legs: list[dict] = []
        for leg_id, info in legs_meta.items():
            if not isinstance(info, dict):
                continue
            whs = info.get("warehouses") or []
            if not whs:
                continue
            ch = str(info.get("channel") or "FC").upper()
            legs.append(
                {
                    "folder": f"{leg_id}_{ch}",
                    "channel": ch,
                    "warehouses": list(whs),
                    "fba_subdir": ch,
                }
            )
        if legs:
            return legs

    fba = project / "FBA外箱贴"
    channel_map: dict[str, list[str]] = {c: [] for c in CHANNEL_DIRS}
    if not fba.is_dir():
        return []

    for child in sorted(fba.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        name = child.name.upper()
        if name in CHANNEL_DIRS:
            for wh_dir in sorted(child.iterdir()):
                if wh_dir.is_dir() and not wh_dir.name.startswith("_"):
                    if any(wh_dir.rglob("*.pdf")):
                        channel_map[name].append(wh_dir.name)
        elif WH_DIR_RE.match(name):
            if any(child.rglob("*.pdf")):
                channel_map["FC"].append(child.name)

    order_stem = meta.get("split_order_stem") or ""
    if not order_stem:
        oc = meta.get("order_code") or project.name
        m = re.search(r"(C\d{5})", oc)
        order_stem = m.group(1) if m else "LEG"

    leg_names = {
        "FC": f"{order_stem}-A_FC",
        "AWD": f"{order_stem}-B_AWD",
        "GWD": f"{order_stem}-GWD",
    }

    legs = []
    for ch in ("FC", "AWD", "GWD"):
        warehouses = channel_map.get(ch) or []
        if not warehouses:
            continue
        entry: dict = {
            "folder": leg_names[ch],
            "channel": ch,
            "warehouses": warehouses,
            "fba_subdir": ch,
        }
        awd = meta.get("awd_leg_B") or {}
        if ch == "AWD" and awd.get("shipment_id"):
            entry["shipment_id"] = awd["shipment_id"]
        legs.append(entry)
    return legs


def _load_freight_profiles() -> dict:
    if not PROFILES_PATH.is_file():
        return {}
    try:
        return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _freight_forwarder_for_leg(project: Path, meta: dict, leg_id: str) -> str | None:
    legs_meta = meta.get("split_legs") or {}
    if leg_id in legs_meta:
        ff = legs_meta[leg_id].get("freight_forwarder")
        if ff:
            return str(ff)
    ledger_path = meta.get("split_ledger") or ""
    ledger_file = Path(ledger_path) if ledger_path else project / "拆单比对" / "split_ledger.json"
    if ledger_file.is_file():
        try:
            ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
            for b in ledger.get("batches") or []:
                if b.get("split_leg_id") == leg_id:
                    return b.get("freight_forwarder")
        except Exception:
            pass
    return None


def _leg_skips_separate_inbound(project: Path, meta: dict, leg_id: str) -> bool:
    profiles = _load_freight_profiles()
    ff = _freight_forwarder_for_leg(project, meta, leg_id)
    if not ff:
        return False
    prof = (profiles.get("forwarders") or {}).get(ff) or {}
    return prof.get("inbound_label_mode") == "send_embedded_in_carton"


def _write_send_inbound_note(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / SEND_INBOUND_NOTE).write_text(SEND_INBOUND_NOTE_BODY, encoding="utf-8")


def collect_inbound_pdfs(project: Path, channel: str, wh: str) -> list[Path]:
    found: list[Path] = []
    wh_dir = fba_wh_path(project, channel, wh)
    if wh_dir.is_dir():
        for p in wh_dir.glob("*入库贴*.pdf"):
            found.append(p)
    inbound = project / "货代入库贴"
    if inbound.is_dir():
        for p in inbound.rglob("*入库贴*.pdf"):
            if any(part in SKIP_NAMES for part in p.parts):
                continue
            if wh.upper() in str(p).upper():
                found.append(p)
    return list(dict.fromkeys(found))


def ship_date_dot(iso_or_any: str) -> str:
    """2026-07-31 / 2026.07.31 / 2026.7.31 → 2026.7.31 (project folder style)."""
    s = (iso_or_any or "").strip()
    m = re.match(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})", s)
    if m:
        return f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"
    return s.replace("-", ".") if s else "TBD"


def _load_project_meta(project: Path) -> dict:
    meta_path = project / "PROJECT.json"
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _leg_id_from_folder(folder: str) -> str:
    """C26079-A_FC → C26079-A；LEG_FC → LEG_FC."""
    if "_" in folder:
        ch = folder.rsplit("_", 1)[-1]
        if ch in CHANNEL_DIRS:
            return folder[: -(len(ch) + 1)]
    return folder


def _strips_by_leg(project: Path, meta: dict) -> tuple[str, dict[str, int]]:
    stem = meta.get("split_order_stem") or ""
    if not stem:
        m = re.search(r"(C\d{5})", meta.get("order_code") or project.name)
        stem = m.group(1) if m else "BATCH"
    strips_by_leg: dict[str, int] = {}
    ledger_path = meta.get("split_ledger") or ""
    ledger_file = Path(ledger_path) if ledger_path else project / "拆单比对" / "split_ledger.json"
    if ledger_file.is_file():
        try:
            ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
            for b in ledger.get("batches") or []:
                lid = b.get("split_leg_id") or ""
                if lid:
                    strips_by_leg[lid] = int(b.get("shipped_strips") or 0)
        except Exception:
            pass
    if not strips_by_leg:
        drafts = ROOT / "2_Processed_AI" / "drafts"
        for p in drafts.glob("*freight_customs_summary.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                lid = data.get("split_leg_id") or ""
                total = sum(int(r.get("strips") or 0) for r in data.get("files") or [])
                if lid and total:
                    strips_by_leg[lid] = total
            except Exception:
                pass
    return stem, strips_by_leg


def factory_pack_dirname_for_leg(
    project: Path, leg: dict, meta: dict, ship_dot: str
) -> tuple[str, int, str]:
    """Return (dirname, strips, batch_id) for one leg's 贴标包."""
    leg_id = _leg_id_from_folder(leg["folder"])
    _stem, strips_map = _strips_by_leg(project, meta)
    strips = int(strips_map.get(leg_id) or 0)
    if strips <= 0:
        drafts = ROOT / "2_Processed_AI" / "drafts"
        for p in drafts.glob("*freight_customs_summary.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("split_leg_id") == leg_id:
                    strips = sum(int(r.get("strips") or 0) for r in data.get("files") or [])
                    break
            except Exception:
                pass
    return f"{leg_id}_{strips}_{ship_dot}_贴标包", strips, leg_id


def copy_factory_warehouse(
    project: Path,
    *,
    factory: Path,
    factory_name: str,
    channel: str,
    wh: str,
    flat_single_wh: bool,
    counts: dict,
    missing: list[str],
    inbound_skipped_send: list[str] | None = None,
    skip_separate_inbound: bool = False,
) -> None:
    """Copy carton + inbound labels for one warehouse into a per-leg factory pack.

    Single WH: 外箱贴_{仓}/ + 入库贴_{仓}/ under pack root.
    Multi WH:  {仓}/外箱贴/ + {仓}/入库贴/  (leg already in pack folder name).
    """
    if flat_single_wh:
        carton_out = factory / f"外箱贴_{wh}"
        inbound_out = factory / f"入库贴_{wh}"
        miss_carton = f"{factory_name}/外箱贴_{wh}"
        miss_inbound = f"{factory_name}/入库贴_{wh}"
    else:
        carton_out = factory / wh / "外箱贴"
        inbound_out = factory / wh / "入库贴"
        miss_carton = f"{factory_name}/{wh}/外箱贴"
        miss_inbound = f"{factory_name}/{wh}/入库贴"

    carton_out.mkdir(parents=True, exist_ok=True)
    inbound_out.mkdir(parents=True, exist_ok=True)

    wh_src = fba_wh_path(project, channel, wh)
    if wh_src.is_dir():
        for p in wh_src.rglob("*.pdf"):
            if should_skip(p, wh_src):
                continue
            if "入库贴" in p.name:
                shutil.copy2(p, inbound_out / p.name)
                counts["factory_inbound"] = counts.get("factory_inbound", 0) + 1
            else:
                rel = p.relative_to(wh_src)
                target = carton_out / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
                counts["factory_carton"] = counts.get("factory_carton", 0) + 1
    else:
        missing.append(miss_carton)

    if not any(inbound_out.glob("*.pdf")):
        for pdf in collect_inbound_pdfs(project, channel, wh):
            shutil.copy2(pdf, inbound_out / pdf.name)
            counts["factory_inbound"] = counts.get("factory_inbound", 0) + 1
        if not any(inbound_out.glob("*.pdf")):
            if skip_separate_inbound:
                _write_send_inbound_note(inbound_out)
                if inbound_skipped_send is not None:
                    inbound_skipped_send.append(miss_inbound)
            else:
                missing.append(miss_inbound)


def _order_short(project: Path, meta: dict, factory_packs_meta: list[dict]) -> str:
    stem, _ = _strips_by_leg(project, meta)
    if stem and stem != "BATCH":
        return stem
    for p in factory_packs_meta:
        m = re.match(r"(C\d{5})", p.get("folder") or "")
        if m:
            return m.group(1)
    m = re.search(r"(C\d{5})", meta.get("order_code") or project.name)
    return m.group(1) if m else "BATCH"


def _pack_carton_count(dirs: list[Path]) -> int:
    """Sum formal carton PDFs. Inbound PDFs also end in N箱 and must not be added again."""
    total = 0
    for top in dirs:
        for f in top.rglob("*.pdf"):
            if "入库贴" in f.name:
                continue
            m = CARTON_N_RE.search(f.name)
            if m:
                total += int(m.group(1))
    return total


def wechat_zip_name(order_short: str, cartons: int) -> str:
    """短号_箱数_外箱贴入库贴.zip，例 C26114_290箱_外箱贴入库贴.zip"""
    return f"{order_short}_{cartons}箱_外箱贴入库贴.zip"


def build_wechat_zip(
    out_root: Path,
    *,
    order_short: str,
    cartons: int,
    factory_folders: list[str],
    ship_dot: str = "",
) -> dict:
    """Merge same-batch leg 贴标包 only into one WeChat zip (no 完整存档)."""
    del ship_dot
    zip_name = wechat_zip_name(order_short, cartons)
    zip_path = out_root / zip_name
    for pattern in ("*微信发送.zip", "*外箱贴入库贴.zip"):
        for old in out_root.glob(pattern):
            if old.resolve() != zip_path.resolve():
                old.unlink()
    if zip_path.exists():
        zip_path.unlink()

    include_dirs: list[Path] = []
    for name in factory_folders:
        p = out_root / name
        if p.is_dir():
            include_dirs.append(p)

    zip_stem = zip_name[:-4]
    single = len(include_dirs) == 1
    members = 0
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for top in include_dirs:
            for f in top.rglob("*"):
                if not f.is_file():
                    continue
                if should_skip(f, out_root):
                    continue
                rel = f.relative_to(top).as_posix()
                if single:
                    arcname = f"{zip_stem}/{rel}"
                else:
                    arcname = f"{top.name}/{rel}"
                zf.write(f, arcname)
                members += 1

    return {
        "file": zip_name,
        "path": str(zip_path),
        "bytes": zip_path.stat().st_size if zip_path.is_file() else 0,
        "members": members,
        "included_tops": [p.name for p in include_dirs],
        "excluded_tops": ["完整存档"],
        "rule": "same-batch 贴标包 only for WeChat; 完整存档 not included",
    }


def export_packs(project: Path, out_root: Path, *, make_zip: bool = True) -> dict:
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    legs = detect_legs(project)
    meta = _load_project_meta(project)
    ship = meta.get("ship_date") or meta.get("delivery_date") or ""
    if not ship:
        m = re.search(r"(\d{4}\.\d{1,2}\.\d{1,2})", project.name)
        ship = m.group(1) if m else "TBD"
    ship_dot = ship_date_dot(ship)

    archive = out_root / "完整存档"
    archive.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    missing: list[str] = []
    inbound_skipped_send: list[str] = []
    factory_packs_meta: list[dict] = []

    shared = archive / "共用"
    for folder, key in [
        ("订单表", "shared_order"),
        ("出货表", "shared_outbound"),
        ("产品标签", "shared_labels"),
    ]:
        src = project / folder
        if src.exists():
            copy_tree_filtered(src, shared / folder, counts=counts, key=key)
        else:
            missing.append(f"共用/{folder}")

    for leg in legs:
        leg_folder = leg["folder"]
        channel = leg["channel"]
        leg_id = _leg_id_from_folder(leg_folder)
        skip_inbound = _leg_skips_separate_inbound(project, meta, leg_id)
        arch_leg = archive / leg_folder
        arch_leg.mkdir(parents=True, exist_ok=True)

        freight_src = project / "货代入库贴下单表"
        customs_src = project / "报关资料表"
        freight_dest = arch_leg / "货代入库贴下单表"
        customs_dest = arch_leg / "报关资料表"
        freight_dest.mkdir(parents=True, exist_ok=True)
        customs_dest.mkdir(parents=True, exist_ok=True)

        if freight_src.is_dir():
            for x in freight_src.glob("*.xlsx"):
                if x.name.startswith("~$") or ".pre_" in x.name:
                    continue
                name_u = x.stem.upper()
                if channel == "AWD" and "AWD" not in name_u and "IUTE" not in name_u:
                    if not any(w.upper() in name_u for w in leg["warehouses"]):
                        continue
                if channel == "FC" and ("AWD" in name_u or "IUTE" in name_u):
                    continue
                if channel == "FC" and "-B " in x.stem:
                    continue
                shutil.copy2(x, freight_dest / x.name)
                counts["archive_freight"] = counts.get("archive_freight", 0) + 1

        if customs_src.is_dir():
            for x in customs_src.glob("*.xlsx"):
                if x.name.startswith("~$"):
                    continue
                name_u = x.stem.upper()
                if channel == "AWD":
                    if "AWD" not in name_u and "IUTE" not in name_u and "C26079-B" not in x.stem:
                        if not any(w.upper() in name_u for w in leg["warehouses"]):
                            continue
                if channel == "FC" and ("AWD" in name_u or "IUTE" in name_u):
                    continue
                if channel == "FC" and "-B " in x.stem:
                    continue
                shutil.copy2(x, customs_dest / x.name)
                counts["archive_customs"] = counts.get("archive_customs", 0) + 1

        labels_dest = arch_leg / "外箱贴"
        labels_dest.mkdir(parents=True, exist_ok=True)
        carton_n = 0
        for wh in leg["warehouses"]:
            wh_src = fba_wh_path(project, channel, wh)
            if not wh_src.is_dir():
                missing.append(f"{leg_folder}/外箱贴/{wh}")
                continue
            carton_n += copy_tree_filtered(
                wh_src, labels_dest / wh, counts=counts, key="archive_carton"
            )
        if carton_n == 0 and not leg["warehouses"]:
            missing.append(f"{leg_folder}/外箱贴")

        inbound_dest = arch_leg / "货代入库贴"
        inbound_dest.mkdir(parents=True, exist_ok=True)
        for wh in leg["warehouses"]:
            pdfs = collect_inbound_pdfs(project, channel, wh)
            wh_dir = inbound_dest / wh
            if not pdfs:
                if skip_inbound:
                    _write_send_inbound_note(wh_dir)
                    inbound_skipped_send.append(f"{leg_folder}/货代入库贴/{wh}")
                else:
                    missing.append(f"{leg_folder}/货代入库贴/{wh}")
                continue
            wh_dir.mkdir(parents=True, exist_ok=True)
            for pdf in pdfs:
                shutil.copy2(pdf, wh_dir / pdf.name)
                counts["archive_inbound"] = counts.get("archive_inbound", 0) + 1

        # One 贴标包 per leg; flat when this leg has exactly one warehouse
        factory_name, strips, batch_id = factory_pack_dirname_for_leg(
            project, leg, meta, ship_dot
        )
        factory = out_root / factory_name
        factory.mkdir(parents=True, exist_ok=True)
        whs = list(leg["warehouses"])
        flat_single_wh = len(whs) == 1
        for wh in whs:
            copy_factory_warehouse(
                project,
                factory=factory,
                factory_name=factory_name,
                channel=channel,
                wh=wh,
                flat_single_wh=flat_single_wh,
                counts=counts,
                missing=missing,
                inbound_skipped_send=inbound_skipped_send,
                skip_separate_inbound=skip_inbound,
            )
        factory_packs_meta.append(
            {
                "folder": factory_name,
                "batch": batch_id,
                "strips": strips,
                "ship_date": ship_dot,
                "layout": "flat_single_wh" if flat_single_wh else "wh_nested",
                "warehouses": whs,
                "channel": channel,
                "inbound_skipped_send": skip_inbound,
                "freight_forwarder": _freight_forwarder_for_leg(project, meta, batch_id),
            }
        )

    for bad in out_root.rglob("*.pre_*"):
        try:
            bad.unlink()
        except OSError:
            pass

    wechat_zip = None
    if make_zip:
        factory_folders = [p["folder"] for p in factory_packs_meta]
        include_dirs = [out_root / name for name in factory_folders if (out_root / name).is_dir()]
        wechat_zip = build_wechat_zip(
            out_root,
            order_short=_order_short(project, meta, factory_packs_meta),
            cartons=_pack_carton_count(include_dirs),
            factory_folders=factory_folders,
        )

    manifest = {
        "kind": "output_packs",
        "generated_at": _now(),
        "rule": "Templates/Colleague_Pack_Export.md",
        "project": project.name,
        "pack_root": str(out_root),
        "packs": {
            "archive": "完整存档",
            "factory_label_kits": [p["folder"] for p in factory_packs_meta],
            "factory_naming": "{split_leg_id}_{actual_strips}_{ship_date}_贴标包",
            "factory_one_pack_per_leg": True,
            "wechat_send_zip": (wechat_zip or {}).get("file"),
        },
        "factory_packs": factory_packs_meta,
        "wechat_send": wechat_zip,
        "legs": legs,
        "counts": counts,
        "missing": missing,
        "inbound_skipped_send": inbound_skipped_send,
        "note": "copy-only; SEND legs skip separate inbound (see freight_forwarder_profiles.json)",
    }
    (out_root / "_pack_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export 完整存档 + per-leg 贴标包 + optional WeChat merge zip"
    )
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default="", help="Default: 3_Output_Final/{project.name}")
    ap.add_argument(
        "--zip",
        dest="make_zip",
        action="store_true",
        default=True,
        help="Merge same-batch packs into {短号}_{箱数}箱_外箱贴入库贴.zip (default)",
    )
    ap.add_argument(
        "--no-zip",
        dest="make_zip",
        action="store_false",
        help="Skip WeChat zip; keep folders only",
    )
    args = ap.parse_args()
    project = Path(args.project)
    if not project.is_dir():
        print(f"project missing: {project}", file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else ROOT / "3_Output_Final" / project.name
    manifest = export_packs(project, out, make_zip=args.make_zip)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
