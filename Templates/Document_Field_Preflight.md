# 单据字段预检（Document Field Preflight）

> 确认日：2026-07-24  
> 补充规则：不改既有 C04 填表正文；每步生成前先核对「当前已有信息是否足够」。  
> 机器可读：`Scripts/document_field_preflight.json`  
> 报错闸门：`.cursor/rules/error-confirm-gate.mdc`

## 强制顺序（每张表）

```text
1. 列出该单据 required_fields（本文件 / JSON）
2. 对照当票 PROJECT.json + 订单 + 外箱贴识别 + 总表 join 等「当前已有」
3. 不足 → 写入缺失清单，提示使用者；本表 SKIP（不得臆造）
4. 足够 → 执行生成 / 复制 / 归纳
5. 全部报错与缺失一次汇总（不得只报第一条）
```

## 本票单据清单与必填

| 单据 | required（摘要） | 本票常见来源 |
|------|------------------|--------------|
| **订单表** | 已有 EF 订单文件（近端已写好则跳过生成） | `订单表/*.xls` |
| **外箱贴归纳** | inbox PDF；渠道/仓码/货件号/页数可识别 | `FBA外箱贴/_inbox` |
| **货代下单表** | 仓码、货件号、地址、箱数、条数、店铺销售链接；单价可用总表 1039；**FC 追踪编码→B15**（截图见 `_tracking_inbox`） | **登记 JSON**（`PROJECT.json` / `split_ledger` / `*_recognize.json`）+ 订单 + 总表 1039；**不要求外箱贴 PDF**（见 `document_field_preflight.json` → `freight`）；追踪截图 [`Shipment_Tracking_Screenshot_Inbox.md`](Shipment_Tracking_Screenshot_Inbox.md) |
| **报关资料表** | 仓、箱数、条数、毛净重、单价/货值、**合同协议号（登记库未撞号）**；表内抬头按店 | 货代同口径 + 总表；协议号见 [`Customs_Contract_Protocol_No.md`](Customs_Contract_Protocol_No.md) |
| **出货表** | `ship_date`、店码、出货短号、**所属订单=订单短码**、尺寸+颜色明细（无 FNSKU）、业务员 | 订单上半；短号基准；事后见 [`Post_Gen_Verify.md`](Post_Gen_Verify.md) |
| **产品标签** | 品牌+尺寸+条数/包+颜色 → 标签源 PDF 存在 | 订单下半 + `桌布标签` |
| **货代入库贴** | 货代回传 PDF；下单表箱数可对照 | `货代入库贴/_inbox` |
| **输出两包/微信 zip** | 外箱贴正式树 +（建议）入库贴；贴标包按腿 | Shipments 成品子树 |
| **Gate→Final** | 使用者明示 + 交叉对照通过（含事后跨表） | 草稿 vs 沉淀库 + [`Cross_Flow_Verify.md`](Cross_Flow_Verify.md) |

## 与多单并批

同日多 EF：出货表按 `ship_date` 合并预检「各单上半明细是否齐」。  
货代/报关：按仓预检，并用 Σ订单总条数/总箱数 交叉核对。见 [`Multi_Order_Ship_Batch.md`](Multi_Order_Ship_Batch.md)。
