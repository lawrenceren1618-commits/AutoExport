# 交叉流动核对（事后 / 全单据）

> 确认日：2026-07-30  
> 机器：`Scripts/cross_flow_rules.json` · `Scripts/m1/post_gen_verify.py` · `Scripts/20_post_gen_verify.py`  
> 原则：**数据从来不是孤立的**——按既定规则流动；权威源不同的表不得强行「字段全部对齐」。

## 与其它闸门

| 闸门 | 时机 | 管什么 |
|------|------|--------|
| 预检 | 生成前 | 字段是否够 |
| **本文件** | 写入后 / 补验 | 身份键 + **按权威源**勾稽 |
| Gate HX | Final 前 | 沉淀 + 复用本核对；须你确认 |

## 权威源（强制）

| 单据 | 权威 | 可对照但不强齐 |
|------|------|----------------|
| 出货「所属订单」 | 订单 EF → 短码 | — |
| **报关**单价/条数/货值 | **总表 1039 + 沉淀库 + 正算反算**（`Amount_Weight_Reconcile`） | 货代单价/implied 条数 |
| 货代 F15 单箱数量 | `floor(仓条÷仓箱)`（可少余数） | 报关条数 |
| 货代/报关 **箱数** | 外箱贴确认行（严格来源） | 两表箱数互相对照 |
| 报关表内抬头 | 波丽丝（**参考**核对） | 非与货代统一字段 |
| 合同协议号 | 登记库；**生成后程序复查** | — |

禁止：拿货代取整后的条数/单价去「纠正」报关；报关必须以总表/沉淀为准。

## 身份键

| 键 | 必须一致 |
|----|----------|
| `order_code` EF | PROJECT ↔ 订单表 ↔ 标签夹 ↔ 报告（禁串票） |
| `order_short` | 出货「所属订单」↔ EF 抽出短码 |
| `outbound_short` | PROJECT ↔ 出货 G2 ↔ 文件名 |
| 仓 / FBA / 协议号 / 腿号 | 见规则 JSON |

## C26079 Shipments 所属订单空 — 根因（已核实）· 已回写

见会话 [出货表版式修复](f91e3df1-92a1-4b43-ab5f-0d82b9c57832)：

1. **初填（~7/21）**：当时规则「所属订单留空」→ Shipments F5 空。  
2. **7/29**：只成功改了 **完整存档**；Shipments 正本未落盘（mtime 仍 7/21）。  
3. **7/30**：已用完整存档 **回写** Shipments；F5=`C26079`；事后核对两侧 PASS。  
4. **单向复制**：修表须先改 Shipments，再 `13_export`。  
5. 另：`C26079-A_freight_customs_summary.json` 曾被 C26082 同名覆盖（待清理）。

## 可预期技术栈（本地 = 云端同一套规则）

```text
权威规则（唯一）
  Scripts/cross_flow_rules.json + Templates/01|02|03 + Amount_Weight_Reconcile
        │
        ▼
生成器（Python，本地与云端同源）
  Scripts/19_cloud_job_step.py  ← web generate-bridge 只 spawn，不另写业务口径
  m1/outbound_fill · 09_generate_freight_customs_drafts · label_copy
        │
        ▼
事后核对（同脚本）
  m1/post_gen_verify.verify_* → 2_Processed_AI/cross_check_reports/post_gen_*.json
        │
        ▼
工作正本：1_Input_Raw/Shipments/{项目}/
输出副本：3_Output_Final/…（只复制；修表必须先改 Shipments 再导出）
```

| 面 | 约定 |
|----|------|
| 本地 CLI | `python Scripts/20_post_gen_verify.py --project "…"` |
| 云端作业 | 同 `19` + `post_gen`；失败 → issues 全量回 job |
| 修出货/货代/报关 | **只写 Shipments**；再跑 `13_export` 更新存档 |
| 报告文件名 | 须含 `order_short`/`leg_id`，禁止多票共用一个 summary 路径 |

## 用法

```text
python Scripts/20_post_gen_verify.py --project "1_Input_Raw/Shipments/<项目夹>"
```
