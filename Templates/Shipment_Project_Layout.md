# 发货项目制（Shipment Project）组织规则

> 每一票发货 = 一个项目文件夹。不再用「01/02/03 三分法目录」作为日常归类主轴（三分法 Correspondence 文档仍描述单据类型）。  
> 物理根目录：`1_Input_Raw/Shipments/`（**处理黑箱**）  
> **用户端简洁 IO**（输入/输出/汇总存档）：`User_IO/` — 见 [`User_IO_Layout.md`](User_IO_Layout.md)。  
> **输出端两包**（旧仓，仅复制）：`3_Output_Final/{同一项目名}/…`。见 [`Colleague_Pack_Export.md`](Colleague_Pack_Export.md)。Gate→Final 业务闸门仍独立。  
> 多单并腿补充：[`Multi_Order_Ship_Batch.md`](Multi_Order_Ship_Batch.md)。
## 1. 项目文件夹命名

```text
{订单号}_{店铺代码}_{出货日期YYYYMMDD}_{条数}
```

例：`EF-C26039-C07-10540_C07_20260524_10540`

| 段 | 说明 |
|----|------|
| 订单号 | 优先工厂 EF 长号；仅有出货短号时用短号并后续补映射 |
| 店铺代码 | `C04` / `C07` |
| 出货日期 | 实际发货日 |
| 条数 | 本票总条数；未知时暂用 `TBD` 或 `NNNCTN`（箱数占位），确认后改名 |

每项目含 `PROJECT.json` 元数据。

## 2. 子文件夹（固定）

| 子文件夹 | 谁产生 | 说明 |
|----------|--------|------|
| `订单表/` | **系统生成** | 固定中文备货+装箱模板 |
| `出货表/` | **系统生成** | C04/C07-U 版式 |
| `货代入库贴下单表/` | **系统生成** | 货代下单模板填空 |
| `报关资料表/` | **系统生成** | 报关套表 |
| `产品标签/` | 自标签源**复制** | **固定**：`{EF订单号}标签/{N}条装/{尺寸}/原名.pdf`（见 [`Shipment_Product_Label_Layout.md`](Shipment_Product_Label_Layout.md)） |
| `FBA外箱贴/` | **使用者后续更新** | FC/AWD 外箱贴（GWD 停用）；可上传原包后由助手识别拆分归纳（见 [`Carton_Label_Channels.md`](Carton_Label_Channels.md)）；确认后的**货代入库贴**一仓一 PDF 亦落在对应 `{渠道}/{仓码}/`（见 [`Freight_Inbound_Label_Pipeline.md`](Freight_Inbound_Label_Pipeline.md)） |
| `拆单比对/` | **系统生成** | 拆单时：`split_ledger.json`（计划/已发/剩余）；见 [`Split_Shipment_Ledger.md`](Split_Shipment_Ledger.md) |
| `货代入库贴/` | **使用者后续更新** | 货代回传 PDF：`_inbox` / `_staging` / `_recognize`；与「下单表」区分；正式件写入 `FBA外箱贴/…` |
| `_来源归档/` | 历史样例 | 采购、信息表、旧模板等辅助 |

识别规则（读历史包时）：

- 使用者**提供路径优先**；路径空/不精确时：该路径 **下一级 → 上一级 → 同级**（见 `.cursor/rules/user-path-resolve.mdc`）。
- 文件名含 `EF` → 订单表样例  
- `C04`/`C07` 开头且像 `C04-2615-U-日期` → 出货表样例  
- 路径/名含「货代入库贴下单」「货代下单」→ 货代入库贴下单表  
- 含「报关」或「1039」→ 报关资料表  
- `FBA….pdf` / 外箱贴目录 → FBA外箱贴  
- 其它 → `_来源归档` 或产品标签  

近端当票订单源：以项目 `订单表/` 为准（例：`Shipments/EF-C26079-C04-36460  桌布-2026.7.10/订单表`）。

## 3. 总表位置

人工产品总表：**不**拆进各发货项目，固定：

`1_Input_Raw/00_Master_Reference/`

字段比对见：`2_Processed_AI/cross_check_reports/master_vs_docs_field_compare_20260720.md`（⚠ 项确认前不写死沉淀）。

## 4. 与模块握手

- M1 订单/出货 → 写入项目内 `订单表/` `出货表/`（先 drafts，Gate 后 Final）  
- M2 货代下单 → `货代入库贴下单表/`（仓/FBA 来自 M4 确认后）  
- M3 报关 → `报关资料表/`  
- M4 → 使用者更新 `FBA外箱贴/`；下单用仓码来自确认后的货件信息  

## 5. 历史迁移说明

原 `00_Master_Reference/5月发货计划/` 已 **复制**（非删除）到 `Shipments/` 各项目。源目录可保留作备份，确认无误后再删。
