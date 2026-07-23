# SKU（亚马逊卖家 SKU）— 对应关系与人工备注

> 确认日：2026-07-23  
> 沉淀：`Scripts/settled_knowledge_db.json` → `sku_index` / `confirmed_defaults.amazon_sku`  
> 机器可读：`Scripts/canonical_schema.json` → `amazon_sku_lock`

## 1. 定位

| 项 | 约定 |
|----|------|
| **SKU** | 亚马逊后台 **卖家 SKU（MSKU）**；系统内基本**不可改** |
| **唯一性** | 在 **同一店铺 + 同一品牌** 内 **唯一**，不重复 |
| **与 FNSKU** | 两套码并存；亚马逊履约贴外箱常可见 SKU；FNSKU 仍用于标签/沉淀双向锁 |
| **总表** | 总表应含 SKU 列；上传后经确认写入 `sku_index` |

**不串店**：C04（WIGENIUS）与 C07（Dressmaker）的 SKU **互不共用**。

## 2. 识别优先级（有 SKU 后）

1. **已沉淀 `sku_index`**（店铺+品牌+SKU → 尺寸/颜色/条数包/FNSKU）→ **权威**  
2. 外箱贴 / PDF 抽到的 SKU → 查沉淀或总表  
3. 夹名 / 页内 `126-6` 等 → 仅作辅助；与 SKU 冲突时 **以 SKU（或人工备注）为准**，并写备注  
4. 无 SKU、无沉淀 → 维持旧逻辑（夹名+页标+计划 FNSKU），并标待补 SKU  

夹名错标（如本票 126 米白外标 6pack、实含 10 条装）时：使用者**手动指出正确 SKU/规格** → 助手写入当票备注 +（确认后）沉淀，避免下次再靠页标猜测。

## 3. 人工备注（强制留痕）

当票目录：

```text
Shipments/{项目}/拆单比对/SKU_人工备注.md
```

全局可检索沉淀：`settled_knowledge_db.json` → `sku_manual_notes[]`（须使用者确认后再入库）。

每条备注至少含：

| 字段 | 说明 |
|------|------|
| `date` | 日期 |
| `order_code` / `split_leg` | 哪一票哪一腿 |
| `store` / `brand` | C04/C07、品牌 |
| `sku` | 亚马逊 SKU（人工确认） |
| `size` / `color` / `strips_per_pack` | 实际规格 |
| `fnsku` | 若已知一并写 |
| `why` | 为何手判（夹名错、页标混装、总表缺列等） |
| `source` | 人工口述 / 总表 / 外箱贴截图等 |

## 4. 与总表列

总表增加 SKU 后映射：

| 总表列 | canonical |
|--------|-----------|
| SKU / 卖家SKU / MSKU | `amazon_sku` |
| （已有）FNSKU | `fnsku` |
| 店铺 / 品牌 / 尺寸 / 颜色 / 条数包 | 既有 keys |

导入后：`amazon_sku` + `entity_code` + `brand` → 唯一键；冲突汇报，禁止静默覆盖。

## 5. 本票备忘（C26079-A）

见同项目 `拆单比对/SKU_人工备注.md`：126 米白曾因夹名 6pack 误导，靠页内 `126-6`/`126-10` 拆分；**待总表补 SKU 后，将该两规格的 SKU 写入备注并沉淀**。
