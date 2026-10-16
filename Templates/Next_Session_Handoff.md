# AutoExport — 新对话交接包（压缩版）

> 项目根：`D:\.cursor\Cursor-projects\AutoExport`  
> 本包刷新：**2026-10-16**（准备上新 · neat-freak 轻量）  
> 阶段用词：`.cursor/rules/shipment-pipeline-order.mdc`（禁止「外箱贴→货代」）  
> 回合收尾：`.cursor/rules/session-turn-closeout.mdc`（四行结论）  
> 外箱贴归夹：`.cursor/rules/carton-spec-layout-gate.mdc` + `Templates/Carton_Label_Channels.md` §2.1

---

## 远期备案（上新提一次）

- **多票/库存洞察**：字段仍待你定 → `Templates/Backlog_Multi_Ticket_Inventory.md`
- **发货统计轨**：`发货统计/cv_bundle_20260828`；主表已补 C26105/106 与 1–7 月包/箱（库缺规格已按 2026-10-09 确认锁定）→ `Templates/Ship_Stats_Correspondence.md`

---

## 票进度

### Gate CONFIRMED · Final 齐（勿重做除非纠错）

| 票 | Final / 微信 zip |
|----|------------------|
| C26089 | `3_Output_Final/EF-C26089-C07-40000_C07_20260821_40000/` |
| C26095 | `3_Output_Final/EF-C26095-C07-7800_C07_20260829_7800/` |
| C26100 | `3_Output_Final/EF-C26100-C07-12000_C07_20260919_12000/` |
| C26105 | `3_Output_Final/EF-C26105-C04-17360_C04_20261001_17360/` · `C26105_2026.10.10_微信发送.zip` |
| C26106 | `3_Output_Final/EF-C26106-C07-12820_C07_20261001_12820/` · `C26106_2026.10.1_微信发送.zip` |

### 进行中 · C26110（未 Gate / 未 Final）

| 项 | 值 |
|----|-----|
| 项目夹 | `1_Input_Raw/Shipments/EF-C26110-C07-20000_C07_20261030_20000/` |
| 订单 | `EF-C26110-C07-20000` · C07/Dressmaker · 下单 2026.10.10 · 交货/出货日 **2026.10.30** |
| 规格 | 60X102 · 白 · 10条/包 · **500箱 / 20000条** · FNSKU `X004SJV9UF` · 4包/箱 |
| 出货短号 | **C07-2613**（本机序列；下一 C07=**C07-2614**，C04 下一=**C04-2619**）→ `Scripts/outbound_short_seq.json` |
| AWD | **IUSW** · STAR-`RQGSBZGZZDQYQ` · 追踪 `3ZX8AH2H` · 址已入 `amazon_warehouse_addresses.json` |

| 阶段 | 状态 |
|------|------|
| P-ORDER | ✅ `订单表/EF-C26110-C07-20000  桌布-2026.10.30.xlsx` |
| P-OUT | ✅ `出货表/C07-2613-U-2026.10.30.xlsx` |
| P-LABEL | ✅ `产品标签/…/10条装/60x102/102白-10条.pdf` |
| P-FREIGHT | ✅ 货代下单 + 报关（IUSW 500箱） |
| P-CARTON | ✅ `FBA外箱贴/AWD/IUSW/白_60X102inch_10条装/AWD_IUSW_白_60X102inch_10条装_500箱.pdf`（500页=计划） |
| P-INBOUND | ❌ 等货代入库贴放 `_inbox` |
| P-GATE / P-FINAL | ❌ |

**编号规则（本会话确认）**：订单 EF 长号全公司共用→**每次你给**；出货短号本机按 **C04/C07 各一条序列**递推（`outbound_short_seq.json`）。

**P-CARTON 注意**：`10` 对 IUSW 可能抽不出仓码（码尾非数字→`_no_wh`）；按登记仓 **IUSW** 迁入后再 `17_reorg`。正式件在规格夹；`_staging` / `.flat_pages_bak_*` 为残留。

---

## 固化规则（勿回退）

| 项 | 位置 |
|----|------|
| 外箱贴：`10` 拆页 ≠ 完工；promote 后必须 `17_reorg` | `carton-spec-layout-gate.mdc` · Carton §2.1 |
| 微信 zip：贴标包打成 `{短号}_{出货日}_微信发送.zip`，不含完整存档 | `Colleague_Pack_Export.md` |
| 包/箱=尺寸+条/包（与颜色无关）；新增锁定见下 | `packing_locked_by_size_spp`（2026-10-09） |

**2026-10-09 新增锁定（包/箱）**：84+6=8；84+2=24；126+6=6；120+6=5；60圆+6=15。

---

## 洁癖轻量（2026-10-16）

| 面 | 状态 |
|----|------|
| 代码/脚本 | `verified-current` — 05/09/10/17 仍现役；IUSW 已写入仓址库 |
| 文档 | `changed-and-verified` — 本交接包刷新 |
| 规则 | `verified-current` — pipeline / carton / 出货短号规则未改口径 |
| 运行态 | `not-applicable` — 本轮不做云端核对 |
| 工作区 | `pending` — drafts 临时脚本；C26110 `_staging` 散页与 `.flat_pages_bak_*` |

**删除候选（未删，待你确认）**

- `2_Processed_AI/drafts/`：`_gen_C26110_*` / `_setup_C26110_*` / `_qty_plan_C26110*` / `_append_ship_stats_*` / `_ship_stats_*` / `_reorg_carton_*` 等一次性脚本与旧数量草稿
- C26110：`FBA外箱贴/_staging/AWD/_no_wh/`（500 散页半成品，正式 PDF 已在规格夹）
- C26110：`FBA外箱贴/AWD/IUSW/.flat_pages_bak_20261010_*`
- 历史：105/106 `IUTJ/.flat_pages_bak_*`（若仍在）

**遗留（非阻断）**

- C26110 发货统计是否写入主表：未做（Final 后再补亦可）
- 发货统计 5 月「灰蓝/米黄」2 行仍无条/包，包/箱空着

---

## 新对话提示词

```text
继续 AutoExport（D:\.cursor\Cursor-projects\AutoExport）。先读 Templates/Next_Session_Handoff.md（2026-10-16）。

硬规则：shipment-pipeline-order.mdc + session-turn-closeout.mdc + carton-spec-layout-gate.mdc；列 Shipments 用 python os.walk（忌 Glob 判 PDF）。

现状：
- C26089/95/100/105/106：Gate CONFIRMED · Final 齐（勿重做除非纠错）
- **进行中 C26110**：Shipments/EF-C26110-C07-20000_C07_20261030_20000
  · C07 · 出货 C07-2613 · 日 2026.10.30 · 500箱/20000条 · 102白10条 · FNSKU X004SJV9UF
  · AWD IUSW · STAR-RQGSBZGZZDQYQ · 追踪 3ZX8AH2H
  · 已齐：P-ORDER / P-OUT / P-LABEL / P-FREIGHT（货代+报关）/ P-CARTON（白_60X102inch_10条装 500箱 PDF）
  · 未齐：P-INBOUND（等入库贴 inbox）→ 再 Gate → Final+微信 zip
- 订单号你给；出货短号本机递推（C07 下一=C07-2614，C04 下一=C04-2619）
- P-CARTON=17_reorg 归夹；IUSW 可能被 10 判成 _no_wh，按登记仓迁入即可

下一优先：等货代入库贴进 _inbox 后跑 12 → Gate → 13 Final；或你另开新票。

每轮四行：已完成 / 未完成 / 下一步 / 状态词。
```
