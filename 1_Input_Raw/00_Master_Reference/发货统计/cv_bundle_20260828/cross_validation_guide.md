# 发货记录 · 库存/财务交叉验证接入指南

> 打包日：**2026-08-28**  
> 用途：作为**另一技能 / 库存财务系统**中「发货部分」的**交叉验证数据源**（只读参照，非写入权威）。

---

## 1. 包根路径（复制整夹即可）

```text
D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\00_Master_Reference\发货统计\cv_bundle_20260828\
```

---

## 2. 文件清单

| 文件 | 角色 |
|------|------|
| **`2026年发货记录.xls`** | 主表快照（v3 列序；含 C26095；B3 冻结） |
| **`rows_flat.json`** | 机器可读扁平行（319 规格行）；**推荐 CV 脚本直接读此文件** |
| **`column_schema_v3.json`** | 列定义、批次分组、数量勾稽公式 |
| **`ship_stats_size_dims.json`** | 尺寸简码 ↔ inch、颜色归一、头程分摊公式 |
| **`known_gaps.json`** | 已知空字段（包/箱、物易通运费）；CV 时须跳过或标待确认 |
| **`Ship_Stats_Freight_Allocation.md`** | 头程分摊人类可读规则（2026-08-28 确认） |
| **`Ship_Stats_Correspondence.md`** | 字段对应、树粒度、成本 S3、FNSKU 等总规则 |
| **`field_map.json`** | 规则锁定摘要（B6/B8/成本流） |
| **`ship_stats_freight_allocate.py`** | 头程分摊审计脚本（只读出报告，不改表） |

**AutoExport 仓内权威原件（本包为快照，后续以 inbox 为准）：**

| 原件 | 路径 |
|------|------|
| 主表 live | `…/发货统计/_inbox/2026年发货记录.xls` |
| 尺寸映射 live | `Scripts/ship_stats_size_dims.json` |
| 分摊脚本 live | `Scripts/ship_stats_freight_allocate.py` |
| 装箱沉淀库 | `Scripts/settled_knowledge_db.json` → `packing_standards` |

---

## 3. 交叉验证主键（建议）

与库存/财务系统对账时，优先用以下组合匹配：

| 层级 | 键 | 说明 |
|------|-----|------|
| 批次 | `batch_ticket` | 如 `C26095-A`、`C26079-B`；来自给货日期列 |
| 规格行 | `batch_ticket` + `strips_per_pack` + `size_short` + `gram_weight_g` | 同腿多 SKU |
| 数量 | `cartons` × `packs_per_carton` = 包数；× `strips_per_pack` = 条数 | 见 `column_schema_v3.json` |
| 渠道 | `channel` | 物易通=实填运费；后台扣款/纽酷=运费 **0**（避免重复扣头程） |
| 货件 | `fba_ids` | 可与 FBA 外箱贴 / 货代单交叉 |

**给货日（A1）**：树/存档日用实际交货日；表内「给货日期」列即此口径。

---

## 4. 运算规则（CV 必核）

### 4.1 数量勾稽

```text
packs_total   = cartons × packs_per_carton
strips_total  = packs_total × strips_per_pack
```

`packs_per_carton` 或 `freight_rmb` 为 **null** 的行 → 见 `known_gaps.json`，**不得**当作已通过 CV。

### 4.2 每包重量（头程分摊前置）

```text
每条重量(g)   = gram_weight_g × 面积(m²)     # 面积见 ship_stats_size_dims.json
每包重量(kg)   = 每条重量(g) × strips_per_pack / 1000
```

### 4.3 头程分摊（批次级）

```text
头程单价(元/kg) = 批次 freight_rmb ÷ Σ(各规格 packs_total × 每包重量)
每包头程(元)     = 头程单价 × 该规格每包重量
```

- **纽酷 / 后台扣款 / SEND**：`freight_rmb = 0`（已在平台到账体现）
- **物易通**：填实际 RMB 运费

### 4.4 国内花费（每包）

```text
每包采购成本 = 条单价 × strips_per_pack    # 成本列或单价截图确认流
每包国内花费 = 每包采购成本 + 每包头程
```

### 4.5 颜色 / 尺寸

- 尺寸简码 ↔ 全称：`ship_stats_size_dims.json` → `short_to_dims`
- 米白 = Ivory = 象牙白；**白 ≠ 米白**（不同 SKU）

---

## 5. 2026-08-28 清洗范围（读表时注意）

- **2026+** 桌布：克重独立 D 列；规格简写 `6`/`10`/`2`；尺寸简写 `102白` 等
- **2026 前**：规格/尺寸未统一改写（含 `110G 桌布-6` 等历史写法）
- **非桌布**（秸秆、假发等）：未改
- **已知批次克重**：C26079=90、C26080=90
- **C26046**：A 纽酷 500 箱运费 0 + B 物易通 500 箱运费 47277.9

---

## 6. 跑头程分摊审计（可选）

在 AutoExport 根目录：

```bash
python Scripts/ship_stats_freight_allocate.py
```

报告：`2_Processed_AI/cross_check_reports/ship_stats_freight_allocate_*.json`

---

## 7. 给另一技能的提示词片段（可复制）

```text
发货交叉验证数据源（只读）：
根目录 D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\00_Master_Reference\发货统计\cv_bundle_20260828
主读 rows_flat.json + column_schema_v3.json + ship_stats_size_dims.json
规则文 Ship_Stats_Freight_Allocation.md、Ship_Stats_Correspondence.md
空字段清单 known_gaps.json — null 运费/包箱不得当已通过
批次键 batch_ticket（C26xxx-A/B）；数量：cartons×packs_per_carton×strips_per_pack
纽酷/后台扣款运费=0；物易通填实价
```
