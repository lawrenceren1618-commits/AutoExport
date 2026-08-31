# 货件追踪编码（主路径 PDF 文本层 · 失败才备用 OCR）

> 确认日：2026-07-31（默认不跑 OCR，防卡顿）；2026-08-19：Tesseract **保留为备用**，仅主路径无法处理/报错时尝试。  
> 补充规则：不改货代「客户单号=111111111」；**追踪编码**写货代表 **B15**（任意订单号旁），禁止写入客户单号。  
> FC：有则填；AWD：通常空（既有确认）。

## 库务入口

`/ops/fba-track`：上传 **PDF** → 主路径文本层抽取 → 抽不出仓+货件号才备用 Tesseract → 空字段手补 → 「确认保存参考」。

图片无 PDF 文本层 → 直接走备用 OCR；仍须确认。规划见 `Templates/Ocr_Dual_Convert_Compare.md`。

## 上传路径（当票本地流水线，可选）

```text
Shipments/{项目}/货代入库贴下单表/_tracking_inbox/
```

## 识别字段

| 字段 | 来源信号（PDF 文本层） | 写入 |
|------|------------------|------|
| `warehouse_code` | 货件名称前缀 / 仓码 | 匹配货代表 |
| `fba_shipment_id` | 「货件编号」`FBA…` | 与货代 A15 核对 |
| `tracking_id` | PDF 有则填；**无则空置手补** | 货代 **B15** |
| `cartons` | 各仓自己的箱数（段内「N箱」）；**禁止**用总箱填每仓 | 交叉核对 / 货代箱数 |

## 流程

```text
PDF → 主路径文本层归类（有则填 / 宁空不填错）
  →（仅失败）备用 Tesseract
  → 人工补空 → 确认保存参考（fba_warehouse_headers）
  → 货代等单据调用（H42 / B15）
```

主、备都抽不出 → 空行手填；预检仍可标缺失。

## 与预检

`document_field_preflight`：`freight.optional` 含 `tracking_id`；**FC 且已提供材料则升为 required**。
