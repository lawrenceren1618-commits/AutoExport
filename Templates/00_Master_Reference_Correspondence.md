# ⓪ 人工对应关系总表 — 参考说明

> 上传目录：`1_Input_Raw/00_Master_Reference/`  
> **统一字段**：见 [`Canonical_Data_Schema.md`](Canonical_Data_Schema.md) 与 `Scripts/canonical_schema.json`

## 定位

人工总表 → 映射为 canonical keys →（H01 确认后）写入沉淀库。

## 导入后必须能映射到的核心列

| 总表常见列名 | canonical key |
|--------------|---------------|
| 主体代码 / C04·C07 | `entity_code` |
| 品牌 | `brand` |
| 颜色 / 尺寸 / 克重 | `color` / `size` / `gram_weight` |
| 条数/箱、包数/箱、条数/包 | `strips_per_carton` 等 |
| FNSKU / 产品标签 | `fnsku` |
| 包装方式 / 外箱尺寸 | `pack_method` / `carton_lwh_cm` |
| HS / 1039 单价 | `hs_code` / `declare_unit_price_1039` |

未映射列进入 `unmapped`，不得丢弃不报。

## 冲突

总表多版本：以 **`master_upload_at`（上传时间）最新** 为建议默认，仍须使用者确认。  
与订单冲突：订单侧看 **`order_date`**。详见 Canonical 文档 §4。
