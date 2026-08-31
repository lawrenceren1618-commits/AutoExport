# 多单同批发货（主单拆腿 + 次单并腿）

> 确认日：2026-07-24  
> 本票样例：主单 **EF-C26080** 拆 A/B；次单 **EF-C26068** 并入其中一批  
> 同构参考：C26079（一单多腿）+ 本文件扩展  
> 沉淀：`settled_knowledge_db.json` → `confirmed_defaults.multi_order_ship_batch`  
> 报错闸门：`.cursor/rules/error-confirm-gate.mdc`

## 0. 定位

| 模式 | 说明 |
|------|------|
| **一单多腿**（C26079） | 一个 EF 拆 `C26079-A` / `-B`… |
| **主单拆腿 + 次单并腿**（本文件） | 主 EF 仍拆腿；**另一 EF 整单（或该批发货量）并入主单的某一腿** |

- **宿主项目夹**：以主单命名（近端可先 `EF-C26080_待识别`，识别后按 [`Shipment_Project_Layout.md`](Shipment_Project_Layout.md) 改名）。  
- **次单不单独建票夹**：订单文件与主单同放 `订单表/`。  
- **腿 ID**：始终以**主单短码**编号：`C26080-A`、`C26080-B`（次单不另起 `C26068-A` 作物理批主键）。

## 1. PROJECT.json 字段

| 字段 | 说明 |
|------|------|
| `order_codes` | 本项目全部 EF 长号列表（主+次） |
| `primary_order_stem` / `split_order_stem` | 主单短码，如 `C26080` |
| `co_ship.enabled` | `true` |
| `co_ship.secondary_order_stem` | 如 `C26068` |
| `co_ship.join_leg` | `C26080-A` 或 `C26080-B`；识别前可为 `null` |
| `split_shipment` | `true`（主单拆批） |

歧义（无法判断次单并入哪腿、跨店混 FNSKU 等）→ **报错清单 → 停 → 使用者确认**（见 error-confirm-gate）。

## 2. 单据生成主键（强制）

| 单据 | 主键 / 合并规则 | 交叉核对 |
|------|-----------------|----------|
| **出货表** | **`ship_date`**：同一出货日的全部订单行 → **一张**出货表（同店）；跨店 → 报错待确认 | 出货数量 ↔ 当日各腿实发条数 |
| **货代下单表** | **`warehouse_code`** 为核心（一仓一文件/一行综合，沿用既有货代规则） | Σ(各订单计划总条数/总箱数) ↔ Σ(分仓条数/箱数)；误差率口径见 [`Amount_Weight_Reconcile.md`](Amount_Weight_Reconcile.md) |
| **报关** | **仓 + 条数** 为核心（生成与勾稽对齐货代分仓） | 同分仓条数/箱数与订单合计 |

微信贴标包：仍 **仅贴标包**、按物理发货腿合并；命名以主单短码：`{C26080}_{出货日}_微信发送.zip`。见 [`Colleague_Pack_Export.md`](Colleague_Pack_Export.md)。

## 3. 标签与 FNSKU

- 产品标签仍按 **各自 EF**：`产品标签/{EF}标签/{N}条装/{尺寸}/原名.pdf`  
- **禁止** C04↔C07 串 FNSKU；跨店并批必须先报错待确认  

## 4. 上传 → 识别状态机

```text
WAIT_UPLOAD
  → RECOGNIZE（订单表 + FBA外箱贴/_inbox）
  → PREFLIGHT（每表字段预检，见 Document_Field_Preflight.md）
  → CONFIRM_ERRORS（汇总全部报错/缺失；未确认不得硬填）
  → LEDGER（split_ledger + co_ship.join_leg；可改项目夹名）
  → DOCS（出货按日 / 货代按仓 / 报关按仓 / 标签 / 入库贴 / 两包）
  → GATE（须明示）→ Final
```

近端本票：已写好订单 + 外箱贴驱动。  
远期：使用者在总表加发货批次列（FNSKU×箱数）后，用订单规格键 join 总表生成全套单据；**列名未定前禁止臆造解析器**。

## 5. 本票上传路径

```text
1_Input_Raw/Shipments/EF-C26080_待识别/
  订单表/                         # EF-C26080 + EF-C26068
  FBA外箱贴/_inbox/               # 可分子夹 batch_A / batch_B
  货代入库贴/_inbox/
  拆单比对/
  PROJECT.json                    # status=WAIT_UPLOAD
  UPLOAD_README.md
```

绝对根：`D:\.cursor\Cursor-projects\AutoExport\1_Input_Raw\Shipments\EF-C26080_待识别\`
