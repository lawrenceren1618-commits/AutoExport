# -*- coding: utf-8 -*-
"""事后交叉核对 CLI。

Usage:
  python Scripts/20_post_gen_verify.py --project "1_Input_Raw/Shipments/<夹>"
  python Scripts/20_post_gen_verify.py --work-dir <job work> --job-json <job.json>
  python Scripts/20_post_gen_verify.py --xlsx <出货.xlsx> --order-code EF-... --outbound-short C04-2616 --ship-date 2026-07-31
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Scripts"))

from m1.post_gen_verify import (  # noqa: E402
    verify_gen_trio_artifacts,
    verify_labels_dir,
    verify_order_artifact,
    verify_outbound_file,
    verify_outbound_xlsx,
    verify_project,
    verify_project_outbound,
    write_report,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-flow post-gen verify")
    ap.add_argument("--project", default="")
    ap.add_argument("--work-dir", default="")
    ap.add_argument("--job-json", default="")
    ap.add_argument("--xlsx", default="")
    ap.add_argument("--order-code", default="")
    ap.add_argument("--order-short", default="")
    ap.add_argument("--outbound-short", default="")
    ap.add_argument("--ship-date", default="")
    ap.add_argument("--store", default="")
    ap.add_argument("--brand", default="")
    ap.add_argument("--strips", type=float, default=None)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.project:
        report = verify_project(Path(args.project))
    elif args.work_dir and args.job_json:
        job = json.loads(Path(args.job_json).read_text(encoding="utf-8-sig"))
        report = verify_gen_trio_artifacts(Path(args.work_dir), job)
    elif args.xlsx:
        report = verify_outbound_file(
            Path(args.xlsx),
            order_code=args.order_code or None,
            order_short=args.order_short or None,
            outbound_short=args.outbound_short or None,
            ship_date=args.ship_date or None,
            store=args.store or None,
            brand=args.brand or None,
            strips=args.strips,
        )
    else:
        ap.print_help()
        return 2

    out = Path(args.out) if args.out else None
    path = write_report(report, out)
    print(f"pass={report['pass']} wrote {path}")
    for f in report["findings"]:
        if f.get("ok"):
            mark = "SOFT" if f.get("soft") else "PASS"
        else:
            mark = "SOFT-FAIL" if f.get("soft") else "FAIL"
        exp = f.get("expected")
        act = f.get("actual")
        extra = ""
        if exp is not None or act is not None:
            extra = f" expected={exp!r} actual={act!r}"
        print(f"  {mark} {f.get('check')}:{extra} {f.get('detail') or ''}")
    if report.get("hard_failures"):
        print("--- hard_failures ---")
        for f in report["hard_failures"]:
            print(f"  {f.get('check')}: expected={f.get('expected')!r} actual={f.get('actual')!r}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
