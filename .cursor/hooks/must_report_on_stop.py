# -*- coding: utf-8 -*-
"""stop: followup_message (ASCII JSON escapes; clear multi-line format)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent
STAMP = DIR / "need_status_report.flag"
LOG = DIR / "last_hook_event.json"

# Keep short: force four-line closeout, no essay.
MSG = "\n".join(
    [
        "【系统催报】工具失败/中断/挂死 — 请立刻回复用户（先别调工具）。",
        "",
        "按下面四行写，一行一项：",
        "已完成：……（有则写路径/阶段，无则写「无」）",
        "未完成：……（卡在哪 / 缺什么）",
        "下一步：……（只写一条动作）",
        "状态词：进行中 | 停等 | 失败",
        "",
        "若上一则已按此四行发过，只回：四行已发。",
    ]
)


def emit(obj: dict) -> None:
    data = json.dumps(obj, ensure_ascii=True).encode("ascii")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.write(b"\n")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}

    status = str(data.get("status") or "")
    loop_count = int(data.get("loop_count") or 0)

    stamp = None
    if STAMP.exists():
        try:
            stamp = json.loads(STAMP.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stamp = {"reason": "stamp_unreadable"}

    need = status in ("aborted", "error") or stamp is not None

    try:
        LOG.write_text(
            json.dumps(
                {
                    "event": "stop",
                    "at": datetime.now().isoformat(timespec="seconds"),
                    "status": status,
                    "loop_count": loop_count,
                    "need_followup": need,
                    "stamp": stamp,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

    if not need or loop_count >= 1:
        emit({})
        return 0

    try:
        if STAMP.exists():
            STAMP.unlink()
    except OSError:
        pass

    emit({"followup_message": MSG})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
