# cv_bundle_20260828 — 发货记录交叉验证包

**打包日**：2026-08-28  
**用途**：给库存/财务技能作发货部分 **只读交叉验证** 数据源。

## 快速路径

```text
D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\00_Master_Reference\发货统计\cv_bundle_20260828\
```

## 先读

1. `cross_validation_guide.md` — 接入说明、主键、公式、提示词
2. `manifest.json` — 文件索引
3. `rows_flat.json` — 扁平行数据（319 行）

## 本包含

| 类型 | 文件 |
|------|------|
| 数据 | `2026年发货记录.xls`、`rows_flat.json` |
| 结构 | `column_schema_v3.json` |
| 运算 | `ship_stats_size_dims.json`、`Ship_Stats_Freight_Allocation.md` |
| 业务规则 | `Ship_Stats_Correspondence.md`、`field_map.json` |
| 质量 | `known_gaps.json` |
| 工具 | `ship_stats_freight_allocate.py` |

**说明**：本夹为快照；AutoExport 内 live 主表仍在 `../_inbox/2026年发货记录.xls`。
