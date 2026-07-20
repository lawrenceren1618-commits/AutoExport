# -*- coding: utf-8 -*-
"""
04_ingest_master_table.py
脚本职责：读取 1_Input_Raw/00_Master_Reference 下人工总表，预览行数据；
          仅在使用者显式确认（CLI --confirm）后写入 Scripts/settled_knowledge_db.json
          或提示走 Web H01（/api/master-import → Supabase）。
握手：H01
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER_DIR = PROJECT_ROOT / "1_Input_Raw" / "00_Master_Reference"
SETTLED_DB = Path(__file__).resolve().parent / "settled_knowledge_db.json"


def list_master_files(directory: Path = MASTER_DIR) -> list[Path]:
    """列出总表候选文件（xlsx/xls/csv）。"""
    # TODO: 过滤临时文件
    exts = {".xlsx", ".xls", ".csv"}
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in exts)


def preview_rows(file_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    """
    解析总表前若干行供人工确认。

    实现思路：pandas.read_excel / read_csv；列名映射与 web/lib/master-import.ts 对齐。
    """
    # TODO: 实现解析
    pass


def ingest_confirmed(file_path: Path, settled_path: Path = SETTLED_DB) -> dict:
    """
    H01：仅当 --confirm 时合并进沉淀库 JSON（本地），并标记 source=master_table。

    云端等价路径：后台「我已确认，写入沉淀库」→ Supabase。
    """
    # TODO: 合并 products / packing_standards / fnsku_index
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="H01 人工总表预览/确认入库（本地）")
    parser.add_argument("--file", type=str, help="指定总表路径")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="显式确认后写入 settled_knowledge_db.json",
    )
    args = parser.parse_args()
    # TODO: 调度 preview / ingest
    print("Use --file and optional --confirm. Prefer web /admin/master-import for Supabase.")
    _ = args


if __name__ == "__main__":
    main()
