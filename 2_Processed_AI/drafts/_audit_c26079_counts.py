# -*- coding: utf-8 -*-
from pathlib import Path
import json
import re

root = Path(r"D:/.cursor/Cursor-projects/AutoExport")
out = next(p for p in (root / "3_Output_Final").iterdir() if "C26079" in p.name)
ship = next(p for p in (root / "1_Input_Raw" / "Shipments").iterdir() if "C26079" in p.name)

WH_RE = re.compile(
    r"\b(AVP1|CLT2|GYR2|LGB8|MDW2|IUTE|ONT8|RDU2|FTW1|SWF2|HEA2|MCC1|TEB9|LAS1|LAX9|SBD1)\b"
)


def wh_from_name(name: str) -> list[str]:
    return WH_RE.findall(name)


report: dict = {
    "output": str(out),
    "ship": str(ship),
    "ship_freight_a": [],
    "ship_freight_b": [],
    "out_freight_a": [],
    "out_freight_b": [],
    "ship_customs": [],
    "out_customs_a": [],
    "out_customs_b": [],
    "ship_fba_wh_dirs": [],
    "pack_a_wh": [],
    "pack_b_files": [],
    "mismatch_notes": [],
}

freight_dir = next(
    p for p in ship.iterdir() if p.is_dir() and "货代" in p.name and "下单" in p.name
)
for f in sorted(freight_dir.iterdir()):
    if not f.is_file():
        continue
    item = {"name": f.name, "wh": wh_from_name(f.name), "size": f.stat().st_size}
    if "C26079-A" in f.name:
        report["ship_freight_a"].append(item)
    elif "C26079-B" in f.name:
        report["ship_freight_b"].append(item)

customs = next((p for p in ship.iterdir() if p.is_dir() and "报关" in p.name), None)
if customs:
    for f in sorted(customs.iterdir()):
        if f.is_file():
            report["ship_customs"].append(
                {"name": f.name, "wh": wh_from_name(f.name), "size": f.stat().st_size}
            )

fba = next(p for p in ship.iterdir() if p.is_dir() and "FBA" in p.name)
report["ship_fba_top"] = sorted(d.name for d in fba.iterdir() if d.is_dir())
# count carton pdfs per WH (exclude bak/inbox/staging/recognize)
for d in sorted(fba.iterdir()):
    if not d.is_dir():
        continue
    if d.name.startswith("_"):
        continue
    pdfs = [
        p
        for p in d.rglob("*.pdf")
        if ".mixed_bak" not in str(p) and p.is_file()
    ]
    # for AWD dig one level
    subdirs = [x.name for x in d.iterdir() if x.is_dir() and not x.name.startswith(".")]
    report["ship_fba_wh_dirs"].append(
        {
            "dir": d.name,
            "subdirs": subdirs,
            "pdf_count_excl_bak": len(pdfs),
        }
    )

arch = next(c for c in out.iterdir() if c.is_dir() and "完整" in c.name)
for leg in sorted(arch.iterdir()):
    if not leg.is_dir():
        continue
    freight = next((p for p in leg.rglob("*") if p.is_dir() and "货代" in p.name and "下单" in p.name), None)
    customs_d = next((p for p in leg.rglob("*") if p.is_dir() and "报关" in p.name), None)
    fba_d = next((p for p in leg.rglob("*") if p.is_dir() and "FBA" in p.name), None)
    entry = {
        "leg": leg.name,
        "freight": [],
        "customs": [],
        "fba_wh": [],
    }
    if freight:
        for f in sorted(freight.iterdir()):
            if f.is_file():
                entry["freight"].append({"name": f.name, "wh": wh_from_name(f.name)})
    if customs_d:
        for f in sorted(customs_d.iterdir()):
            if f.is_file():
                entry["customs"].append({"name": f.name, "wh": wh_from_name(f.name)})
    if fba_d:
        entry["fba_wh"] = sorted(
            d.name for d in fba_d.rglob("*") if d.is_dir() and WH_RE.fullmatch(d.name)
        ) or sorted(
            d.name
            for d in fba_d.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )
    report.setdefault("archive_legs", []).append(entry)
    if "C26079-A" in leg.name:
        report["out_freight_a"] = entry["freight"]
        report["out_customs_a"] = entry["customs"]
    if "C26079-B" in leg.name:
        report["out_freight_b"] = entry["freight"]
        report["out_customs_b"] = entry["customs"]

pack_a = next(c for c in out.iterdir() if c.is_dir() and "C26079-A" in c.name)
report["pack_a_wh"] = sorted(d.name for d in pack_a.iterdir() if d.is_dir())
pack_b = next(c for c in out.iterdir() if c.is_dir() and "C26079-B" in c.name)
report["pack_b_files"] = [
    str(p.relative_to(pack_b)).replace("\\", "/")
    for p in pack_b.rglob("*")
    if p.is_file()
]

# Compare WH sets for A
wh_freight_a = sorted({w for x in report["ship_freight_a"] for w in x["wh"]})
wh_pack_a = report["pack_a_wh"]
wh_customs_a = sorted({w for x in report["ship_customs"] for w in x["wh"] if w != "IUTE"})
# FBA FC-side WH that have carton content
wh_fba_fc = [
    x["dir"]
    for x in report["ship_fba_wh_dirs"]
    if x["dir"] in ("AVP1", "CLT2", "GYR2", "LGB8", "MDW2") and x["pdf_count_excl_bak"] > 0
]

report["compare_A"] = {
    "ship_freight_file_count": len(report["ship_freight_a"]),
    "out_freight_file_count": len(report["out_freight_a"]),
    "ship_customs_file_count": len(report["ship_customs"]),
    "wh_from_ship_freight_A": wh_freight_a,
    "wh_from_pack_A": wh_pack_a,
    "wh_from_ship_customs": sorted({w for x in report["ship_customs"] for w in x["wh"]}),
    "wh_fba_fc_with_pdfs": wh_fba_fc,
    "freight_minus_pack": sorted(set(wh_freight_a) - set(wh_pack_a)),
    "pack_minus_freight": sorted(set(wh_pack_a) - set(wh_freight_a)),
    "customs_minus_freight_A": sorted(
        set(w for x in report["ship_customs"] for w in x["wh"]) - set(wh_freight_a) - {"IUTE"}
    ),
}

# Possible "6 vs 5": customs has 6 including B or template?
report["compare_counts_hypothesis"] = {
    "ship_freight_all_xlsx": len(report["ship_freight_a"]) + len(report["ship_freight_b"]),
    "ship_freight_A_only": len(report["ship_freight_a"]),
    "ship_freight_B_including_pre_media": len(report["ship_freight_b"]),
    "out_archive_freight_A": len(report["out_freight_a"]),
    "out_archive_freight_B": len(report["out_freight_b"]),
    "out_archive_freight_A_plus_B": len(report["out_freight_a"]) + len(report["out_freight_b"]),
    "pack_A_warehouse_count": len(wh_pack_a),
    "ship_customs_count": len(report["ship_customs"]),
}

out_path = root / "2_Processed_AI" / "drafts" / "c26079_count_compare.json"
out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("WROTE", out_path)
print(json.dumps(report["compare_A"], ensure_ascii=False, indent=2))
print(json.dumps(report["compare_counts_hypothesis"], ensure_ascii=False, indent=2))
print("ship_freight_b:", json.dumps(report["ship_freight_b"], ensure_ascii=False, indent=2))
print("ship_customs:", json.dumps(report["ship_customs"], ensure_ascii=False, indent=2))
print("out_freight_a count", len(report["out_freight_a"]))
print("out_customs_a", json.dumps(report["out_customs_a"], ensure_ascii=False, indent=2))
print("archive_legs keys", [x["leg"] for x in report.get("archive_legs", [])])
