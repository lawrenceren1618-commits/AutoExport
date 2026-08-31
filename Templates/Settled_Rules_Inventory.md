# 已沉淀规则清点（自动生成）

> 生成：`2026-07-24 17:15 +0800` · 脚本 `Scripts/15_generate_settled_rules_inventory.py`  
> **轻量对齐**：`2026-07-24 17:45`（U1–U12 已拍板，见 `Settled_Rules_User_Decisions_2026-07-24.md`）  
> 源：`Scripts/settled_knowledge_db.json`（updated_at=2026-07-24）  
> 图例：✅ 已沉淀无误 · ⚠️ 部分/骨架 · ❓ 待你确认 · 🗑️ 废弃待删  
> **用途**：统一清点流程/字段/调用/写入/对照；U 项已确认 → 可做表格与文件夹简化。

## 0. 数据处理总流程（调用顺序）

```text
订单/外箱贴上传 → 预检 → 识别外箱贴(仓×规格) → 拆并腿账本
  → 货代下单(仓) + 追踪B15 → 报关(仓,协议号登记) → 出货(同日合并)
  → 标签复制 → 入库贴三重验证 → 输出两包/微信zip
  →（明示）Gate 交叉对照 → 3_Output_Final 视为 Final
```

| 步骤 | 名称 | 规则类 | 状态 | 权威 | 备注 |
|------|------|--------|------|------|------|
| P1 | 计划/订单入库 | 流程 | ✅ | End_to_End; Multi_Order | 近端订单驱动 |
| P2 | 总表补齐 / join | 对照 | ⚠️ | 00_Master; H01 | master_table_imports 空；H01 WAIT |
| P3 | 订单生成 | 写入 | ✅ | 01; 05_generate_order | 近端常已有订单跳过 |
| P4 | 产品标签复制 | 写入 | ✅ | label-source-gate; 06 | 源只读；固定落盘 |
| P5–P6 | 外箱贴识别归纳 | 处理 | ✅ | Carton_Label; 10/08/11 | 同仓同规格；中文规格夹 |
| P7 | 仓规格统计/货值 | 对照 | ✅ | Amount_Weight_Reconcile; 09 | 误差率≤1% |
| P8 | 报关生成 | 写入 | ✅ | 03; contract_protocol; 09 | 协议号登记去重 |
| P9 | 仓头/追踪 | 写入 | ✅ | Tracking_Inbox; 14 | FC→B15；客户单号禁写 |
| P11 | 货代下单 | 写入 | ✅ | 02; freight_order_form; 09 | 品牌=无；箱尺16 |
| P12 | 出货表 | 写入 | ✅ | 01; Multi_Order | 按 ship_date；无 FNSKU |
| P13 | 输出两包+微信zip | 写入 | ✅ | Colleague_Pack; 13 | 成品仓只复制 |
| Gate HX | 成品交叉对照 | 对照 | ⚠️ | pre-output-cross-check; 03 | 最小可用已上；C26080 PASS 但 Gate→Final 仍须明示；行级 FNSKU/装箱待总表 |
| 入库贴 | 货代入库贴三重验证 | 对照+写入 | ✅ | Freight_Inbound; 12 | 勿 zip+散装双扫 |
| 预检 | 单据字段预检 | 调用 | ✅ | Document_Field_Preflight | 不够则 SKIP |
| 报错闸门 | 全量汇报停确认 | 调用 | ✅ | error-confirm-gate | 含协议号唯一 |

## 1. 字段定义与联系（核心维）

| 域 | 定义/值 | 状态 | 权威 | 联系/约束 |
|----|---------|------|------|-----------|
| 主体/店 | entity_code C04/C07 | ✅ | entities + entity_brand_rules | 串店禁 |
| 品牌 | WIGENIUS / Dressmaker | ✅ | 同上 | 随店锁定 |
| 订单号 | EF 长号 | ✅ | order_code_style | 订单表 |
| 出货短号 | C0x-U-日期 | ✅ | outbound_code_style + outbound_short_seq.json | 出货表 |
| 克重默认 | 90G | ✅ | gram_weight | 其它克重当票确认 |
| HS | 6302539090 | ✅ | hs_defaults | 以总表为准 |
| 颜色别名 | 米白=Ivory… | ✅ | color_米白_aliases | 标签锁 |
| FNSKU 锁 | 牌+尺寸+条/包+色+品名 | ⚠️ | canonical_schema | 空索引已删；行级锁待总表/当票 |
| SKU 锁 | 店+牌内唯一 | ⚠️ | amazon_sku | 空索引已删；行级待总表 |
| 条数/箱·包数/箱·内外箱 | 装箱规格 | ⚠️ | packing_standards | **以库为准**；空表须汇报；§1.1 冲突确认 |
| 货代客户单号 | 111111111 | ✅ | freight_order_form | 禁写追踪 |
| 货代品牌列 | 无 | ✅ | freight_brand_column |  |
| 箱重尺 | 全 16 | ✅ | carton_weight/l/w/h |  |
| 单箱条数 | floor(条÷箱) | ✅ | qty_per_carton |  |
| 销售链接 | C04/C07 分链 | ✅ | sales_link |  |
| 合同协议号 | YYYYMMDD+NNN | ✅ | customs_contract_protocol_no | 登记库全局唯一 |
| 报关表内抬头 | C04=波丽丝 | ✅ | entity_brand_rules | ≠文件名 |
| 出货 FNSKU | 不填 | ✅ | outbound_needs_fnsku=false |  |
| 误差率 | ≤1% 通过 | ✅ | amount_weight_reconcile | >1% 确认 |
| 渠道 | FC / AWD（GWD 停用） | ✅ | carton_label_channels | 一腿一渠道；GWD 不新建 |
| C07 继承 | 同 C04 流水线 | ✅ | c07_inherits_c04_pipeline | 仅店/牌/FNSKU 不同 |

## 2. 调用 / 写入 / 对照闸门

| 闸门 | 时机 | 状态 | 权威 | 备注 |
|------|------|------|------|------|
| 全局搜索 | 调用前 | ✅ | global-search-gate | 须归类确认 |
| 用户路径 | 优先邻域 | ✅ | user-path-resolve |  |
| 标签源 | 只复制 | ✅ | label-source-gate | 禁增删源 |
| H01 总表入库 | 须明示确认 | ⚠️ | modules-handshake; 04 | imports 空；空索引已删，非阻塞简化 |
| Gate→Final | 须明示+对照 | ⚠️ | pre-output-cross-check | C26080 03 PASS；Final 仍 WAIT |
| 成品仓 | 只复制禁生成 | ✅ | Colleague_Pack_Export |  |
| 脱敏 | 禁底价入 AI 中间 | ✅ | .cursorrules; mapping_dict | mapping 有则用 |
| 装箱冲突 | 汇报后确认 | ✅ | packing-spec-variance |  |
| Web 栈 | Next/Supabase/Vercel | ✅ | web-stack-ui-gate | 禁私加重大依赖 |

## 3. confirmed_defaults 键清点

| 键 | 状态 | 文档/来源 |
|----|------|-----------|
| `amazon_sku` | ✅ | Templates/SKU_Correspondence.md |
| `amount_weight_reconcile` | ✅ | Templates/Amount_Weight_Reconcile.md |
| `c07_inherits_c04_pipeline` | ✅ | Scripts/entity_brand_rules.json c07_inherits_c04_pipeline |
| `carton_label_channels` | ✅ | Templates/Carton_Label_Channels.md |
| `color_canonical_米白` | ✅ | — |
| `color_米白_aliases` | ✅ | — |
| `customs_contract_protocol_no` | ✅ | Templates/Customs_Contract_Protocol_No.md |
| `data_source_interfaces` | ✅ | Templates/Data_Source_Interfaces.md |
| `document_field_preflight` | ✅ | Templates/Document_Field_Preflight.md |
| `error_confirm_gate` | ✅ | .cursor/rules/error-confirm-gate.mdc |
| `freight_brand_column` | ✅ | — |
| `freight_inbound_labels` | ✅ | Templates/Freight_Inbound_Label_Pipeline.md |
| `freight_order_form` | ✅ | Templates/02_Freight_Forwarder_Correspondence.md |
| `gram_weight` | ✅ | — |
| `label_output_layout` | ✅ | — |
| `local_data_paths` | 🗑️ | — |
| `multi_order_ship_batch` | ✅ | Templates/Multi_Order_Ship_Batch.md |
| `order_code_style` | ✅ | — |
| `outbound_code_style` | ✅ | — |
| `outbound_needs_fnsku` | ✅ | — |
| `output_packs` | ✅ | Templates/Colleague_Pack_Export.md |
| `shipment_tracking_screenshots` | ✅ | Templates/Shipment_Tracking_Screenshot_Inbox.md |
| `size_120` | ✅ | — |
| `size_shortcode_map` | ✅ | — |
| `validated_templates` | ✅ | — |
| `packing_authority` | ✅ | §1.1 扩大：箱规以沉淀库为准；冲突/库空汇报 |
| `customs_c04_1039_for_all_stores` | ✅ | Templates/03_Customs_Correspondence.md |
| `folder_simplify_policy` | ✅ | Settled_Rules_User_Decisions U7 |
| `gate_cross_validate` | ✅ | pre-output-cross-check; Scripts/03 |
| `fx_rate_profit_only` | ✅ | .cursorrules §3 |
| `empty_indexes_removed` | ✅ | U1 |
| `one_off_scripts_policy` | ✅ | U6 |
| `local_operational_paths` | ✅ | Templates/Local_Operational_Paths.md |

## 4. 沉淀数据表（行数据）

| 表 | 行数 | 状态 |
|----|-----:|------|
| `products` / `fnsku_index` / `sku_index` / `sku_manual_notes` | — | 🗑️ 已按 U1 删除（2026-07-24） |
| `packing_standards` | 1 | ⚠️ 2026-08-14 起按确认回写；C07 60X102 白 10条装 |
| `master_table_imports` | 0 | ⚠️ 可空；H01 明示后再填 |
| `cross_check_log` | 0 | ⚠️ 报告在 `cross_check_reports/`；可后续回写摘要 |

## 5. Templates 覆盖

| 文件 | 主题 | 状态 |
|------|------|------|
| `00_Master_Reference_Correspondence.md` | 总表 | ⚠️ |
| `01_Order_Outbound_Correspondence.md` | 订单/出货字段 | ✅ |
| `02_Freight_Forwarder_Correspondence.md` | 货代字段 | ✅ |
| `03_Customs_Correspondence.md` | 报关字段 | ✅ |
| `Customs_Contract_Protocol_No.md` | 协议号 | ✅ |
| `Amount_Weight_Reconcile.md` | 货值毛净重 | ✅ |
| `Carton_Label_Channels.md` | 外箱贴 | ✅ |
| `Freight_Inbound_Label_Pipeline.md` | 入库贴 | ✅ |
| `Colleague_Pack_Export.md` | 输出两包 | ✅ |
| `Multi_Order_Ship_Batch.md` | 多单并批 | ✅ |
| `Document_Field_Preflight.md` | 预检 | ✅ |
| `Shipment_Tracking_Screenshot_Inbox.md` | 追踪截图 | ✅ |
| `Split_Shipment_Ledger.md` | 拆单账本 | ✅ |
| `Shipment_Project_Layout.md` | 项目夹 | ✅ |
| `Shipment_Product_Label_Layout.md` | 标签落盘 | ✅ |
| `SKU_Correspondence.md` | SKU | ⚠️ |
| `End_to_End_Shipment_Pipeline.md` | 全流程 | ✅ |
| `Architecture_Modules_Handshake.md` | 模块握手 | ⚠️ |
| `Canonical_Data_Schema.md` | 字段分层 | ✅ |
| `Table_Field_Change_Maps.md` | 变更项地图 | ✅ |
| `Data_Source_Interfaces.md` | 数据接口 | ⚠️ |
| `Local_Data_Paths.md` | 废弃 | 🗑️ 已删（U8） |
| `Local_Operational_Paths.md` | 本机绝对路径速查 | ✅ |
| `Settled_Rules_User_Decisions_2026-07-24.md` | U1–U12 拍板 | ✅ |
| `Next_Session_Handoff.md` | 交接 | ✅ |
| `Shipping_Customs_Template.md` | 报关模板说明 | ⚠️ |
| `Settled_Rules_Audit_2026-07-23.md` | 旧审计 | ⚠️ 以本清点+User_Decisions 为准 |

## 6. 编号脚本

| 编号 | 脚本 | 类 | 状态 |
|------|------|----|------|
| 03 | `cross_validate.py` | 对照 | ⚠️ 最小可用；优先扩展 |
| 04 | `ingest_master_table.py` | 写入沉淀 | ⚠️ |
| 05 | `generate_order.py` | 写入 | ✅ |
| 06 | `copy_shipment_labels.py` | 写入 | ✅ |
| 07 | `split_shipment_ledger.py` | 处理 | ✅ |
| 08 | `parse_fba_carton_labels.py` | 处理 | ✅ |
| 09 | `generate_freight_customs_drafts.py` | 写入 | ✅ |
| 10 | `carton_label_ingest.py` | 处理 | ⚠️ |
| 11 | `awd_iute_page_summary.py` | 处理 | ✅ |
| 12 | `freight_inbound_label_ingest.py` | 对照+写入 | ✅ |
| 13 | `export_output_packs.py` | 写入 | ✅ |
| 14 | `tracking_screenshot_ingest.py` | 写入 | ✅ |
| 15 | `generate_settled_rules_inventory.py` | 清点 | ✅ |
| cp | `contract_protocol.py` | 写入 | ✅ |

## 7. U1–U12 状态（已全部拍板）

权威答复：[`Settled_Rules_User_Decisions_2026-07-24.md`](Settled_Rules_User_Decisions_2026-07-24.md)。  
落盘键：`customs_c04_1039_for_all_stores` / `folder_simplify_policy` / `gate_cross_validate` / `fx_rate_profit_only` / `empty_indexes_removed` / `local_operational_paths` 等。

| ID | 终态（摘要） |
|----|--------------|
| U1 | 空索引已删 |
| U2 | 法律名全称仅备案 |
| U3 | C07 报关同 C04（波丽丝+畅选+波丽丝文件名） |
| U4 | 尺寸短码锁定现表 |
| U5 | GWD 停用 |
| U6 | one-off 脚本按需留删 |
| U7 | 不硬收敛 01/02/03；先任务后简洁 |
| U8 | 旧 Local_Data_Paths 已删；接口表 + Local_Operational_Paths 并存 |
| U9 | 云端后置；可 git→GitHub（须再明示） |
| U10 | FC/AWD 两套中文规格命名 |
| U11 | 03 最小可用；优先扩展对照 |
| U12 | 表内美金、不做汇率；利润汇率 6.8 |

## 8. 下一步（现役）

1. **表格/文件夹简化**（`folder_simplify_policy`）：先完成任务再简洁；可选「旧树当库 + 新上传/输出夹」  
2. 用户明示时：Gate→Final / git commit+push  
3. 预检够才做；报错全量汇报（error-confirm-gate）

---

机器可读副本：`2_Processed_AI/drafts/settled_rules_inventory.json`（生成时可能仍含旧 U 表，以本 md + User_Decisions 为准）
