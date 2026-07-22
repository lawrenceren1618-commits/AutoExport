# -*- coding: utf-8 -*-
import json, re, shutil
from pathlib import Path
import xlrd

ORDER_XLS = Path(r"D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26079-C04-36460  桌布-2026.7.10\订单表\EF-C26079-C04-36460  桌布-2026.7.10.xls")
BASELINE = Path(r"D:\.cursor\Cursor-projects\AutoExport\2_Processed_AI\label_source_inventory\baseline_latest.json")
LAST_COMPLETED = Path(r"D:\.cursor\Cursor-projects\AutoExport\2_Processed_AI\label_source_inventory\last_completed.json")
OUT = Path(r"D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26079-C04-36460  桌布-2026.7.10\产品标签\_design_match.json")
ORDER_CODE = "EF-C26079-C04-36460"
ORDER_GRAM = 90
UNRESOLVED_COLORS = {"金", "银", "金色", "银色"}


def normalize_size(raw: str) -> str:
    s = raw.strip().lower().replace(" ", "")
    s = s.replace("*", "x").replace("inch", "")
    if "round" in s or "圆" in raw:
        return "90圆"
    m = re.match(r"(\d+)x(\d+)", s)
    if not m:
        return s
    a, b = m.group(1), m.group(2)
    if a == "60" and b == "102":
        return "6x102"
    return f"{a}x{b}"


def parse_lines():
    sh = xlrd.open_workbook(str(ORDER_XLS)).sheet_by_index(0)
    hdr = next(
        r
        for r in range(sh.nrows)
        if "尺寸规格" in "".join(str(sh.cell_value(r, c)) for c in range(sh.ncols)).replace(" ", "")
        and "条数" in "".join(str(sh.cell_value(r, c)) for c in range(sh.ncols))
    )
    lines = []
    for r in range(hdr + 1, sh.nrows):
        size = str(sh.cell_value(r, 0)).strip()
        if not size or size.startswith("合计"):
            break
        lines.append(
            {
                "size": size,
                "color": str(sh.cell_value(r, 1)).strip(),
                "strips_per_pack": int(float(sh.cell_value(r, 2))),
                "fnsku": str(sh.cell_value(r, 3)).strip(),
                "packs_per_carton": float(sh.cell_value(r, 4)),
                "cartons": float(sh.cell_value(r, 5)),
                "total_strips": float(sh.cell_value(r, 6)),
            }
        )
    return lines


def gram_from_rel(rel: str):
    if "90克" in rel:
        return 90
    if "110克" in rel:
        return 110
    if "150克" in rel:
        return 150
    return None


def strips_folder(rel: str):
    m = re.search(r"/(\d+)条装/", rel)
    return int(m.group(1)) if m else None


def size_in_rel(norm_size: str, rel: str) -> bool:
    rel_l = rel.lower()
    if norm_size == "6x102":
        return "6x102" in rel_l or "60x102" in rel_l
    if norm_size == "90圆":
        return "90圆" in rel
    return norm_size.lower() in rel_l


def color_match(color: str, rel: str) -> tuple[bool, bool]:
    if color in UNRESOLVED_COLORS:
        return False, True
    text = rel
    if color == "米白":
        return any(k in text for k in ("米白", "象牙", "ivory")), False
    if color == "白":
        if any(k in text for k in ("米白", "象牙", "ivory")):
            return False, False
        return ("白" in text and "米白" not in text), False
    if color == "黑":
        return "黑" in text, False
    if color == "蓝":
        return "蓝" in text, False
    return False, False


def score_candidate(line, rel: str) -> int:
    if not rel.startswith("C04-Wigenius"):
        return -1
    if strips_folder(rel) != line["strips_per_pack"]:
        return -1
    if not size_in_rel(normalize_size(line["size"]), rel):
        return -1
    matched, unresolved = color_match(line["color"], rel)
    if unresolved or not matched:
        return -1
    g = gram_from_rel(rel)
    s = 50
    if g == ORDER_GRAM:
        s += 40
    elif g in (110, 150):
        s += 20
    else:
        s += 5
    return s


def line_status(candidates):
    if not candidates:
        return "missing"
    top = candidates[0]["score"]
    if len(candidates) > 1 and candidates[1]["score"] == top:
        return "ambiguous"
    g = gram_from_rel(candidates[0]["rel"])
    if g == ORDER_GRAM:
        return "copied_ready"
    if g in (110, 150):
        return "weight_mismatch"
    return "missing"


def main():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    inventory = [f["rel"] for f in baseline["files"] if f["rel"].startswith("C04-Wigenius")]
    parsed = parse_lines()
    summary = {k: 0 for k in ("copied_ready", "weight_mismatch", "color_unresolved", "missing", "ambiguous")}
    out_lines = []
    for line in parsed:
        if line["color"] in UNRESOLVED_COLORS:
            status = "color_unresolved"
            cands = []
        else:
            cands = [{"rel": rel, "score": sc} for rel in inventory if (sc := score_candidate(line, rel)) >= 0]
            cands.sort(key=lambda x: (-x["score"], x["rel"]))
            cands = cands[:8]
            status = line_status(cands)
        summary[status] += 1
        out_lines.append(
            {
                "fnsku": line["fnsku"],
                "size": line["size"],
                "color": line["color"],
                "strips_per_pack": line["strips_per_pack"],
                "packs_per_carton": line["packs_per_carton"],
                "cartons": line["cartons"],
                "total_strips": line["total_strips"],
                "candidates": cands,
                "status": status,
            }
        )
    doc = {
        "order_code": ORDER_CODE,
        "order_gram_target": ORDER_GRAM,
        "label_scope": "C04-Wigenius",
        "lines": out_lines,
        "summary": summary,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(BASELINE, LAST_COMPLETED)
    print("Summary:", json.dumps(summary, ensure_ascii=False))
    assert len(out_lines) == 23


if __name__ == "__main__":
    main()
