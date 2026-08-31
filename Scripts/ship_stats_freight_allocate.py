# -*- coding: utf-8 -*-
"""
发货统计 · 头程运费分摊（只读审计 + 可选 JSON 报告）

规则：Templates/Ship_Stats_Freight_Allocation.md
尺寸：Scripts/ship_stats_size_dims.json
源表：1_Input_Raw/00_Master_Reference/发货统计/_inbox/2026年发货记录.xls

默认 --dry-run：不写表，仅输出报告到 2_Processed_AI/cross_check_reports/
"""
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "1_Input_Raw/00_Master_Reference/发货统计/_inbox"
XLS = INBOX / "2026年发货记录.xls"
DIMS_PATH = ROOT / "Scripts/ship_stats_size_dims.json"
SETTLED_PATH = ROOT / "Scripts/settled_knowledge_db.json"
REPORT_DIR = ROOT / "2_Processed_AI/cross_check_reports"

COL_GIVE, COL_GSM, COL_SPEC, COL_SIZE = 2, 3, 4, 5
COL_CARTONS, COL_CHANNEL, COL_FREIGHT, COL_PACK = 7, 8, 10, 12

NIUKU_KW = ("纽酷", "纽台", "SEND", "后台扣款")
COLOR_SUFFIX = ("米白", "象牙白", "象牙", "白", "黑", "蓝", "灰", "绿", "粉", "红", "紫", "黄", "橙", "棕")


@dataclass
class SpecLine:
    row_idx: int
    spec: str
    size: str
    gsm: float | None
    cartons: float
    pack_per_ctn: float | None
    channel: str
    freight_share: float | None = None
    pack_weight_kg: float | None = None
    pack_freight: float | None = None
    issues: list[str] = field(default_factory=list)


@dataclass
class Batch:
    ticket: str
    give: str
    channel: str
    freight_total: float | None
    lines: list[SpecLine] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_num(val) -> float | None:
    if val == "" or val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    if re.match(r"^[\d.]+$", s):
        return float(s)
    if re.match(r"^[\d.]+\+[\d.]+$", s):
        return sum(float(x) for x in s.split("+"))
    return None


def parse_size_color(size: str) -> tuple[str, str]:
    s = str(size).strip()
    if not s:
        return "", ""
    m = re.match(r"^(90圆|60圆)(.*)$", s)
    if m:
        return m.group(1), m.group(2).strip() or "白"
    m = re.match(r"^(84|102|126|120)(.*)$", s)
    if m:
        return m.group(1), m.group(2).strip() or "白"
    return s, ""


def order_full(short: str, dims: dict) -> str | None:
    entry = dims.get("short_to_dims", {}).get(short)
    return entry.get("order_full") if entry else None


def piece_weight_kg(gsm: float, short: str, dims_cfg: dict) -> float | None:
    entry = dims_cfg.get("short_to_dims", {}).get(short)
    if not entry:
        return None
    shape = entry.get("shape")
    gsm_f = float(gsm)
    if shape == "rect":
        l_in = entry["length_inch"]
        w_in = entry["width_inch"]
        area_m2 = (l_in * 0.0254) * (w_in * 0.0254)
    elif shape == "round":
        d_in = entry["diameter_inch"]
        r_m = (d_in * 0.0254) / 2
        area_m2 = math.pi * r_m * r_m
    else:
        return None
    return gsm_f * area_m2 / 1000.0  # g → kg per piece


def pack_weight_kg(gsm: float, short: str, strips: int, dims_cfg: dict) -> float | None:
    pw = piece_weight_kg(gsm, short, dims_cfg)
    if pw is None:
        return None
    return pw * strips


def lookup_ppc(settled: dict, strips: int, short: str, color: str, gsm: float | None) -> int | None:
    """沉淀库 packing_standards；同尺寸+条/包+克重+颜色 → 包/箱。"""
    full = order_full(short, settled) or order_full(short, {"short_to_dims": load_json(DIMS_PATH)})
    if not full:
        return None
    gw = f"{int(gsm)}G" if gsm else "90G"
    matches = []
    for row in settled.get("packing_standards", []):
        if row.get("strips_per_pack") != strips:
            continue
        if row.get("size") != full:
            continue
        if row.get("gram_weight", "90G") != gw and gw not in ("90G", "110G"):
            continue
        if row.get("color") == color:
            matches.append(row["packs_per_carton"])
    if matches:
        return matches[0]
    # 同尺寸同条/包：颜色不影响箱规
    generic = []
    for row in settled.get("packing_standards", []):
        if row.get("strips_per_pack") == strips and row.get("size") == full:
            if gsm and row.get("gram_weight", "90G") not in (gw, "90G", "110G"):
                continue
            generic.append(row["packs_per_carton"])
    uniq = sorted(set(generic))
    return uniq[0] if len(uniq) == 1 else None


def is_niuku(channel: str) -> bool:
    return any(k in str(channel) for k in NIUKU_KW)


def extract_ticket(give: str) -> str:
    m = re.search(r"(C26\d{2,}[A-Z]?)", str(give))
    return m.group(1) if m else ""


def read_batches(xls_path: Path) -> list[Batch]:
    sh = xlrd.open_workbook(str(xls_path)).sheet_by_index(0)
    batches: list[Batch] = []
    current: Batch | None = None
    spec_carry = ""
    gsm_carry: float | None = None

    for r in range(2, sh.nrows):
        give_raw = sh.cell_value(r, COL_GIVE)
        give = str(give_raw).strip() if give_raw else ""
        spec_raw = str(sh.cell_value(r, COL_SPEC)).strip()
        size = str(sh.cell_value(r, COL_SIZE)).strip()
        cartons = parse_num(sh.cell_value(r, COL_CARTONS))
        channel = str(sh.cell_value(r, COL_CHANNEL)).strip()
        freight = parse_num(sh.cell_value(r, COL_FREIGHT))
        ppc = parse_num(sh.cell_value(r, COL_PACK))
        gsm_val = parse_num(sh.cell_value(r, COL_GSM))

        if not any([give, spec_raw, size, cartons]):
            continue

        if give:
            ticket = extract_ticket(give)
            if current and current.lines:
                batches.append(current)
            current = Batch(
                ticket=ticket,
                give=give,
                channel=channel,
                freight_total=freight if freight is not None else None,
            )
            spec_carry = ""
            gsm_carry = None

        if current is None:
            continue

        if channel and not current.channel:
            current.channel = channel
        if freight is not None and current.freight_total is None:
            current.freight_total = freight

        if spec_raw:
            spec_carry = spec_raw
        if gsm_val is not None:
            gsm_carry = gsm_val

        if not size or cartons is None:
            continue

        strips = int(float(spec_carry)) if spec_carry.isdigit() else None
        line = SpecLine(
            row_idx=r,
            spec=spec_carry,
            size=size,
            gsm=gsm_carry,
            cartons=cartons,
            pack_per_ctn=ppc,
            channel=current.channel,
        )
        if strips is None:
            line.issues.append("spec_not_digit")
        current.lines.append(line)

    if current and current.lines:
        batches.append(current)
    return batches


def allocate_batch(batch: Batch, dims_cfg: dict, settled: dict) -> None:
    if is_niuku(batch.channel):
        batch.freight_total = batch.freight_total or 0.0
        for line in batch.lines:
            line.pack_freight = 0.0
        return

    if batch.freight_total is None or batch.freight_total <= 0:
        batch.issues.append("freight_missing_or_zero")
        return

    total_pack_kg = 0.0
    for line in batch.lines:
        if not line.spec.isdigit():
            line.issues.append("bad_spec")
            continue
        strips = int(line.spec)
        short, color = parse_size_color(line.size)
        if line.pack_per_ctn is None:
            if line.gsm:
                ppc = lookup_ppc(settled, strips, short, color, line.gsm)
                if ppc:
                    line.pack_per_ctn = float(ppc)
                    line.issues.append("ppc_from_settled")
                else:
                    line.issues.append("pack_per_ctn_missing")
                    continue
            else:
                line.issues.append("pack_per_ctn_missing")
                continue
        if line.gsm is None:
            line.issues.append("gsm_missing")
            continue
        pw = pack_weight_kg(line.gsm, short, strips, dims_cfg)
        if pw is None:
            line.issues.append("size_not_in_dims")
            continue
        line.pack_weight_kg = pw
        n_packs = line.cartons * line.pack_per_ctn
        total_pack_kg += n_packs * pw

    if total_pack_kg <= 0:
        batch.issues.append("total_pack_weight_zero")
        return

    rate = batch.freight_total / total_pack_kg
    for line in batch.lines:
        if line.pack_weight_kg is None:
            continue
        line.pack_freight = round(rate * line.pack_weight_kg, 4)


def build_report(batches: list[Batch]) -> dict:
    out_batches = []
    blockers = []
    for b in batches:
        if not b.ticket.startswith("C26"):
            continue
        total_packs = 0.0
        lines_out = []
        for ln in b.lines:
            ppc = ln.pack_per_ctn or 0
            n_packs = ln.cartons * ppc if ppc else None
            if n_packs:
                total_packs += n_packs
            lines_out.append(
                {
                    "row": ln.row_idx,
                    "spec": ln.spec,
                    "size": ln.size,
                    "cartons": ln.cartons,
                    "pack_per_ctn": ln.pack_per_ctn,
                    "packs": n_packs,
                    "pack_weight_kg": ln.pack_weight_kg,
                    "pack_freight_yuan": ln.pack_freight,
                    "issues": ln.issues,
                }
            )
        if b.issues:
            blockers.extend([f"{b.ticket}:{x}" for x in b.issues])
        for ln in b.lines:
            blockers.extend([f"{b.ticket}:row{ln.row_idx}:{x}" for x in ln.issues if x not in ("ppc_from_settled",)])

        out_batches.append(
            {
                "ticket": b.ticket,
                "give": b.give.split("\n")[0],
                "channel": b.channel,
                "freight_total": b.freight_total,
                "total_packs": total_packs or None,
                "batch_issues": b.issues,
                "lines": lines_out,
            }
        )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(XLS),
        "rule": "Templates/Ship_Stats_Freight_Allocation.md",
        "batches": out_batches,
        "blockers": sorted(set(blockers)),
        "ready": len(blockers) == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Ship stats head freight allocation audit")
    ap.add_argument("--xls", type=Path, default=XLS)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--ticket", type=str, default=None, help="Only report one ticket e.g. C26095")
    args = ap.parse_args()

    if not args.xls.exists():
        print(f"missing {args.xls}")
        return 1

    dims_cfg = load_json(DIMS_PATH)
    settled = load_json(SETTLED_PATH)
    batches = read_batches(args.xls)
    if args.ticket:
        batches = [b for b in batches if b.ticket.startswith(args.ticket)]

    for b in batches:
        allocate_batch(b, dims_cfg, settled)

    report = build_report(batches)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.out or (REPORT_DIR / f"ship_stats_freight_allocate_{ts}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"report: {out_path}")
    print(f"batches: {len(report['batches'])} blockers: {len(report['blockers'])} ready: {report['ready']}")
    if report["blockers"]:
        for b in report["blockers"][:30]:
            print(" ", b)
        if len(report["blockers"]) > 30:
            print(f"  ... +{len(report['blockers']) - 30} more")
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
