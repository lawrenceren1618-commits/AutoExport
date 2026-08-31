# 事后核对（出货表优先）

> 确认日：2026-07-30  
> 机器：`Scripts/m1/post_gen_verify.py` · `Scripts/20_post_gen_verify.py`  
> 全单据扩展（货代/报关权威源等）：[`Cross_Flow_Verify.md`](Cross_Flow_Verify.md)

## 与其它闸门

| 闸门 | 时机 | 管什么 |
|------|------|--------|
| 预检 `Document_Field_Preflight` | **生成前** | 字段是否够；出货 **所属订单短码** 为 required |
| **本文件 · 事后核对** | **出货 xlsx 刚写入后** | 写入值是否符合对应关系 |
| Gate HX `03_cross_validate` | Final 前 | 复用 `verify_project`（含出货） |

硬失败 → 全量 findings + 阻断 `gen_trio`（不继续货代/报关）。`gen_order` 后 `verify_order_artifact` 失败则阻断该步。

## 订单硬项（摘要 · 2026-08-14）

| 检查 | 期望 |
|------|------|
| 下半总条数 G | `=C{r}*E{r}*F{r}`（C26079） |
| 上半数量 F | 引用对应下半 G（如 `=G15`） |
| 纸箱/内盒行 | 内盒{沉淀库 LWH}；外箱 **`纸箱：{LWH}`**（禁止误写成「纸箱规格：…cm」） |
| 热缩行 | 热缩膜包装；外箱 `纸箱规格：{LWH}cm` |

版式母版：`Templates/order_layout_master.xlsx`。LWH 权威：`packing_standards`。

## 出货硬项（摘要）

| 检查 | 期望 |
|------|------|
| 文件名 | `{outbound_short}-U-{日期}.xlsx` |
| G2 客户及订单号 | `outbound_short`（无 U、无日期） |
| 发货日 | = 订单交货日口径 `YYYY.M.D` |
| F5 所属订单 | 订单短码 `Cxxxxx`（非空；≠ EF 长号、≠ 出货短号） |
| 明细合计 / `=SUM` | 与 PROJECT / 表头数量勾稽 |
| 无 FNSKU | 出货表不得出现 FNSKU |

对照：`order_code`（EF）↔ `order_short`（所属订单）↔ `outbound_short`（G2）。

## 挂接

- `19_cloud_job_step.step_gen_trio`：`fill_outbound_template` 后立刻 `verify_outbound_file`
- `03_cross_validate`：项目级 `verify_project`
- CLI：

```text
python Scripts/20_post_gen_verify.py --project "1_Input_Raw/Shipments/<夹>"
python Scripts/20_post_gen_verify.py --xlsx <出货.xlsx> --order-code EF-... --order-short Cxxxxx --outbound-short C04-2616 --ship-date 2026-07-31
```

报告：`2_Processed_AI/cross_check_reports/post_gen_*.json`。

## 工作正本

修出货必须写 `Shipments/…/出货表/`，再 export 到完整存档；禁止只改存档（见 C26079 根因备案于 Cross_Flow_Verify）。
