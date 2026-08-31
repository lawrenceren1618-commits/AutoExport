# 上传说明 — EF-C26080 + EF-C26068 并批

状态：`WAIT_UPLOAD`（放入后通知助手；先汇总报错，确认后再生成单据）

主规则：`Templates/Multi_Order_Ship_Batch.md`（既有 C04 单票规则不改，只补充）

## 绝对路径（请把文件放这里）

| 内容 | 绝对路径 |
|------|----------|
| **项目根** | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26080_待识别\` |
| **订单**（C26080 + C26068 的 xls/xlsx） | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26080_待识别\订单表\` |
| **外箱贴**（两批可混放） | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26080_待识别\FBA外箱贴\_inbox\` |
| **外箱贴·可分批 A** | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26080_待识别\FBA外箱贴\_inbox\batch_A\` |
| **外箱贴·可分批 B** | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26080_待识别\FBA外箱贴\_inbox\batch_B\` |
| **货代入库贴**（后置） | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26080_待识别\货代入库贴\_inbox\` |
| **其它附件** | `D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26080_待识别\_来源归档\` |

## 规则摘要

- C26080 → `C26080-A` / `C26080-B`；C26068 并入其中一批（识别后落定）
- 同一出货日 → 一张出货表；货代/报关以仓为核心；订单总条数/总箱数交叉核对
- 遇错全部汇报，待你确认后继续（`.cursor/rules/error-confirm-gate.mdc`）
- 若本票为 C07：处理口径参照 C04，仅店铺/品牌/FNSKU 换对应关系（`c07_inherits_c04_pipeline`）
