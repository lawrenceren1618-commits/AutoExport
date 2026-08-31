# 块 A — 统一数据字段（Canonical Schema）

> 所有总表 / 工厂订单 / 出货 / 货代 / 报关 / PDF 识别结果，先映射到本表 **key**，再写入沉淀/临时库或填模板。  
> 机器可读：[`Scripts/canonical_schema.json`](../Scripts/canonical_schema.json)  
> 单表变更/映射沉淀：[`Templates/Table_Field_Change_Maps.md`](Table_Field_Change_Maps.md) · [`Scripts/table_field_maps.json`](../Scripts/table_field_maps.json)  
> 代码映射：[`web/lib/master-import.ts`](../web/lib/master-import.ts)（与 JSON 别名保持同步）

## 任务树（块 A）

| ID | 任务 | 状态 |
|----|------|------|
| A1 | 定义 canonical keys + 分级（沉淀/临时） | 进行中→本文档 |
| A2 | 中英列名别名表 | 本文档 + JSON |
| A3 | 值规范化规则 | 本文档 |
| A4 | 接到导入脚本 / 交接包 | 同步改代码 |

---

## 1. 字段总表

### 1.1 沉淀类（settled）— 相对稳定

| key | 中文 | 类型 | 说明 |
|-----|------|------|------|
| `entity_code` | 公司代码 | enum | `C04` \| `C07` |
| `company_name` | 公司名 | string | 内部用；页眉另规则 |
| `brand` | 品牌 | string | C04→WIGENIUS；C07→Dressmaker |
| `gram_weight` | 面料克重 | string/number | 如 `90G` / `90` |
| `size` | 产品尺寸 | string | 统一去空格，保留 inch/圆桌等 |
| `color` | 颜色 | string | 蓝/黑/米白/白… |
| `strips_per_pack` | 每包条数 | number | 常见 10 |
| `packs_per_carton` | 每箱包数 | number | |
| `strips_per_carton` | 每箱条数 | number | = 条/包×包/箱；可推算 |
| `fnsku` | FNSKU | string | 一箱一码；禁跨店 |
| `pack_method` | 包装方式 | enum | `heat_shrink` \| `carton` |
| `inner_pack_lwh_cm` | 内包装长宽高 | string | 纸箱包装必填；热缩可空 |
| `carton_lwh_cm` | 外箱长宽高 | string | `L*W*H` cm |
| `hs_code` | 海关编码 | string | 默认桌布 **`6302539090`（以总表为准）** |
| `gram_weight` | 面料克重 | string/number | **默认 `90G`**；其它克重当票确认 |
| `product_name_zh` | 中文品名 | string | |
| `product_name_en` | 英文品名 | string | |
| `tax_rebate` | 是否退税 | enum | `yes` \| `no` \| `unknown` |
| `declare_unit_price_1039` | 1039 每箱报关单价 | number | 沉淀参考价；当票可覆盖 |

### 1.2 订单/批次类（order）

| key | 中文 | 类型 | 最新判定 |
|-----|------|------|----------|
| `order_code` | 订单编号 | string | |
| `order_date` | 下单日期 | date | **订单冲突：此日最新优先** |
| `delivery_date` | 交货日期 | date | **出货发货日以此为准**（非下单日） |
| `master_upload_at` | 总表上传时间 | datetime | **总表冲突：上传最新优先** |
| `qty_strips` | 订单总条数 | number | |
| `qty_cartons` | 订单总箱数 | number | |

### 1.3 临时/货件类（shipment）— 货件后

| key | 中文 | 类型 | 来源 |
|-----|------|------|------|
| `outbound_short` | 出货短号 | string | `{店铺}-{YY}{NN}`；表内仅短号 |
| `ship_date` | 发货/出货日期 | date | **= 订单交货日期** |
| `sales_person` | 业务员 | string | 默认任胜国 |
| `destination` | 目的地 | string | 默认 US；文件名 U=USA |
| `fba_shipment_id` | FBA 货件号 | string | PDF/截图→确认 |
| `tracking_id` | 追踪编码 | string | **手填**或截图确认 |
| `warehouse_code` | 仓库代码 | string | PDF |
| `warehouse_address` | 仓库地址 | string | PDF |
| `ship_strips` | 本批发货条数 | number | |
| `cartons` | 本批箱数 | number | |
| `packs` | 本批包数 | number | |
| `carton_combo` | FNSKU×箱数组合 | json/string | PDF |
| `split_shipment` | 是否拆单 | bool | |
| `split_batch_no` | 拆单序号 | string | |
| `remaining_strips` | 剩余条数 | number | 拆单账本累计 |
| `remaining_cartons` | 剩余箱数 | number | 拆单账本累计 |
| `gross_kg_total` | 货件总毛重 | number | 汇总 |
| `net_kg_total` | 货件总净重 | number | 汇总 |
| `declare_amount_total` | 货件总报关金额 | number | 汇总 |
| `export_date` | 出口日期 | date | 常固定/当票 |
| `export_code` | 出口相关编码 | string | 常固定 |

### 1.4 派生 key（系统生成）

| key | 规则 |
|-----|------|
| `sku_key` | `{brand}|{size}|{color}` |
| `product_key` | 同 sku_key（装箱索引） |
| `fnsku_lock_key` | `{brand}|{size}|{strips_per_pack}|{product_name_zh}`（**双向**锁定 FNSKU；颜色用于消歧） |
| `data_tier` | `settled` \| `temporary` |

### 1.5 FNSKU 双向锁定（强制）

核心锁定维（双向成立）：

| 维 | 说明 |
|----|------|
| 品牌 | C04↔WIGENIUS / C07↔Dressmaker |
| 尺寸 | |
| 条数/包 | |
| **颜色** | **核心维**，不是附属「消歧」 |
| 品名 | 品名内嵌颜色须与颜色列一致 |

- **正向**：上列 → FNSKU  
- **反向**：FNSKU → 上列，须与订单/总表一致  
- 亚马逊只认 FNSKU；**克重不参与锁定**，不因 90G/110G 拒绝标签复制  
- 颜色命名不统一（订单列 vs 品名 vs 标签文件名）→ **汇报使用者修正**，禁止静默合并别名（除非已写入确认别名表）

`fnsku_lock_key` = `{brand}|{size}|{strips_per_pack}|{color}|{product_name_zh}`

---

## 2. 列名别名（表头 → key）

见 `canonical_schema.json` → `header_aliases`。常见例：

- `主体代码` / `C04` / `公司代码` → `entity_code`
- `条数/箱` / `条数每箱` → `strips_per_carton`
- `包数/箱` / `包数每箱` → `packs_per_carton`
- `条数/包` → `strips_per_pack`
- `热缩膜` / `纸箱` / `包装方式` → `pack_method`
- `产品标签` / `FNSKU` → `fnsku`
- `外箱尺寸` / `纸箱规格` → `carton_lwh_cm`
- `下单日期` → `order_date`
- `海外订单号` / `FBA` → `fba_shipment_id`

未识别列名：**保留原列名并标 `unmapped`**，不得 silently drop。

---

## 3. 值规范化

| key | 规则 |
|-----|------|
| `entity_code` | 抽 `C04`/`C07`；订单号含片段可推断 |
| `brand` | 空则按 entity 补默认；与 entity 冲突则汇报 |
| `pack_method` | 含「热缩」→ heat_shrink；含「纸箱」→ carton |
| `carton_lwh_cm` / `inner_pack_lwh_cm` | 统一 `L*W*H`，去 `cm` 字样可保留单位标注 |
| `size` | 经 `size_shortcode_map`：总表短码→订单全称；再规范化（如 `90inchround`、`60X102inch`）。**120=70X120inch** |
| `order_date` | → `YYYY-MM-DD` |
| 数量字段 | 转 number；空→ null，不填 0 除非表内为 0 |

---

## 4. 冲突「最新」

| 来源 | 时间戳字段 | 用途 |
|------|------------|------|
| 工厂订单行 | `order_date` | 同 sku+entity 多版装箱/克重 |
| 人工总表行 | `master_upload_at`（文件上传时写入） | 总表多版 |

冲突时：**列出旧值/新值/时间 → 使用者确认 → 再沉淀**。  
装箱/内外箱：**以沉淀库 `packing_standards` 为准**；库空或与计划不一致 → 汇报确认（§1.1），禁止计划行跳过库、禁止编造箱尺。

---

## 5. Cursor / 脚本调用约定

1. 任何表格解析第一步：`headers → canonical keys`（本 schema）。  
2. 第二步：规范化值。  
3. 第三步：按 `data_tier` 写入 settled 或 temporary。  
4. 填模板：只取模板需要的 key，禁止全量灌列。
