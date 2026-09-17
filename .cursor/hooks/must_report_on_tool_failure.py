# -*- coding: utf-8 -*-
"""postToolUseFailure: OBSERVE ONLY (Cursor docs: no output fields supported)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent
STAMP = DIR / "need_status_report.flag"
LOG = DIR / "last_hook_event.json"


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
        data = {"_raw": raw[:2000]}

    tool = data.get("tool_name") or data.get("toolName") or data.get("tool") or "unknown"
    err = data.get("error_message") or data.get("error") or data.get("message") or ""
    ftype = data.get("failure_type") or ""
    payload = {
        "event": "postToolUseFailure",
        "at": datetime.now().isoformat(timespec="seconds"),
        "tool": tool,
        "failure_type": ftype,
        "error": str(err)[:1200],
        "is_interrupt": data.get("is_interrupt"),
        "input_keys": sorted(map(str, data.keys()))[:50],
    }
    try:
        LOG.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        STAMP.write_text(
            json.dumps(
                {
                    "reason": "postToolUseFailure",
                    "tool": tool,
                    "at": payload["at"],
                    "error": payload["error"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

    emit({})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
