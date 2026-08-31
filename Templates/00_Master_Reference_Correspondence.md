# ⓪ 人工对应关系总表 — 参考说明

> 上传目录：`1_Input_Raw/00_Master_Reference/`  
> **统一字段**：见 [`Canonical_Data_Schema.md`](Canonical_Data_Schema.md) 与 `Scripts/canonical_schema.json`  
> 发货项目制：见 [`Shipment_Project_Layout.md`](Shipment_Project_Layout.md)

## 定位

人工总表 → 映射为 canonical keys →（H01 确认后）写入沉淀库。

本目录同时存放总表与（远期）发货批次列；**近端**尚无标准发货计划表，当票以订单/手工明细驱动，见 [`End_to_End_Shipment_Pipeline.md`](End_to_End_Shipment_Pipeline.md) §0.1。

**远期拟议**：在总表为每次发货单独加一列，单元格 = 该行 FNSKU 本票箱数（空=不发）。列命名规则待使用者确认后再写解析与 Correspondence。

### 已确认权威默认（2026-07-20）

| 项 | 约定 |
|----|------|
| HS | **以总表为准** → 桌布 `6302539090` |
| 克重 | **默认 90G**；其它克重须当票确认 |
| 尺寸短码↔全称 | **已确认**：见 `canonical_schema.json` → `size_shortcode_map`（**120=70X120inch**） |
| 历史发货计划 | `5月发货计划` 及已复制到 `Shipments/` 的文件 = **已验证模板**，生成时优先对齐版式 |
| 箱规（2026-08-19） | 总表 xlsx **行 45–49**（126/120 **10条装**）内盒/外箱已改为 `18*30*35.5` / `57*32*37`；权威仍以 `packing_standards` 为准。桌面副本若打开占用则未覆盖。 |
| C07 1039 | 总表无该 C07 FNSKU 行时：同 **条数/包+尺寸+颜色** 可继承 **C04** 同行 1039/净毛重（C26089 `X004SJV9UF` → `X003WN3V5J` 你已确认继续用）。售价/申报单价仍可因颜色不同而不同。 |

## 导入后必须能映射到的核心列

| 总表常见列名 | canonical key |
|--------------|---------------|
| 主体代码 / C04·C07 | `entity_code` |
| 品牌 | `brand` |
| 颜色 / 尺寸 / 克重 | `color` / `size` / `gram_weight` |
| 条数/箱、包数/箱、条数/包 | `strips_per_carton` 等 |
| FNSKU / 产品标签 | `fnsku`（出货表不需要） |
| **SKU / 卖家SKU / MSKU** | **`amazon_sku`**（店铺+品牌内唯一；亚马逊侧基本不可改；见 [`SKU_Correspondence.md`](SKU_Correspondence.md)） |
| 包装方式 / 外箱尺寸 | `pack_method` / `carton_lwh_cm` |
| HS / 1039 单价 | `hs_code` / `declare_unit_price_1039` |

未映射列进入 `unmapped`，不得丢弃不报。

## 冲突

总表多版本：以 **`master_upload_at`（上传时间）最新** 为建议默认，仍须使用者确认。  
与订单冲突：订单侧看 **`order_date`**。详见 Canonical 文档 §4。  
**SKU**：同店同牌重复或与已沉淀 `sku_index` 规格不一致 → **立即汇报**；夹名/页标与 SKU 不符时，人工备注后确认再入库（[`SKU_Correspondence.md`](SKU_Correspondence.md)）。
