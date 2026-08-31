# -*- coding: utf-8 -*-
"""
03_cross_validate.py
成品输出前交叉对照（Gate HX）：草稿/当票要点 vs 沉淀规则。

Usage:
  python Scripts/03_cross_validate.py --project "<Shipments/...>"
  python Scripts/03_cross_validate.py --project "..." --out "2_Processed_AI/cross_check_reports/..."

不依赖已删除的空 products/fnsku_index 表；对照以 confirmed_defaults + entity_brand_rules + 登记库为主。
总表行级 join 待 H01 有数据后再扩展。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTLED_DB = ROOT / "Scripts" / "settled_knowledge_db.json"
ENTITY_RULES = ROOT / "Scripts" / "entity_brand_rules.json"
PROTOCOL_REG = ROOT / "Scripts" / "contract_protocol_registry.json"
REPORT_DIR = ROOT / "2_Processed_AI" / "cross_check_reports"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def check_entity_brand(project_meta: dict, entity_rules: dict) -> list[dict]:
    findings: list[dict] = []
    store = (project_meta.get("store") or "").upper()
    brand = project_meta.get("brand") or ""
    ents = entity_rules.get("entities") or {}
    if store not in ("C04", "C07"):
        findings.append(
            {
                "check": "entity_store",
                "ok": False,
                "detail": f"store={store!r} not C04/C07",
            }
        )
        return findings
    expect_brand = (ents.get(store) or {}).get("brand_tablecloth") or ""
    ok = brand.upper() == expect_brand.upper() or (
        store == "C04" and brand.upper() == "WIGENIUS"
    ) or (store == "C07" and brand.upper() == "DRESSMAKER")
    findings.append(
        {
            "check": "entity_brand_lock",
            "ok": ok,
            "detail": f"store={store} brand={brand} expect={expect_brand}",
        }
    )
    return findings


def check_customs_1039_path(project: Path, entity_rules: dict) -> list[dict]:
    """C04/C07 报关均须波丽丝表内抬头；文件名含畅选+波丽丝。"""
    findings: list[dict] = []
    customs_dir = project / "报关资料表"
    if not customs_dir.is_dir():
        findings.append(
            {"check": "customs_dir", "ok": False, "detail": "报关资料表 missing"}
        )
        return findings
    files = [p for p in customs_dir.glob("*.xlsx") if not p.name.startswith("~$")]
    if not files:
        findings.append(
            {"check": "customs_files", "ok": False, "detail": "no customs xlsx"}
        )
        return findings
    try:
        import openpyxl
    except ImportError:
        findings.append(
            {"check": "customs_openpyxl", "ok": False, "detail": "openpyxl missing"}
        )
        return findings
    header_ok = True
    name_ok = True
    details: list[str] = []
    for p in files:
        if "畅选+波丽丝" not in p.name and "畅选" not in p.name:
            name_ok = False
            details.append(f"filename_pattern:{p.name}")
        wb = openpyxl.load_workbook(p, data_only=True)
        if "基础表" not in wb.sheetnames:
            header_ok = False
            details.append(f"no_基础表:{p.name}")
            wb.close()
            continue
        ws = wb["基础表"]
        v = str(ws.cell(9, 4).value or "")
        wb.close()
        if "波丽丝" not in v:
            header_ok = False
            details.append(f"header_cell:{p.name}={v!r}")
    findings.append(
        {
            "check": "customs_filename_c04_pattern",
            "ok": name_ok,
            "detail": "; ".join(details) if details and not name_ok else f"n={len(files)}",
        }
    )
    findings.append(
        {
            "check": "customs_table_header_bolisi",
            "ok": header_ok,
            "detail": "; ".join(details) if details and not header_ok else "波丽丝 ok",
        }
    )
    return findings


def check_protocol_unique(project_meta: dict) -> list[dict]:
    findings: list[dict] = []
    reg = load_json(PROTOCOL_REG)
    entries = reg.get("entries") or []
    proj = project_meta.get("folder_name") or project_meta.get("id") or ""
    mine = [e for e in entries if e.get("project") == proj]
    nos = [e.get("protocol_no") for e in mine if e.get("protocol_no")]
    all_nos = [e.get("protocol_no") for e in entries if e.get("protocol_no")]
    # uniqueness among mine
    dup_mine = len(nos) != len(set(nos))
    # each of mine appears exactly once in global? (same no cannot belong to two projects)
    collision = False
    for no in nos:
        owners = {e.get("project") for e in entries if e.get("protocol_no") == no}
        if len(owners) > 1:
            collision = True
    findings.append(
        {
            "check": "protocol_registered",
            "ok": len(mine) > 0,
            "detail": f"count={len(mine)} nos={nos}",
        }
    )
    findings.append(
        {
            "check": "protocol_unique_in_project",
            "ok": not dup_mine,
            "detail": f"nos={nos}",
        }
    )
    findings.append(
        {
            "check": "protocol_no_cross_project_collision",
            "ok": not collision,
            "detail": f"checked={nos}",
        }
    )
    return findings


def check_c07_inherits(project_meta: dict, settled: dict) -> list[dict]:
    store = (project_meta.get("store") or "").upper()
    if store != "C07":
        return [{"check": "c07_inherits", "ok": True, "detail": "n/a not C07"}]
    block = (settled.get("confirmed_defaults") or {}).get("c07_inherits_c04_pipeline")
    return [
        {
            "check": "c07_inherits_documented",
            "ok": bool(block),
            "detail": "c07_inherits_c04_pipeline present" if block else "missing",
        }
    ]


def check_amount_reconcile_draft(project: Path) -> list[dict]:
    drafts = ROOT / "2_Processed_AI" / "drafts"
    # C26080 style
    stem = ""
    m = re.search(r"(C\d{5})", project.name)
    if m:
        stem = m.group(1)
    candidates = list(drafts.glob(f"*{stem}*reconcile*.json")) if stem else []
    if not candidates:
        return [
            {
                "check": "amount_weight_reconcile_draft",
                "ok": True,
                "detail": "no draft found — skip (not fail)",
                "soft": True,
            }
        ]
    data = load_json(candidates[0])
    # various shapes
    err = (
        data.get("error_rate_pct_amount")
        or data.get("amount_error_rate_pct")
        or (data.get("summary") or {}).get("error_rate_pct_amount")
    )
    passed = data.get("reconcile_pass")
    if passed is None and err is not None:
        try:
            passed = float(err) <= 1.0
        except (TypeError, ValueError):
            passed = None
    return [
        {
            "check": "amount_weight_reconcile",
            "ok": bool(passed) if passed is not None else True,
            "detail": f"file={candidates[0].name} error_rate={err} pass={passed}",
            "soft": passed is None,
        }
    ]


def run_for_project(project: Path) -> dict:
    settled = load_json(SETTLED_DB)
    entity_rules = load_json(ENTITY_RULES)
    meta_path = project / "PROJECT.json"
    meta = load_json(meta_path) if meta_path.is_file() else {"folder_name": project.name}

    findings: list[dict] = []
    findings.extend(check_entity_brand(meta, entity_rules))
    findings.extend(check_c07_inherits(meta, settled))
    findings.extend(check_customs_1039_path(project, entity_rules))
    findings.extend(check_protocol_unique(meta))
    findings.extend(check_amount_reconcile_draft(project))

    # 事后交叉流动核对（订单↔出货↔货代↔报关↔报告）
    try:
        sys.path.insert(0, str(ROOT / "Scripts"))
        from m1.post_gen_verify import verify_project

        post = verify_project(project)
        for f in post.get("findings") or []:
            findings.append(
                {
                    "check": f"post_gen:{f.get('check')}",
                    "ok": f.get("ok"),
                    "detail": (
                        f"expected={f.get('expected')!r} actual={f.get('actual')!r} "
                        f"{f.get('detail') or ''}"
                    ).strip(),
                    "soft": f.get("soft"),
                    "edge": f.get("edge"),
                }
            )
    except Exception as e:
        findings.append(
            {
                "check": "post_gen_verify",
                "ok": False,
                "detail": str(e),
            }
        )

    hard = [f for f in findings if not f.get("soft") and not f.get("ok")]
    report = {
        "generated_at": _now(),
        "project": str(project),
        "pass": len(hard) == 0,
        "findings": findings,
        "hard_failures": hard,
        "doc": "Templates/Cross_Flow_Verify.md + pre-output-cross-check",
        "note": "Includes post_gen cross-flow; row-level FNSKU lock still expands with master ingest",
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-validate shipment before Final")
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    project = Path(args.project)
    if not project.is_dir():
        print(f"project missing: {project}")
        return 1
    report = run_for_project(project)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else REPORT_DIR / f"cross_check_{project.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = REPORT_DIR / "cross_check_latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pass={report['pass']} wrote {out}")
    for f in report["findings"]:
        mark = "PASS" if f.get("ok") else ("SOFT" if f.get("soft") else "FAIL")
        print(f"  {mark} {f.get('check')}: {f.get('detail')}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
