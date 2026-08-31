# 发货存档索引（按发货日三级归类）

> 确认日：2026-07-29（详细层 + 单价截图流）  
> 机器：`Scripts/shipment_archive_index.json` · `web/lib/pipeline/archive-index.ts`  
> UI：`/ops/archives`（库务；**不进** `/workspace` 主路径）  
> 字段权威：[`Ship_Stats_Correspondence.md`](Ship_Stats_Correspondence.md)

## 原则

1. **仅索引视图**：不建 `YYYY/MM/DD` 物理夹。  
2. **按存档日**三级：年 → 月 → 日。日期 = **实际交货日**（优先）否则 **订单交货日**（`job.ship_date` / `order_delivery_date`）；**禁止**用 `created_at` / 做任务时间。  
3. **叶子汇总**：短码 · 批次 · **整票箱数**（库内/悬停为 EF 长号）。  
4. **详细项**：点击展开 `spec_details`（各规格箱数）。  
5. **写入时机**：Gate 确认 + `archive` 步成功后登记（同 job 覆盖；**今后业务必须进统计**）。  
6. **成本 S3**：上传单价截图 → OCR → 你确认 → 云端仅 `batch_total_cost`；本地 `发货统计/local_unit_prices/{id}.json`。

## 日期判定（A1）

```text
actual_delivery_date  （有则用）
        ↓ 无 → 视为 = 订单交货日
order_delivery_date / job.ship_date
        ↓
禁止 fallback 到 created_at
```

机器：`resolveArchiveShipDate`；创建作业时若未填实际交货日，会写入 `actual_delivery_date = order_delivery_date`。

## 箱数口径

优先：外箱贴确认行合计；否则计划行 `qty_cartons`；详细层用计划行规格箱数。

## API

- `GET /api/ops/archives`
- `POST /api/ops/archives/cost-shot`（multipart：entry_id + file）
- `POST /api/ops/archives/cost-confirm`（JSON：confirm + batch_total_cost + lines）
