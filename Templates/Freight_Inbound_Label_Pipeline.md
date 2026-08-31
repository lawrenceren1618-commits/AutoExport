# 货代入库贴流水线

> 确认日：2026-07-24  
> 沉淀：`settled_knowledge_db.json` → `confirmed_defaults.freight_inbound_labels`  
> 脚本：`Scripts/12_freight_inbound_label_ingest.py`  
> 与「货代入库贴**下单表**」分目录：见 [`02_Freight_Forwarder_Correspondence.md`](02_Freight_Forwarder_Correspondence.md)

## 0. 定位

| | **下单表** | **入库贴** |
|--|-----------|------------|
| 谁产生 | 系统按仓生成 xlsx | **货代业务员**根据下单表回传 PDF（**普通货代**）；或**已含于外箱贴**（**SEND 承运人**，见下） |
| 目录 | `货代入库贴下单表/` | `货代入库贴/`（上传/识别）→ 确认后写入 `FBA外箱贴/{渠道}/{仓}/` |
| 用途 | 发给货代下单 | 工厂贴标备货；与外箱贴按仓配对 |

### 0.1 货代类型：SEND 承运人 vs 普通货代（2026-08-20 确认）

机器可读：`Scripts/freight_forwarder_profiles.json`。

| 类型 | 代表货代 | 外箱贴来源 | 是否另要入库贴 |
|------|----------|------------|----------------|
| **亚马逊 SEND 承运人** | **纽酷** | 卖家从亚马逊后台下载 | **否** — 下载的外箱贴 PDF **已自带入库贴**，SEND 流程不额外回传 |
| **普通货代** | **物易通** 等 | 使用者上传或货代提供 | **是** — 须先发货代下单表，货代回传 PDF → 本流水线识别入库 |

作业要点：

1. **SEND 腿**（如 C26089-A 纽酷 FC 五仓）：只收外箱贴；**不**等 `货代入库贴/_inbox`；贴标包可仅给外箱贴，manifest 标 `inbound_skipped_send` 而非缺失。  
2. **普通货代腿**（如 C26089-B 物易通 AWD）：下单表 + 等回传入库贴；无确认 PDF 前贴标包 `入库贴/` 标缺失。  
3. 下单表（xlsx）两类货代**均可生成**（报关/对账用）；SEND 腿入库贴**不依赖**货代回传。

来源途径（**普通货代**；强制顺序）：

1. 人工将货代下单表发给货代业务员  
2. 业务员回传「根据下单表生成」的入库贴 PDF  
3. 放入当票 `货代入库贴/_inbox/`  
4. 助手识别 → 规范化 → **三重交叉验证** + **页去重** → 按仓合并为一仓一 PDF → 落入对应外箱贴仓夹  

**禁止**在 `3_Output_Final` 内做识别/合并；成品仓只复制。

---

## 1. 处理区目录

```text
货代入库贴/
  _inbox/          # 货代回传原件（使用者放入）
  _staging/        # 按页拆分（确认前）
  _recognize/      # 识别 JSON + 交叉验证报告
```

正式整理件（通过验证后）：

```text
FBA外箱贴/{FC|AWD}/{仓码}/
  {颜色}_{尺寸}_{N}条装/{渠道}_{仓}_{规格}_{N}箱.pdf   # 外箱贴
  {渠道}_{仓}_入库贴_{N}箱.pdf                         # 入库贴（本流水线）
```

例：`FBA外箱贴/FC/AVP1/FC_AVP1_入库贴_175箱.pdf`  
（GWD 已停用，勿新建该渠道树。）

外箱贴 = 一仓一规格一多页 PDF；入库贴 = **一仓一多页 PDF**。

---

## 2. 流水线

```text
_inbox 上传
  → 识别（页级：shipment_id / warehouse_code / 指纹）
  → 规范化 JSON（仓级汇总）
  → 三重交叉验证 + 页去重无重复
  →（通过）按仓合并 → 写入 FBA外箱贴/{渠道}/{仓}/
  → 复制进输出两包（完整存档 / 工厂贴标包）
```

### 2.1 识别字段

| 字段 | 用途 |
|------|------|
| `shipment_id` | FC=`FBA…`；AWD=`STAR-…` 等；对照下单表「任意订单号」与外箱贴货件号 |
| `warehouse_code` | 对照下单表仓码与 `FBA外箱贴/.../{仓}/` |
| `page_index` / `page_fingerprint` | 张数统计；去重 |
| `carton_seq` | 贴面有则抽；非强制 |

版式启发式可复用外箱贴文本抽取；**C26079 样例已标定（2026-07-24）**：

| 信号 | 例 |
|------|-----|
| 文件名 | `label_FBA19JT39521_175.pdf` / `label_STAR-QG6…_140.pdf` |
| 正文 | `Receiving Information: AVP1`（或 IUTE） |
| 货件号 | `FBA…` 或 `STAR-…` |
| 箱序 | 页内 `n/N`（去重指纹） |

无可靠信号 → `UNKNOWN`，阻断合并。

### 2.2 三重交叉验证（强制）

权威对照：当腿 **货代下单表**（仓码 / 任意订单号 / 箱数）+ **外箱贴归纳**（仓码 / 货件号 / 箱数合计）。

| # | 项 | 规则 |
|---|----|------|
| 1 | FBA / 货件号 | 入库贴 `shipment_id` ≡ 该仓下单表任意订单号 ≡ 外箱贴该仓货件号 |
| 2 | 仓库代码 | 入库贴 `warehouse_code` ≡ 下单表仓码 ≡ 外箱贴仓夹名 |
| 3 | 张数 ≡ 箱数 | 去重后总页数 = 该仓下单表箱数 = 外箱贴该仓箱数合计 |

另：**同一 PDF / 合并结果内不得有重复页**（页指纹相同 → 阻断并列出页号）。

任一失败 → **阻断**写入正式入库贴；只写 `_recognize` 报告。

### 2.3 合并与命名

通过后：按 `warehouse_code` 合并页序（箱序升序，若无箱序则按源文件页序）→ 一仓一文件：

```text
{渠道}_{仓码}_入库贴_{N}箱.pdf
```

`N` = 去重后页数（须已通过张数≡箱数）。

---

## 3. 与输出两包

见 [`Colleague_Pack_Export.md`](Colleague_Pack_Export.md)：

- **完整存档**：含订单、出货、报关、外箱贴、货代下单表、**货代入库贴**（确认件）  
- **工厂贴标包**：按目的仓 → 该仓外箱贴 + 该仓入库贴  

---

## 4. 脚本用法

```text
python Scripts/12_freight_inbound_label_ingest.py --project "Shipments/…"
python Scripts/12_freight_inbound_label_ingest.py --project "…" --apply
```

默认 inbox：`{project}/货代入库贴/_inbox`。无 `--apply` 时仅识别与验证报告。  
对照基准：缺省合并 `2_Processed_AI/drafts/*freight_customs_summary.json`（A/B）+ 下单表文件名 + 外箱贴仓箱统计。

## 5. 本票 C26079 验证记录（2026-07-24）

| 仓 | 渠道 | 货件号 | 页数=箱数 | 正式件 |
|----|------|--------|-----------|--------|
| AVP1 | FC | FBA19JT39521 | 175 | `FC_AVP1_入库贴_175箱.pdf` |
| CLT2 | FC | FBA19JT71WTZ | 128 | `FC_CLT2_入库贴_128箱.pdf` |
| GYR2 | FC | FBA19JT3Q0H0 | 139 | `FC_GYR2_入库贴_139箱.pdf` |
| LGB8 | FC | FBA19JT0K3PY | 182 | `FC_LGB8_入库贴_182箱.pdf` |
| MDW2 | FC | FBA19JT16DMQ | 181 | `FC_MDW2_入库贴_181箱.pdf` |
| IUTE | AWD | STAR-QG6CTURZGY6MX | 140 | `AWD_IUTE_入库贴_140箱.pdf` |

源包：`货代入库贴/945箱入库贴(1).zip` → `_inbox`；报告：`货代入库贴/_recognize/inbound_recognize_latest.json`。  
三重验证 + 无重复页：**全通过**；已沉淀 `settled_knowledge_db.json` → `freight_inbound_labels.layout_calibrated`。
