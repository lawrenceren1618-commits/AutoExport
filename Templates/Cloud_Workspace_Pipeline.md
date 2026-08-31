# 云端作业台流水线（按 B 组成 · 不以本地 B 为运行路径）

> 确认日：2026-07-27（流程 UI 对齐 1B+2C）  
> 机器：`Scripts/cloud_workspace_pipeline.json` · `web/lib/pipeline/*`  
> 部署：Vercel Root=`web` · 数据 schema=`autoexport` · Storage 桶见 migration

## 原则

1. **运行时** = 云端 `/workspace` + Supabase（表 + Storage）。  
2. **前台 UI** = 仅 **输入 / 输出**（提取、处理不单独展示；由输入区按钮 + 预检驱动）。登录便于存档与沉淀精度。  
3. **库务** = `/ops`（总表 H01、进度树、**发货存档索引**、FBA 仓头/追踪）；不塞进做单主路径。旧 `/admin/*` 重定向到 `/ops/*`。  
4. **组成参考** = 原 B（Shipments）分部；**本地 B** 仅归档/样例，非日常作业路径。  
5. **根本库** = settled（JSON + `autoexport.settled_*` / `settled_config`）。本机 settled JSON 权威，禁 cloud→本地 settled 回写。  
6. Gate（HX）未通过 + 未用户确认 → 不得 Final / 正式汇总存档。  
7. **订单号自动生成**：`EF-{CyyNNN}-{C0X}-{总条数}`（`Scripts/order_code_seq.json`，next=**C26083**）；出货短号 `Scripts/outbound_short_seq.json`（C04→**2618**，C07→**2609**）。

## 阶段 ↔ 模块

| 层 | 内容 | 握手 |
|----|------|------|
| **前台·输入** | 发货计划 →（订单/产品标签包后）外箱贴与追踪（多仓逐行+OCR，确认后）→（货代表后）入库贴 | |
| **后台波次** | 提取规格键/仓×规格；总表补齐、分批判定、Gate（不单独做 Tab） | HX |
| **前台·输出** | 订单 → **产品标签包** → 出货/货代/报关（同波次）→ **发货贴标包** → 存档 | H12/H42/H13 |

> `upload`/`download` 已接 Storage（本地 blob 回退）。`gen_order` / 出货 / 标签只读复制 / `09` 参数化已接 Python 桥。详见 [`Storage_Python_Bridge.md`](Storage_Python_Bridge.md)。已知缺口：贴标包 zip 仍契约；部分中文路径曾落 local blob。

| 输出物 | 模块 |
|--------|------|
| 订单表 / 出货表 | M1 |
| 货代下单表 | M2 |
| 报关单证 | M3 |
| 产品标签包 | 标签源只读复制 |
| 发货贴标包 | pack / Colleague_Pack |
| 汇总存档 | archive（Final 后）；**索引**见 `/ops/archives`（年/月/日树，整票一行，无物理三级夹） |

字段层级见 `Scripts/canonical_schema.json`；业务默认见 `settled_knowledge_db.json` → `flow_ui_alignment_2026_07_27`。

## 保存模式

| 模式 | 含义 |
|------|------|
| upload_raw | Storage 原件不可变 + sha256 |
| draft | 生成草稿 |
| pre_final | 可下载，Gate WAIT |
| final | HX + 用户确认 |
| archive | 审查向打包 |

## API（概要）

见 JSON `apis`；实现于 `web/app/api/jobs/**`（含 `run` / `gate`；创建时自动发号）。
