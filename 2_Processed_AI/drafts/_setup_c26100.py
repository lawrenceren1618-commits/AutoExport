# -*- coding: utf-8 -*-
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(r"D:\.cursor\Cursor-projects\AutoExport")
sys.path.insert(0, str(ROOT / "Scripts"))

from m1.label_copy import copy_product_labels
from m1.outbound_fill import fill_outbound_template

root = ROOT
TZ = timezone(timedelta(hours=8))

order_code = "EF-C26100-C07-12000"
order_short = "C26100"
entity = "C07"
ship_date = "2026-09-19"
order_date = "2026-08-25"
strips = 12000
cartons = 300
outbound_short = "C07-2611"
yyyymmdd = ship_date.replace("-", "")
folder = f"{order_code}_{entity}_{yyyymmdd}_{strips}"
proj = root / "1_Input_Raw" / "Shipments" / folder

draft = json.loads(
    (root / "2_Processed_AI/drafts/EF-C26100-C07-12000_order_draft.json").read_text(
        encoding="utf-8"
    )
)
lines = draft["assembled"]["lines"]
print("line", lines[0].get("fnsku"), lines[0].get("strips_per_carton"), lines[0].get("qty_strips"))

for sub in [
    "订单表",
    "出货表",
    "货代入库贴下单表",
    "报关资料表",
    "产品标签",
    "FBA外箱贴/_inbox",
    "货代入库贴/_inbox",
    "货代入库贴/_staging",
    "货代入库贴/_recognize",
    "拆单比对",
]:
    (proj / sub).mkdir(parents=True, exist_ok=True)

src_order = root / "2_Processed_AI/drafts" / "EF-C26100-C07-12000  桌布-2026.9.19.xlsx"
dst_order = proj / "订单表" / src_order.name
shutil.copy2(src_order, dst_order)
print("order", dst_order)

lab = copy_product_labels(
    order_code=order_code,
    entity_code=entity,
    lines=lines,
    dest_root=proj / "产品标签",
)
print(
    "labels",
    lab.get("ok"),
    "copied",
    lab.get("copied"),
    "missing",
    lab.get("missing"),
    "ambiguous",
    lab.get("ambiguous"),
)

ob_lines = [
    {
        "size": ln.get("size"),
        "color": ln.get("color"),
        "qty_strips": ln.get("qty_strips"),
        "gram_weight": ln.get("gram_weight"),
        "product_name_zh": ln.get("product_name_zh"),
    }
    for ln in lines
]
ob = fill_outbound_template(
    outbound_short=outbound_short,
    ship_date=ship_date,
    lines=ob_lines,
    out_path=proj / "出货表" / f"{outbound_short}-U-2026.9.19.xlsx",
    order_code=order_code,
    order_short=order_short,
)
print("outbound", ob)

job_id = str(uuid.uuid4())
project = {
    "id": folder,
    "folder_name": folder,
    "order_code": order_code,
    "order_short": order_short,
    "outbound_short": outbound_short,
    "outbound_filename": f"{outbound_short}-U-2026.9.19.xlsx",
    "store": entity,
    "brand": "Dressmaker",
    "order_date": order_date,
    "delivery_date": ship_date,
    "ship_date": ship_date,
    "strips": strips,
    "cartons": cartons,
    "status": "order_labels",
    "gate_final": "WAIT",
    "job_id": job_id,
    "lines": [
        {
            "size": "60X102inch",
            "color": "白",
            "qty_strips": 12000,
            "qty_cartons": 300,
            "strips_per_pack": 10,
            "packs_per_carton": 4,
            "strips_per_carton": 40,
            "fnsku": "X004SJV9UF",
            "gram_weight": "90G",
        }
    ],
    "source_note": "2026-08-25 新开：用户指定 C26100（跳空 C26096–C26099）；10条装 60x102白 300箱；等外箱贴",
}
(proj / "PROJECT.json").write_text(
    json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

oc = json.loads((root / "Scripts/order_code_seq.json").read_text(encoding="utf-8"))
oc["baselines"]["2026"] = {
    "last_allocated_short": "C26100",
    "next_short": "C26101",
    "note": "2026-08-25 用户指定 EF-C26100-C07-12000；C26096–C26099 跳号空置",
}
(root / "Scripts/order_code_seq.json").write_text(
    json.dumps(oc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

osq = json.loads((root / "Scripts/outbound_short_seq.json").read_text(encoding="utf-8"))
osq["baselines"]["2026"]["C07_last"] = "C07-2611"
osq["baselines"]["2026"]["C07_next"] = "C07-2612"
(root / "Scripts/outbound_short_seq.json").write_text(
    json.dumps(osq, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

jobs_path = root / "2_Processed_AI/cloud_job_store/shipment_jobs.json"
jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
jobs["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
jobs["jobs"] = [
    {
        "id": job_id,
        "project_code": folder,
        "entity_code": "C07",
        "ship_date": ship_date,
        "status": "open",
        "gate_final": "WAIT",
        "meta": {
            "order_code": order_code,
            "order_short": order_short,
            "outbound_short": outbound_short,
            "order_delivery_date": ship_date,
            "total_strips": strips,
            "total_cartons": cartons,
            "lines": project["lines"],
        },
        "note": "order+labels+outbound draft; 等外箱贴",
    }
] + (jobs.get("jobs") or [])
jobs_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("project", proj)
print("job", job_id)
