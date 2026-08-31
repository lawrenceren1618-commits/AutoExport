# 报关合同协议号（去重与登记）

> 确认日：2026-07-24  
> 机器：`Scripts/contract_protocol.py` · 登记库 `Scripts/contract_protocol_registry.json`  
> 沉淀：`settled_knowledge_db.json` → `confirmed_defaults.customs_contract_protocol_no`

## 0. 问题

同一**发货日**下，多票发货计划、多仓报关时，若各票各自写死/随机三位后缀，容易生成**相同合同协议号**。海关侧**不允许重复**。

## 1. 格式（强制）

```text
{YYYYMMDD}{NNN}
```

| 段 | 说明 |
|----|------|
| `YYYYMMDD` | 出货日数字版（与报关文件名日期口径一致） |
| `NNN` | **三位**可变项；习惯自 **501** 起递增（501、502、503…；示例里也曾用 506） |

例：`20260731501`、`20260731502`。

**只改 `NNN`**；日期段与整体位数不变。

## 2. 唯一性范围

- **全局唯一**：整号不得与登记库中任一已占用号重复（含不同发货计划、不同店铺、同日多票）。  
- **同计划多仓**：每仓一个号，互不相同。  
- **同日不同计划**：必须先检索登记库，再分配未占用后缀。

## 3. 生成流程（强制）

```text
1. 确定出货日 → YYYYMMDD
2. 读 Scripts/contract_protocol_registry.json（已占用集合）
3. 若本票本仓已登记过 → 复用原号（幂等，不新占）
4. 否则从 NNN=501 起找第一个未占用后缀（501→999，再 001→500）
5. 写入报关表「合同协议号」单元格
6. 立刻登记：protocol_no + ship_date + project + warehouse + order/plan 键 + 时间
```

冲突或三位耗尽 → **报错全量汇报，停**，不得静默复用他仓号。

## 4. 登记库字段

| 字段 | 说明 |
|------|------|
| `protocol_no` | 完整号 |
| `ship_date` | `YYYY-MM-DD` 或 `YYYYMMDD` |
| `project` | 发货项目夹名 |
| `warehouse_code` | 仓码 |
| `order_or_plan` | EF / 腿 / 计划短码（可空） |
| `allocated_at` | ISO 时间 |

助手/脚本**只追加或幂等复用**；禁止未确认批量清空登记库。

## 5. 与既有报关规则

- 表内其它栏位仍按 [`03_Customs_Correspondence.md`](03_Customs_Correspondence.md)（抬头/1039/变更项）。  
- 端到端 P8 指向本文件。  
- C07 继承 C04 流水线时，**协议号规则同样适用**（仅抬头/FNSKU 不同）。

## 6. 已确认样例（2026-07-24）

项目 `EF-C26080-C07-11590_C07_20260731_13590`，出货日 2026-07-31：  
原 `…801–806` 与同日 C26079-A 撞号 → **重开**为 `…501–506`（SCK8→PSP3）并改表 `基础表` 合同协议号格；登记库 + `settled_knowledge_db.confirmed_defaults.customs_contract_protocol_no.verified_sample`。
