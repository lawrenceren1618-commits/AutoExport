# M1 订单生成模块（块 B）
# 握手：读 M0 沉淀库 / 总表 → 冲突汇报 → 填固定订单模板 → Gate → 3_Output_Final

from .conflict import ConflictReport, detect_packing_conflicts, detect_master_conflicts
from .order_parse import parse_order_workbook, extract_order_meta
from .order_fill import fill_order_template, resolve_blank_template
from .assemble import assemble_order_lines, load_settled_products

__all__ = [
    "ConflictReport",
    "detect_packing_conflicts",
    "detect_master_conflicts",
    "parse_order_workbook",
    "extract_order_meta",
    "fill_order_template",
    "resolve_blank_template",
    "assemble_order_lines",
    "load_settled_products",
]
