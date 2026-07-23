# 已确认规则沉淀核查（2026-07-23）

> 对照：口述/本票确认 ↔ `settled_knowledge_db.json` ↔ Templates / schema / 脚本  
> 图例：✅ 已录入 · ⚠️ 骨架待数据 · ❌ 缺失（已补则改 ✅）

## 1. 主体 / 标签 / 对照

| 规则 | 沉淀库 | 文档 | 脚本 |
|------|--------|------|------|
| C04↔WIGENIUS；页眉不写畅选 | ✅ entities | `.cursorrules` | — |
| C07↔Dressmaker | ✅ | 同上 | — |
| HS `6302539090`；克重默认 90G | ✅ | 00/流水线 | — |
| FNSKU 双向锁含颜色；米白=Ivory | ✅ color + schema | label-source-gate | 06/08 |
| 货值/毛净重误差率 ≤1% | ✅ amount_weight_reconcile | Amount_Weight_Reconcile.md | 09 |
| 标签源只读；落盘路径固定 | ✅ label_output_layout | label-source-gate | 06 |

## 2. 货代下单表（2026-07-22/23）

| 规则 | 沉淀库 | 文档 | 脚本 |
|------|--------|------|------|
| 客户单号 `111111111` 不可改 | ✅ freight_order_form | 02 / Change_Maps | 09 |
| 变更项白名单；收件人姓名空 | ✅ | 02 | 09 |
| 单箱 `floor(条÷箱)` | ✅ | 02 | 09 |
| 箱重/长宽高全 **16** | ✅ | 02 | 09 |
| HS/材质/用途/品牌三列固定 | ✅ | 02 | 09 |
| 销售链接 C04/C07 | ✅ sales_link | 02 | 09 |
| 图片 DISPIMG+**强制 reinject**+验 media | ✅ product_image_rule | 02 / Change_Maps / table_field_maps | 09 校验 |
| FC：任意订单号=FBA；reference=追踪码 | ✅ any_order_no/reference_id | Carton_Label + 02 | 09 |
| AWD：任意订单号=STAR…；reference **通常空** | ✅ | 同上 | B 生成 |

## 3. 外箱贴渠道（2026-07-23）

| 规则 | 沉淀库 | 文档 | 脚本 |
|------|--------|------|------|
| 渠道 FC / AWD / GWD | ✅ carton_label_channels | Carton_Label_Channels.md | 10 |
| **一腿一渠道互斥** | ✅ one_leg_one_channel | 同上 | 作业约定 |
| **统一识别+按版式确认字段**（拆分/合并同目的） | ✅ field_confirm_by_layout + unified_flow | 同上 §0§3 | 10 |
| 流水线含分离→同仓同规格合并 | ✅ | 同上 §4 | 10/11 |
| AWD 特征标定（IUTE/STAR/AWD Box） | ✅ awd_sample_calibrated | 同上 | 11 |
| `_inbox` / `_staging` / 正式树 | ✅ | 项目已建夹 | — |

## 4. SKU（2026-07-23）

| 规则 | 沉淀库 | 文档 | 脚本 |
|------|--------|------|------|
| 店+牌内唯一；亚马逊侧基本不可改 | ✅ amazon_sku | SKU_Correspondence.md | schema |
| 人工备注路径；确认后入 sku_index | ✅ | 当票 SKU_人工备注.md | — |
| **sku_index 行数据** | ⚠️ 空表 | 待总表补 SKU 列 | — |

## 5. 本票状态（非全局规则）

| 项 | 状态 |
|----|------|
| C26079-A FC + B AWD | 拆单完成；草稿抽查通过 |
| B 货代图片 | ✅ 已覆盖正式文件 media=1 |
| Gate→Final | **WAIT**（未明示进 Final） |
| H01 / 云端 | WAIT |

## 6. 本次核查补录

- `freight_order_form`：补 AWD/FC 分渠道的任意订单号与 reference；图片 fail_if_missing  
- `02_Freight…md`：补 AWD 订单号/追踪码/图片校验句  
- `Next_Session_Handoff.md`：同步 A+B 完成态与规则索引  
