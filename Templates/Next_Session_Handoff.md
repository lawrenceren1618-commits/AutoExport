# AutoExport — 新对话交接包（压缩版）

> 项目根：`D:\.cursor\Cursor-projects\AutoExport`  
> 本包刷新：**2026-08-31**（规则固化 · C26100 Final 齐）  
> 阶段用词：`.cursor/rules/shipment-pipeline-order.mdc`（**禁止**写「外箱贴→货代」）

---

## 远期备案（上新时提一次）

- **多票/库存洞察**：`Templates/Backlog_Multi_Ticket_Inventory.md`  
- **发货统计**（与做单分轨）：`发货统计/cv_bundle_20260828` · `Scripts/ship_stats_freight_allocate.py` · `Templates/Ship_Stats_Correspondence.md`

---

## 票进度（至 2026-08-31）

### Gate CONFIRMED · Final 齐（勿重做除非纠错）

| 票 | Final |
|----|-------|
| C26089 | `3_Output_Final/EF-C26089-C07-40000_C07_20260821_40000/` |
| C26095 | `3_Output_Final/EF-C26095-C07-7800_C07_20260829_7800/` |
| **C26100** | `3_Output_Final/EF-C26100-C07-12000_C07_20260919_12000/` |

### C26100 阶段（均已完）

| 阶段 | 状态 |
|------|------|
| P-ORDER / P-OUT / P-LABEL | ✅ |
| P-FREIGHT（货代+报关 `09`） | ✅ 物易通 IUTJ 300箱 · `20260919501` |
| P-CARTON | ✅ 300 页 → `FBA外箱贴/AWD/IUTJ/…` |
| P-INBOUND | ✅ 300 页三重验证 PASS |
| P-GATE | ✅ CONFIRMED · `cross_check_…_20260831_150812.json` |
| P-FINAL | ✅ 完整存档 + 贴标包 + 微信 zip |

---

## 下一优先（分轨）

**做单轨**

1. 新票：按 `shipment-pipeline-order.mdc` — 登记齐 → P-FREIGHT → **停等上传贴** → P-CARTON / P-INBOUND → Gate → Final  
2. 订单 last **C26100** / next **C26101**；出货 C07 next **2612**

**发货统计轨**（不与做单混在同一轮 unless 明示）

- 物易通运费空行 · 剩余包/箱列

**Git**：大量未提交；**未 push**（等明示）

---

## 新对话提示词

```text
继续 AutoExport（D:\.cursor\Cursor-projects\AutoExport）。先读 Templates/Next_Session_Handoff.md。

做单规则：.cursor/rules/shipment-pipeline-order.mdc + session-turn-closeout.mdc

现状：
- C26089/C26095/C26100：Gate CONFIRMED，Final 已出（勿重做）
- 下一单建议 C26101
- 发货统计与做单分轨；Git 未 commit/push，等明示

每轮结束必须：已完成/未完成/下一步/状态词。
```
