# 出货表样本字段扫描

扫描范围: Shipments / 01_Order_Outbound / Templates / 3_Output_Final

## 选用的样本（最多 2 个）

- `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\C04-2615-U_C04_20260624_TBD\出货表\C04-2615-U-2026.6.24.xlsx`
- `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26037-C07_C07_20260517_400CTN\出货表\C07-2604-U-2026.5.17.xlsx`

---

## 样本: `C04-2615-U-2026.6.24.xlsx`

完整路径: `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\C04-2615-U_C04_20260624_TBD\出货表\C04-2615-U-2026.6.24.xlsx`

### 工作表

- Sheet1

### `Sheet1` 结构网格（前 40 行）

行数展示: 18（列宽至 9）

R1C1=发货单
R2C1=订单发货日期： | R2C2=2026.6.24 | R2C6=客户及订单号： | R2C7=C04-2615
R3C1=订单数量： | R3C2=29950 | R3C6=业务员： | R3C7=任胜国
R4C1=产品品类 | R4C2=重量 | R4C3=尺寸规格 | R4C4=颜色 | R4C5=数量 | R4C6=所属订单 | R4C7=所属仓库 | R4C8=备注 | R4C9=目的地
R5C1=单面磨毛纤维桌布 | R5C2=110克/平方米 | R5C3=60X84inch | R5C4=白 | R5C5=4800 | R5C6=C26064 | R5C9=US
R6C3=60*102inch | R6C4=白 | R6C5=6000
R7C3=60*102inch | R7C4=米白 | R7C5=6470
R8C3=60*102inch | R8C4=蓝 | R8C5=2100
R9C3=90圆 | R9C4=白 | R9C5=3900
R10C3=90圆 | R10C4=米白 | R10C5=3080
R11C3=60*126inch | R11C4=白 | R11C5=1800
R12C3=60*126inch | R12C4=米白 | R12C5=600
R13C3=70*120inch | R13C4=白 | R13C5=1200
R14C1=合计 | R14C5=29950

### 页眉/列标题类非空单元格（前 15 行）

R1C1=发货单
R2C1=订单发货日期：
R2C2=2026.6.24
R2C6=客户及订单号：
R2C7=C04-2615
R3C1=订单数量：
R3C2=29950
R3C6=业务员：
R3C7=任胜国
R4C1=产品品类
R4C2=重量
R4C3=尺寸规格
R4C4=颜色
R4C5=数量
R4C6=所属订单
R4C7=所属仓库
R4C8=备注
R4C9=目的地
R5C1=单面磨毛纤维桌布
R5C2=110克/平方米
R5C3=60X84inch
R5C4=白
R5C5=4800
R5C6=C26064
R5C9=US
R6C3=60*102inch
R6C4=白
R6C5=6000
R7C3=60*102inch
R7C4=米白
R7C5=6470
R8C3=60*102inch
R8C4=蓝
R8C5=2100
R9C3=90圆
R9C4=白
R9C5=3900
R10C3=90圆
R10C4=米白
R10C5=3080
R11C3=60*126inch
R11C4=白
R11C5=1800
R12C3=60*126inch
R12C4=米白
R12C5=600
R13C3=70*120inch
R13C4=白
R13C5=1200
R14C1=合计
R14C5=29950


### 数据区样例行（启发式：跳过前 10 行后的前 10 条非空行）

C3=60*126inch | C4=白 | C5=1800
C3=60*126inch | C4=米白 | C5=600
C3=70*120inch | C4=白 | C5=1200
C1=合计 | C5=29950


### 列填充 vs 静态（基于样例 20 行）

- 列 C1: 逐行变化 — 样例: ['合计']
- 列 C3: 静态/重复 — 样例: ['70*120inch', '60*126inch']
- 列 C4: 静态/重复 — 样例: ['白', '米白']
- 列 C5: 逐行变化 — 样例: ['1200', '29950', '600', '1800']

---

## 样本: `C07-2604-U-2026.5.17.xlsx`

完整路径: `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26037-C07_C07_20260517_400CTN\出货表\C07-2604-U-2026.5.17.xlsx`

### 工作表

- Sheet1

### `Sheet1` 结构网格（前 40 行）

行数展示: 10（列宽至 9）

R1C1=发货单
R2C1=订单发货日期： | R2C2=2026.5.17 | R2C6=客户及订单号： | R2C7=C07-2604
R3C1=订单数量： | R3C2=16000 | R3C6=业务员： | R3C7=任胜国
R4C1=产品品类 | R4C2=重量 | R4C3=尺寸规格 | R4C4=颜色 | R4C5=数量 | R4C6=所属订单 | R4C7=所属仓库 | R4C8=备注 | R4C9=目的地
R5C1=单面磨毛纤维桌布 | R5C2=90克/平方米 | R5C3=60X102inch | R5C4=白 | R5C5=16000 | R5C6=C26037 | R5C7=CF012 | R5C9=US
R6C1=合计 | R6C5=16000

### 页眉/列标题类非空单元格（前 15 行）

R1C1=发货单
R2C1=订单发货日期：
R2C2=2026.5.17
R2C6=客户及订单号：
R2C7=C07-2604
R3C1=订单数量：
R3C2=16000
R3C6=业务员：
R3C7=任胜国
R4C1=产品品类
R4C2=重量
R4C3=尺寸规格
R4C4=颜色
R4C5=数量
R4C6=所属订单
R4C7=所属仓库
R4C8=备注
R4C9=目的地
R5C1=单面磨毛纤维桌布
R5C2=90克/平方米
R5C3=60X102inch
R5C4=白
R5C5=16000
R5C6=C26037
R5C7=CF012
R5C9=US
R6C1=合计
R6C5=16000


### 数据区样例行（启发式：跳过前 10 行后的前 10 条非空行）



### 列填充 vs 静态（基于样例 20 行）
## Scripts / 文档中的出货字段映射（仓库内检索）

### Templates/01_Order_Outbound_Correspondence.md
- 出货表短号：C04/C07-{序号}-U-{日期}；**不含 FNSKU**
- 源→出货映射：颜色、尺寸、条数/总条数、克重、箱数等；FNSKU 仅订单装箱明细
- 装箱 canonical keys：size, color, strips_per_pack, nsku, packs_per_carton, qty_cartons, qty_strips, 内外箱尺寸
- 生成入口：Scripts/05_generate_order.py + Scripts/m1/（订单侧重；出货生成待扩展）

### Scripts/_build_field_inventory.py
- 扫描 1_Input_Raw 下 xls/xlsx，输出 Scripts/field_inventory.json（字段清单/列名发现）

### Scripts/m1/（与出货间接相关）
- parse_master.py / ssemble.py / ill_template.py：订单模板填充与总表解析
- 未发现独立「生成出货表」脚本；出货结构以上述 correspondence + Shipment 样例为准
