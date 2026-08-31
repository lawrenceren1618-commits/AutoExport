# 发货项目 · 产品标签落盘与映射（固定规则）

> **本格式已固定为全局规则**，生成/复制标签必须遵守。  
> 闸门：`.cursor/rules/label-source-gate.mdc`  
> JSON：`Scripts/canonical_schema.json` → `label_output_layout` / `size_folder_map` / `color_aliases`

## 1. 固定落盘路径

```text
1_Input_Raw/Shipments/{项目名}/产品标签/
  {EF订单号}标签/
    {N}条装/
      {尺寸短码}/
        {标签源原文件名}.pdf
  _manifest.json
  _design_match.json
```

**禁止**：`by_fnsku/`、扁平无条装夹、修改 PDF 文件名、用 FNSKU 命名。

## 2. 映射关系（固定）

### 2.1 条装夹

| 订单字段 `strips_per_pack` | 文件夹名 |
|----------------------------|----------|
| 2 | `2条装` |
| 6 | `6条装` |
| 10 | `10条装` |
| 其它正整数 N | `{N}条装` |

### 2.2 尺寸映射（短码 ↔ 订单全称 ↔ 标签夹）— 已确认 2026-07-21

| 总表短码 | 订单全称（canonical 展示） | 标签夹名 |
|----------|----------------------------|----------|
| 84 | `60X84inch` | `60x84` |
| 102 | `60X102inch` | `60x102` |
| 126 | `60X126inch` | `60x126` |
| **120** | **`70X120inch`** | `70x120` |
| 90圆 | `90 inch round` | `90圆` |

机器可读：`canonical_schema.json` → `size_shortcode_map` + `size_folder_map`。  
未收录尺寸 → 汇报后补表。

### 2.3 颜色（核心锁定维 + 别名）

| canonical | 同色写法 |
|-----------|----------|
| 白 | 白、白色 |
| 黑 | 黑、黑色 |
| 蓝 | 蓝、蓝色 |
| 米白 | 米白、米白色、象牙、象牙色、象牙白、象牙白色、Ivory、ivory |

### 2.4 FNSKU 双向锁定键

`brand | size | strips_per_pack | color | product_name_zh` ↔ `fnsku`  
（克重不在锁定键内；**90↔110 可互通**；150+ 不与之混锁；亚马逊只认 FNSKU）

### 2.5 标签源匹配 → 落盘

1. 在标签源按 **品牌夹** + **条装** + **尺寸** + **颜色别名** 找 PDF（**90/110** 克重夹可忽略差异；**150+** 不得误用 90/110 标签）  
2. `copy2` → `{EF订单号}标签/{N}条装/{尺寸短码}/{原文件名}`  
3. `_manifest.json` 记录 `fnsku`、`source_rel`、`dest_rel`（供核对）

## 3. 本票样例（EF-C26079）

`产品标签/EF-C26079-C04-36460标签/6条装/60x102/….pdf` 等，共 23 个 PDF。
