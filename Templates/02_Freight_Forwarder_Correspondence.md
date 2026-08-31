# ② 货代下单表 — 字段对应关系

> **独立文档**：只对应「货代入库贴**下单表**」（生成）。  
> 与「货代入库贴」（货代回传 PDF）分目录，见 [`Shipment_Project_Layout.md`](Shipment_Project_Layout.md)。  
> **入库贴回传流水线**（识别 / 三重验证 / 一仓一 PDF）：[`Freight_Inbound_Label_Pipeline.md`](Freight_Inbound_Label_Pipeline.md)。  
> **已验证模板**：`EF-C26040-…/货代入库贴下单表/货代入库贴数据2026.5.10 HEA2 248箱.xlsx`。  
> 单表变更映射：[`Table_Field_Change_Maps.md`](Table_Field_Change_Maps.md) · [`Scripts/table_field_maps.json`](../Scripts/table_field_maps.json)  
> 确认日：**2026-07-22**（本票抽查纠偏后锁定）

状态：规则已按抽查纠偏锁定；**C26079-A 五仓草稿已按新规则改表**。后续票仍须外箱贴到位后再生成。  
前置：仓库代码 / FBA / 地址确认（H42）；货值对照见 [`Amount_Weight_Reconcile.md`](Amount_Weight_Reconcile.md)（误差率 ≤1% 通过；**报关**用分仓正算反算；货代表单价仍用该单价，但箱重尺走固定 16）。  
终审：Gate 通过后写入 `3_Output_Final/{项目}/`（两包结构见 [`Colleague_Pack_Export.md`](Colleague_Pack_Export.md)）。

### 已确认（2026-07-20 / 行策略 2026-07-21 / **字段闸门 2026-07-22**）

| 项 | 约定 |
|----|------|
| **客户单号** | 固定 **`111111111`**（样例占位）；**禁止**改成追踪码 / FBA 号 |
| **品牌 / 类型 / 型号** | 填 **`无`** |
| HS | **`6302539090`** |
| **箱重、长、宽、高** | 固定默认 **`16`**（不写总表毛重/箱规） |
| **单箱数量** | **`floor(该仓总条数 ÷ 该仓总箱数)`**（向下取整） |
| **收件人姓名** | **不填**（空） |
| **收件地址1** | **`仓库代码 + 具体地址`**；权威 [`Amazon_Warehouse_Address.md`](Amazon_Warehouse_Address.md) / `Scripts/amazon_warehouse_addresses.json` |
| **明细行数** | 一仓一文件、**一行综合** |
| **图片** | 插入**样例图片**（模板 `DISPIMG` + `xl/media`；**每次** openpyxl 保存后必须 **reinject media/cellimages**，否则公式在、图不在——FC/AWD 相同）；生成后校验 `xl/media≥1` |
| **销售链接** | 按店铺：C04=`https://www.amazon.com/dp/B0CCRKDW1K?th=1`；C07=`https://www.amazon.com/gp/product/B0FNVMX537` |
| **任意订单号** | **FC**=FBA 货件号；**AWD**=`ShipmentID`（如 `STAR-…`） |
| **reference / 追踪编码** | **FC**=有则填；**AWD**=通常不填（2026-07-23 确认） |
| 生成时机 | 外箱贴入项目 `FBA外箱贴/` 后再填 |
| **入库贴是否另要** | **SEND 承运人**（如纽酷）：外箱贴已含入库贴，**不另要**；**普通货代**（如物易通）：须下单后等回传 PDF → [`Freight_Inbound_Label_Pipeline.md`](Freight_Inbound_Label_Pipeline.md) · `freight_forwarder_profiles.json` |

> **补充（多单并批）**：仓主键与订单总条数/总箱数交叉核对见 [`Multi_Order_Ship_Batch.md`](Multi_Order_Ship_Batch.md)；本表既有确认项不变。

---

## 1. 与订单主体的关系

| 内部主体 | 内部品牌（订单用） | 货代表「品牌」列 | 店铺 |
|----------|-------------------|------------------|------|
| C04 | WIGENIUS | **无** | C04 |
| C07 | Dressmaker | **无** | C07 |

### 硬性规则

1. 货代「品牌」列固定 **无**；不得因内部品牌自动改写。  
2. 不得跨店串 FNSKU。  
3. **仅改「变更项」列**；客户单号、箱重尺、HS、材质、品牌三列等**不得**被生成逻辑冲掉。  
4. 仓库代码、FBA 地址、货件号：等入库货件确认后再写。  
5. **一行综合**：当前仓地址下总箱写在同一明细行；单箱数量用向下取整。

---

## 2. 本类单据

| 子类型 | 落盘 |
|--------|------|
| 货代入库贴**下单表**（生成） | `Shipments/…/货代入库贴下单表/`（常一仓一 xlsx） |
| 货代入库贴（货代回传） | `Shipments/…/货代入库贴/_inbox` → 验证后 `FBA外箱贴/{渠道}/{仓}/…_入库贴_{N}箱.pdf` |

版式：3 sheets — `下单模板`（主填）+ `收货网点` + `产品名称`（后两枚举一般不动）。

---

## 3. 变更项 / 不变项（强制 · 仅本表）

### 3.1 变更项（只允许这些）

| 字段（表内） | 规则 | 来源 |
|--------------|------|------|
| 仓库代码 | 写仓码 | FBA 外箱贴 |
| 收件人姓名 | **空** | — |
| 收件地址1 | `仓码 - 街道 - 城市, 州 邮编 - United States` | [`amazon_warehouse_addresses.json`](../Scripts/amazon_warehouse_addresses.json) |
| 任意订单号 | = **FBA 订单号** | 外箱贴 |
| reference ID | = **追踪编码** | 人工/仓头 |
| 箱 | 该仓总箱数 | 外箱贴统计 |
| 中文品名 / 英文品名 | 综合口径（常「桌布 / table cloth」） | 样例 |
| 单箱数量 | **`floor(总条÷总箱)`** | 仓汇总 |
| 单价 | USD；分仓正算反算之单价 | 总表 1039×箱 → 条 |
| 图片 | 样例 DISPIMG + media | 模板 |
| 销售链接 | 样例 URL（按 C04/C07） | 沉淀库 |

### 3.2 不变项（生成不得改写权威值）

| 字段 | 固定值 |
|------|--------|
| 客户单号 | **`111111111`** |
| 申报币别 | `USD` |
| 箱重 / 长 / 宽 / 高 | 各 **`16`** |
| HS CODE | `6302539090` |
| 材质(中英文) | `聚酯纤维/polyester` |
| 用途(中英文) | `餐桌` |
| 品牌 / 品牌类型 / 型号 | 均为 **`无`** |
| 收件省份/城市/邮编格 | **不填**（地址已写在收件地址1） |
| 3 sheet 结构；row14 列标题；枚举 sheet | 版式不动 |

**不填入本类**：报关全套法律文书、工厂订单页眉、报关表内抬头（波丽丝）叙事。

### 3.3 单价（货代表）

货代表 **G15 单价** 仍用分仓正算反算单价（与报关一致）：

1. `raw = Σ(箱 × 总表每箱单价)`  
2. `单价 = round(raw / 总条数, 2)`  
3. 报关货值 = `round(单价 × 总条数, 2)`（报关侧；货代表不写总价列）  
4. 规格汇总↔分仓误差率闸门见 [`Amount_Weight_Reconcile.md`](Amount_Weight_Reconcile.md)

**注意**：货代表 **箱重/长宽高 ≠ 报关毛净重**；货代表固定 16，报关仍用总表每箱净/毛汇总。

---

## 4. 摘要对照

| 不变 | 变更 |
|------|------|
| 客户单号 `111111111`；箱重尺全 16；HS；材质/用途；品牌三列=`无`；省市区邮编空 | 仓码、收件人姓名(空)、地址、FBA、reference、箱数、品名、单箱 floor、单价、图片、销售链接(按店) |

完整表：`Table_Field_Change_Maps.md` §4。  
生成脚本：`Scripts/09_generate_freight_customs_drafts.py`（含 media reinject）。
