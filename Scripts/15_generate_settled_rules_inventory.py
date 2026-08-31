# -*- coding: utf-8 -*-
"""Generate settled-rules inventory tables for user confirmation.

Usage:
  python Scripts/15_generate_settled_rules_inventory.py
  → Templates/Settled_Rules_Inventory.md
  → 2_Processed_AI/drafts/settled_rules_inventory.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTLED = ROOT / "Scripts" / "settled_knowledge_db.json"
OUT_MD = ROOT / "Templates" / "Settled_Rules_Inventory.md"
OUT_JSON = ROOT / "2_Processed_AI" / "drafts" / "settled_rules_inventory.json"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")


def exists(rel: str) -> bool:
    return (ROOT / rel.replace("\\", "/")).exists()


def status_icon(s: str) -> str:
    return {"settled": "✅", "partial": "⚠️", "pending": "❓", "deprecated": "🗑️"}.get(s, s)


def main() -> int:
    db = json.loads(SETTLED.read_text(encoding="utf-8"))
    cd = db.get("confirmed_defaults") or {}

    # --- Process pipeline (P1–P14 + gates) ---
    pipeline = [
        ("P1", "计划/订单入库", "流程", "settled", "End_to_End; Multi_Order", "近端订单驱动"),
        ("P2", "总表补齐 / join", "对照", "partial", "00_Master; H01", "master_table_imports 空；H01 WAIT"),
        ("P3", "订单生成", "写入", "settled", "01; 05_generate_order", "近端常已有订单跳过"),
        ("P4", "产品标签复制", "写入", "settled", "label-source-gate; 06", "源只读；固定落盘"),
        ("P5–P6", "外箱贴识别归纳", "处理", "settled", "Carton_Label; 10/08/11", "同仓同规格；中文规格夹"),
        ("P7", "仓规格统计/货值", "对照", "settled", "Amount_Weight_Reconcile; 09", "误差率≤1%"),
        ("P8", "报关生成", "写入", "settled", "03; contract_protocol; 09", "协议号登记去重"),
        ("P9", "仓头/追踪", "写入", "settled", "Tracking_Inbox; 14", "FC→B15；客户单号禁写"),
        ("P11", "货代下单", "写入", "settled", "02; freight_order_form; 09", "品牌=无；箱尺16"),
        ("P12", "出货表", "写入", "settled", "01; Multi_Order", "按 ship_date；无 FNSKU"),
        ("P13", "输出两包+微信zip", "写入", "settled", "Colleague_Pack; 13", "成品仓只复制"),
        ("Gate HX", "成品交叉对照", "对照", "partial", "pre-output-cross-check; 03", "骨架有；库行数据空"),
        ("入库贴", "货代入库贴三重验证", "对照+写入", "settled", "Freight_Inbound; 12", "勿 zip+散装双扫"),
        ("预检", "单据字段预检", "调用", "settled", "Document_Field_Preflight", "不够则 SKIP"),
        ("报错闸门", "全量汇报停确认", "调用", "settled", "error-confirm-gate", "含协议号唯一"),
    ]

    # --- Field domains ---
    fields = [
        ("主体/店", "entity_code C04/C07", "settled", "entities + entity_brand_rules", "串店禁"),
        ("品牌", "WIGENIUS / Dressmaker", "settled", "同上", "随店锁定"),
        ("订单号", "EF 长号", "settled", "order_code_style", "订单表"),
        ("出货短号", "C0x-U-日期", "settled", "outbound_code_style + outbound_short_seq.json", "出货表"),
        ("克重默认", "90G", "settled", "gram_weight", "其它克重当票确认"),
        ("HS", "6302539090", "settled", "hs_defaults", "以总表为准"),
        ("颜色别名", "米白=Ivory…", "settled", "color_米白_aliases", "标签锁"),
        ("FNSKU 锁", "牌+尺寸+条/包+色+品名", "partial", "canonical_schema", "fnsku_index 空"),
        ("SKU 锁", "店+牌内唯一", "partial", "amazon_sku", "sku_index 空"),
        ("条数/箱·包数/箱", "装箱规格", "partial", "packing_standards", "表空；§1.1 冲突汇报"),
        ("货代客户单号", "111111111", "settled", "freight_order_form", "禁写追踪"),
        ("货代品牌列", "无", "settled", "freight_brand_column", ""),
        ("箱重尺", "全 16", "settled", "carton_weight/l/w/h", ""),
        ("单箱条数", "floor(条÷箱)", "settled", "qty_per_carton", ""),
        ("销售链接", "C04/C07 分链", "settled", "sales_link", ""),
        ("合同协议号", "YYYYMMDD+NNN", "settled", "customs_contract_protocol_no", "登记库全局唯一"),
        ("报关表内抬头", "C04=波丽丝", "settled", "entity_brand_rules", "≠文件名"),
        ("出货 FNSKU", "不填", "settled", "outbound_needs_fnsku=false", ""),
        ("误差率", "≤1% 通过", "settled", "amount_weight_reconcile", ">1% 确认"),
        ("渠道", "FC/AWD/GWD", "settled", "carton_label_channels", "一腿一渠道"),
        ("C07 继承", "同 C04 流水线", "settled", "c07_inherits_c04_pipeline", "仅店/牌/FNSKU 不同"),
    ]

    # --- Call / write / check rules ---
    call_write = [
        ("全局搜索", "调用前", "settled", "global-search-gate", "须归类确认"),
        ("用户路径", "优先邻域", "settled", "user-path-resolve", ""),
        ("标签源", "只复制", "settled", "label-source-gate", "禁增删源"),
        ("H01 总表入库", "须明示确认", "pending", "modules-handshake; 04", "imports 空"),
        ("Gate→Final", "须明示+对照", "partial", "pre-output-cross-check", "C26080仍 WAIT"),
        ("成品仓", "只复制禁生成", "settled", "Colleague_Pack_Export", ""),
        ("脱敏", "禁底价入 AI 中间", "settled", ".cursorrules; mapping_dict", "mapping 有则用"),
        ("装箱冲突", "汇报后确认", "settled", "packing-spec-variance", ""),
        ("Web 栈", "Next/Supabase/Vercel", "settled", "web-stack-ui-gate", "禁私加重大依赖"),
    ]

    # --- confirmed_defaults keys inventory ---
    default_rows = []
    for k, v in sorted(cd.items(), key=lambda x: x[0]):
        if isinstance(v, dict) and v.get("deprecated"):
            st = "deprecated"
        elif isinstance(v, dict) and (v.get("confirmed_at") or v.get("confirmed_by_user")):
            st = "settled"
        elif k in ("gram_weight", "freight_brand_column", "outbound_needs_fnsku", "order_code_style",
                   "outbound_code_style", "label_output_layout", "size_120", "color_canonical_米白",
                   "validated_templates", "size_shortcode_map") or k.startswith("color_"):
            st = "settled"
        else:
            st = "settled" if v not in (None, "", [], {}) else "pending"
        doc = ""
        if isinstance(v, dict):
            doc = v.get("doc") or v.get("rule") or v.get("source") or ""
        default_rows.append((k, st, doc or "—"))

    # --- Data indexes emptiness ---
    data_indexes = [
        ("products", len(db.get("products") or []), "pending" if not db.get("products") else "settled"),
        ("packing_standards", len(db.get("packing_standards") or []), "pending" if not db.get("packing_standards") else "settled"),
        ("fnsku_index", len(db.get("fnsku_index") or []), "pending" if not db.get("fnsku_index") else "settled"),
        ("sku_index", len(db.get("sku_index") or []), "pending" if not db.get("sku_index") else "settled"),
        ("sku_manual_notes", len(db.get("sku_manual_notes") or []), "partial" if not db.get("sku_manual_notes") else "settled"),
        ("master_table_imports", len(db.get("master_table_imports") or []), "pending"),
        ("cross_check_log", len(db.get("cross_check_log") or []), "pending"),
    ]

    # --- Template coverage ---
    templates = [
        ("00_Master_Reference_Correspondence.md", "总表", "partial"),
        ("01_Order_Outbound_Correspondence.md", "订单/出货字段", "settled"),
        ("02_Freight_Forwarder_Correspondence.md", "货代字段", "settled"),
        ("03_Customs_Correspondence.md", "报关字段", "settled"),
        ("Customs_Contract_Protocol_No.md", "协议号", "settled"),
        ("Amount_Weight_Reconcile.md", "货值毛净重", "settled"),
        ("Carton_Label_Channels.md", "外箱贴", "settled"),
        ("Freight_Inbound_Label_Pipeline.md", "入库贴", "settled"),
        ("Colleague_Pack_Export.md", "输出两包", "settled"),
        ("Multi_Order_Ship_Batch.md", "多单并批", "settled"),
        ("Document_Field_Preflight.md", "预检", "settled"),
        ("Shipment_Tracking_Screenshot_Inbox.md", "追踪截图", "settled"),
        ("Split_Shipment_Ledger.md", "拆单账本", "settled"),
        ("Shipment_Project_Layout.md", "项目夹", "settled"),
        ("Shipment_Product_Label_Layout.md", "标签落盘", "settled"),
        ("SKU_Correspondence.md", "SKU", "partial"),
        ("End_to_End_Shipment_Pipeline.md", "全流程", "settled"),
        ("Architecture_Modules_Handshake.md", "模块握手", "partial"),
        ("Canonical_Data_Schema.md", "字段分层", "settled"),
        ("Table_Field_Change_Maps.md", "变更项地图", "settled"),
        ("Data_Source_Interfaces.md", "数据接口", "partial"),
        ("Local_Data_Paths.md", "废弃", "deprecated"),
        ("Next_Session_Handoff.md", "交接", "settled"),
        ("Shipping_Customs_Template.md", "报关模板说明", "partial"),
        ("Settled_Rules_Audit_2026-07-23.md", "旧审计", "partial"),
    ]

    # --- Pending for user ---
    pending = [
        {
            "id": "U1",
            "item": "products / packing_standards / fnsku_index / sku_index 仍为空",
            "ask": "是否以人工总表做一次 H01 确认入库？或暂维持空表、当票 join？",
            "suggest": "先 H01 导入总表关键列，再谈简化文件夹",
        },
        {
            "id": "U2",
            "item": "entity 法律名：settled 写「畅选贸易」vs entity_brand「许昌畅选贸易」",
            "ask": "沉淀库 entities.C04.legal_name_zh 以哪份为准？",
            "suggest": "以 entity_brand_rules 全称为准，回写 settled",
        },
        {
            "id": "U3",
            "item": "C07 报关表内抬头 / 文件名习惯（畅选+波丽丝文件名）",
            "ask": "C07 是否固定表内抬头=易尚电商；文件名是否继续可用「畅选+波丽丝」样例习惯？",
            "suggest": "表内按店；文件名习惯单独确认后写入 03",
        },
        {
            "id": "U4",
            "item": "尺寸短码映射 size_shortcode_map 曾标暂缓又标 confirmed_2026-07-21",
            "ask": "短码表是否已最终锁定？还是仍「暂缓扩展」？",
            "suggest": "锁定则写入 canonical_schema.size_folder_map 权威说明",
        },
        {
            "id": "U5",
            "item": "GWD 渠道仅预留",
            "ask": "保持预留即可，还是有样例要标定？",
            "suggest": "保持预留",
        },
        {
            "id": "U6",
            "item": "Scripts/_gen_* / _run_* / _reorg_* 本票一次性脚本",
            "ask": "保留作样例、收成通用、或列入删除候选？",
            "suggest": "简化阶段再删；先标 one-off",
        },
        {
            "id": "U7",
            "item": "1_Input_Raw/01|02|03 三分法目录 vs 日常 Shipments 项目制",
            "ask": "三分法是否仅保留 Correspondence 文档、物理样例可收敛？",
            "suggest": "下一步简化：样例进 Shipments/归档，01–03 可空或只放模板种子",
        },
        {
            "id": "U8",
            "item": "Local_Data_Paths / local_data_paths.json 已废弃",
            "ask": "确认删除？",
            "suggest": "确认后删",
        },
        {
            "id": "U9",
            "item": "Gate→Final / P1 云端仍 WAIT",
            "ask": "本阶段是否仍不进 Final、不上云？",
            "suggest": "规则清点完成后再优化；云端另排期",
        },
        {
            "id": "U10",
            "item": "外箱贴中文规格夹：C26079-A「白色 60X…pack」vs AWD「白_60X…条装」两套",
            "ask": "FC 是否统一跟 C26079-A 空格+pack 中文；AWD 保持下划线+条装？",
            "suggest": "按渠道两套写入 Carton_Label（已实践）并标 settled",
        },
        {
            "id": "U11",
            "item": "03_cross_validate.py 仍为骨架",
            "ask": "是否纳入下一步「对照自动化」优先实现？",
            "suggest": "是",
        },
        {
            "id": "U12",
            "item": "利润汇率 6.8 / 脱敏 mapping",
            "ask": "仍为全局默认？mapping_dict 是否需审计？",
            "suggest": "默认保留；mapping 有敏感再查",
        },
    ]

    # --- Scripts map (numbered) ---
    scripts = [
        ("03", "cross_validate.py", "对照", "partial"),
        ("04", "ingest_master_table.py", "写入沉淀", "partial"),
        ("05", "generate_order.py", "写入", "settled"),
        ("06", "copy_shipment_labels.py", "写入", "settled"),
        ("07", "split_shipment_ledger.py", "处理", "settled"),
        ("08", "parse_fba_carton_labels.py", "处理", "settled"),
        ("09", "generate_freight_customs_drafts.py", "写入", "settled"),
        ("10", "carton_label_ingest.py", "处理", "partial"),  # merge by spec not fully in 10
        ("11", "awd_iute_page_summary.py", "处理", "settled"),
        ("12", "freight_inbound_label_ingest.py", "对照+写入", "settled"),
        ("13", "export_output_packs.py", "写入", "settled"),
        ("14", "tracking_screenshot_ingest.py", "写入", "settled"),
        ("15", "generate_settled_rules_inventory.py", "清点", "settled"),
        ("cp", "contract_protocol.py", "写入", "settled"),
    ]

    payload = {
        "generated_at": _now(),
        "settled_db_updated_at": db.get("updated_at"),
        "pipeline": pipeline,
        "fields": fields,
        "call_write": call_write,
        "confirmed_defaults_keys": default_rows,
        "data_indexes": data_indexes,
        "templates": templates,
        "scripts": scripts,
        "pending_user_confirm": pending,
    }

    lines: list[str] = []
    lines += [
        "# 已沉淀规则清点（自动生成）",
        "",
        f"> 生成：`{_now()}` · 脚本 `Scripts/15_generate_settled_rules_inventory.py`  ",
        f"> 源：`Scripts/settled_knowledge_db.json`（updated_at={db.get('updated_at')}）  ",
        "> 图例：✅ 已沉淀无误 · ⚠️ 部分/骨架 · ❓ 待你确认 · 🗑️ 废弃待删  ",
        "> **用途**：统一清点流程/字段/调用/写入/对照；确认 ❓ 项后再做表格与文件夹简化。",
        "",
        "## 0. 数据处理总流程（调用顺序）",
        "",
        "```text",
        "订单/外箱贴上传 → 预检 → 识别外箱贴(仓×规格) → 拆并腿账本",
        "  → 货代下单(仓) + 追踪B15 → 报关(仓,协议号登记) → 出货(同日合并)",
        "  → 标签复制 → 入库贴三重验证 → 输出两包/微信zip",
        "  →（明示）Gate 交叉对照 → 3_Output_Final 视为 Final",
        "```",
        "",
        "| 步骤 | 名称 | 规则类 | 状态 | 权威 | 备注 |",
        "|------|------|--------|------|------|------|",
    ]
    for row in pipeline:
        lines.append(
            f"| {row[0]} | {row[1]} | {row[2]} | {status_icon(row[3])} | {row[4]} | {row[5]} |"
        )

    lines += [
        "",
        "## 1. 字段定义与联系（核心维）",
        "",
        "| 域 | 定义/值 | 状态 | 权威 | 联系/约束 |",
        "|----|---------|------|------|-----------|",
    ]
    for row in fields:
        lines.append(
            f"| {row[0]} | {row[1]} | {status_icon(row[2])} | {row[3]} | {row[4]} |"
        )

    lines += [
        "",
        "## 2. 调用 / 写入 / 对照闸门",
        "",
        "| 闸门 | 时机 | 状态 | 权威 | 备注 |",
        "|------|------|------|------|------|",
    ]
    for row in call_write:
        lines.append(
            f"| {row[0]} | {row[1]} | {status_icon(row[2])} | {row[3]} | {row[4]} |"
        )

    lines += [
        "",
        "## 3. confirmed_defaults 键清点",
        "",
        "| 键 | 状态 | 文档/来源 |",
        "|----|------|-----------|",
    ]
    for k, st, doc in default_rows:
        lines.append(f"| `{k}` | {status_icon(st)} | {doc} |")

    lines += [
        "",
        "## 4. 沉淀数据表（行数据）",
        "",
        "| 表 | 行数 | 状态 |",
        "|----|-----:|------|",
    ]
    for name, n, st in data_indexes:
        lines.append(f"| `{name}` | {n} | {status_icon(st)} |")

    lines += [
        "",
        "## 5. Templates 覆盖",
        "",
        "| 文件 | 主题 | 状态 |",
        "|------|------|------|",
    ]
    for name, topic, st in templates:
        ok = exists(f"Templates/{name}")
        mark = status_icon(st) if ok else "❓缺文件"
        lines.append(f"| `{name}` | {topic} | {mark} |")

    lines += [
        "",
        "## 6. 编号脚本",
        "",
        "| 编号 | 脚本 | 类 | 状态 |",
        "|------|------|----|------|",
    ]
    for num, name, kind, st in scripts:
        lines.append(f"| {num} | `{name}` | {kind} | {status_icon(st)} |")

    lines += [
        "",
        "## 7. 待你确认（未沉淀 / 不一致 / 简化前置）",
        "",
        "| ID | 事项 | 请你定 | 建议 |",
        "|----|------|--------|------|",
    ]
    for p in pending:
        lines.append(f"| {p['id']} | {p['item']} | {p['ask']} | {p['suggest']} |")

    lines += [
        "",
        "## 8. 下一步（确认后）",
        "",
        "1. 你回复各 U#：采用建议 / 改口 / 暂缓  ",
        "2. 助手按确认回写 settled + 删废弃  ",
        "3. **再开始**：表格字段收敛、文件夹简化（Shipments 项目制为主，减少重复样例层）",
        "",
        "---",
        "",
        f"机器可读副本：`2_Processed_AI/drafts/settled_rules_inventory.json`",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_JSON}")
    print(f"pending_items: {len(pending)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
