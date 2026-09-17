# -*- coding: utf-8 -*-
"""Restore user-level Cursor hooks from this backup folder."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEST_ROOT = Path.home() / ".cursor"
DEST_JSON = DEST_ROOT / "hooks.json"
DEST_DIR = DEST_ROOT / "hooks"


def main() -> int:
    src_json = HERE / "hooks.json"
    src_dir = HERE / "hooks"
    if not src_json.is_file() or not src_dir.is_dir():
        print("BACKUP_MISSING", HERE)
        return 1

    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    if DEST_JSON.exists():
        bak = DEST_ROOT / f"hooks.json.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(DEST_JSON, bak)
        print("backed_up_existing", bak)
    if DEST_DIR.exists():
        bakd = DEST_ROOT / f"hooks_dir.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if bakd.exists():
            shutil.rmtree(bakd)
        shutil.move(str(DEST_DIR), str(bakd))
        print("moved_existing_hooks_dir", bakd)

    shutil.copy2(src_json, DEST_JSON)
    shutil.copytree(src_dir, DEST_DIR)
    meta = {
        "restored_at": datetime.now().isoformat(timespec="seconds"),
        "dest_json": str(DEST_JSON),
        "hooks": list(json.loads(DEST_JSON.read_text(encoding="utf-8")).get("hooks") or {}),
    }
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("Reload Cursor window, then check Settings → Hooks (expect 3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
