# -*- coding: utf-8 -*-
"""sessionStart: short reporting rules (ASCII JSON escapes)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

LOG = Path(__file__).resolve().parent / "last_hook_event.json"

CTX = "\n".join(
    [
        "【汇报规则】每回合结束给用户四行（一行一项）：",
        "已完成 / 未完成 / 下一步 / 状态词",
        "失败或中断时优先发这四行；勿只显示 Exploring/Thought。",
        "长任务：先写盘、短命令；忌全库 Grep/Glob。",
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
    try:
        LOG.write_text(
            json.dumps(
                {
                    "event": "sessionStart",
                    "at": datetime.now().isoformat(timespec="seconds"),
                    "keys": sorted(map(str, data.keys()))[:40],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

    emit({"additional_context": CTX})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
