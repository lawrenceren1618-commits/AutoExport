# 亚马逊外箱贴：统一识别 + 按版式确认字段

> 确认日：2026-07-23（目的地规则库补 2026-08-19；引擎策略同日）  
> 沉淀：`settled_knowledge_db.json` → `confirmed_defaults.carton_label_channels`  
> 机器规则：[`Scripts/carton_destination_rules.json`](../Scripts/carton_destination_rules.json) 与 [`web/lib/pipeline/carton-destination-rules.json`](../web/lib/pipeline/carton-destination-rules.json) **两份内容必须相同**（先改 Scripts，再原样复制到 web；Vercel Root=`web`）  
> 识别引擎：主路径 PDF 文本层；备用 Tesseract 仅主路径失败时尝试（见 `Templates/Ocr_Dual_Convert_Compare.md`）  
> 脚本：`Scripts/10_carton_label_ingest.py` · `08_parse_fba_carton_labels.py` · `11_awd_iute_page_summary.py`

## 0. 定位（先读）

**拆分**和**合并**目的相同：

1. **便于助手识别**（抽字段、对计划、写货代/报关）  
2. **便于工厂贴标**（按仓、按规格批量打印）

二者不是两套业务，只是落盘形态：先按页/箱拆开识别，再按「同仓同规格」合并成工厂用的多页 PDF。

**真正要区分的是版式（渠道）**：FC 运营中心贴 vs AWD 贴（及日后 GWD）——字段名、货件号形态、仓码形态不同，必须走 **同一套「识别 → 确认字段」流程**，按版式映射表取值，禁止用 FC 字段硬套 AWD（或反之）。

```text
上传
  → [可选] 清洗 / 转化
  → 【统一】识别版式(channel) + 抽取候选字段
  → 【统一】按版式字段表确认（见 §3）
  → 分离（按仓×规格）→ 合并（同仓同规格一份多页PDF）→ 归纳
  → 下游拆单 / 货代 / 报关
```

---

## 1. 渠道 / 版式

| 代码 | 名称 | 版式状态 |
|------|------|----------|
| **FC** | 运营中心（FBA 仓） | 已用（C26079-A）；中文规格夹：`白色 60X102inches 6pack-9箱` |
| **AWD** | Warehousing & Distribution | 已标定（C26079-B、C26089 IUTE） |
| **GWD** | （停用） | 2026-07-24 起不纳入现役；勿新建 GWD 树 |
| `UNKNOWN` | 无法判定 | **宁空不填错**，汇报后手补 |

仓码与货件形态以 `carton_destination_rules.json` 已确认清单为准（新仓须你确认后再入库）。  
**确认闸门仍强制**：识别只给建议，降低手改量，不取消「确认」一步。

### 1.0.0 识别引擎（2026-08-19 确认）

- **主路径**：PDF 文本层（不默认跑 OCR）。  
- **备用**：已设计的 `tesseract.js` **保留不删**；仅当主路径无法处理或报错（非 PDF、无文本层、抽不出仓码且货件号）才尝试。  
- 抽出结果仍须人工确认。LlamaParse 仅显式对照，不自动当第三引擎。  
- 单价截图是另一条线，仍以 Tesseract 为主。

### 1.0.1 误识防护（2026-08-19）

- AWD 货件号必须是 `STAR-` + 连字符（例 `STAR-WDWSD2Q5T56Y4`）。禁止把 PDF `startxref` 识别成 `STARTXREF`。
- 未在规则库、又没有「货件名称」标签的四位乱码（如 `UCS2`）不得当仓码。
- 无标签的 8–12 位字母数字不得当参考号/追踪。

### 1.1 一腿一渠道（强制）

一票一次发运 = 一条拆单腿；**一腿只发 FC 或 AWD 之一**（互斥）。  
例：A=FC 五仓；B=AWD IUTE。

---

## 2. 统一作业流水线

| 步 | 必须？ | 说明 |
|----|--------|------|
| 清洗 / 转化 | 否 | 助手判断；不需要则跳过 |
| **识别版式 + 抽字段** | **是** | 先定 FC/AWD，再按下表抽 |
| **确认字段** | **是** | 与计划/总表/SKU 对照；冲突汇报 |
| 分离 → 合并 → 归纳 | **是** | 形态服务识别与贴标；最终 **一仓一规格一个多页 PDF** |

### 2.1 P-CARTON 完工标准（强制 · 2026-09-21）

| 步骤 | 脚本 | 产出 |
|------|------|------|
| 拆页识别 | `10_carton_label_ingest.py --apply` | `_staging` / 页级 `_p####`；**仅半成品** |
| promote | 拷到 `FBA外箱贴/{渠道}/{仓}/` | 仍可能是散页 |
| **规格归夹合并** | `17_reorg_carton_by_spec.py --apply` | **完工形态** |

**禁止**：仓根下只剩一堆 `_p0001…` 散页（或单文件整包）就跑 Gate / `13` Final。  
**C26105/106 教训**：曾扁平 promote → Final 拷出 370/275 散页；须归夹后重导。

**AWD 落盘（已验证 · 对齐 C26100）**

```text
FBA外箱贴/AWD/{仓}/
  {颜色}_{尺寸}_{N}条装/
    AWD_{仓}_{颜色}_{尺寸}_{N}条装_{箱数}箱.pdf   # 一规格一多页（发给工厂）
  AWD_{仓}_入库贴_{箱数}箱.pdf                   # 入库贴可在仓根
FBA外箱贴/_flat_pages/{渠道}/{仓}/flat_{时间}/   # 散页，不进贴标包，只供交叉核对
```

例：`米白_60X102inch_6条装/AWD_IUTJ_米白_60X102inch_6条装_180箱.pdf`  
FC 仍可用中文长夹名（如 `白色 60X102inches 6pack-9箱`）；原则同为 **一仓一规格一 PDF**。

归夹键优先 **FNSKU ↔ PROJECT/订单行**；页数必须等于该规格计划箱数，否则停等确认。

**页标纠偏（强制落盘 · 已沉淀）**：夹名包规错标、页内出现多种 `126-6`/`126-10` 等时，`08` 识别为 `page_mark_split` 后，必须再跑  
`Scripts/16_split_mixed_carton_spec_folders.py --apply`：

1. PDF **按页物理拆进**正确规格夹（禁止只改 JSON、夹内仍混装）  
2. **PDF 文件名 = 规格夹名**（含正确箱数），例：`米白色 60X126inches 10pack-9箱.pdf`，禁止沿用混装旧名如 `…6pack-15箱.pdf`  
3. 原混装夹改名 `.mixed_bak_*`；`13` 导出须跳过该备份  
4. 然后再导出贴标包  

沉淀键：`confirmed_defaults.carton_label_channels.page_mark_split_must_rewrite_folders` · `promote_must_reorg_by_spec`

---

## 3. 识别 + 确认字段（按版式区分 · 核心）

每页/每箱先产出公共骨架，再按 `channel` 填版式字段：

```text
channel, confidence, signals[]
# 公共（确认后写入仓头/拆单）
warehouse_key          # FC仓码 或 AWD站点
shipment_id            # 版式相关，见下表
spec: size, color, strips_per_pack
fnsku / amazon_sku     # 能抽则抽；SKU 优先见 SKU_Correspondence
box_index / box_total  # 若有
qty_cartons（汇总后）
```

### 3.1 版式字段对照（确认时用）

| 确认项 | **FC 版式** | **AWD 版式** |
|--------|-------------|--------------|
| 版式信号 | `FBA…U000001`、Fulfillment、四位仓码 | `AWD Box N of M`、`AWD 3PL`、`STAR-…` |
| **货件号** → 货代「任意订单号」 | `FBAxxxxxxxx` | `ShipmentID`（如 `STAR-QG6…`） |
| **仓库键** → 货代仓库代码 / 归纳夹 | AVP1、CLT2、LGB8… | 站点/3PL 名（如 **IUTE**） |
| **地址** | Amazon.com Services + 街道州邮编 | `IUTE - AWD 3PL - …` 等贴面地址 |
| **追踪 / reference** | 有则填（与 FBA 对应） | **通常空**（已确认） |
| **PO** | 少见 / 非货代 B15 | 可有（如 `8NK88PWJ`）→ 记 JSON，不硬塞 B15 |
| **规格** | 夹名 + 页标 `126-6` 等；可纠夹名 | 页内 SKU 行 + FNSKU（优先） |
| **箱序** | 箱唛序号 / 页序 | `Box N of M` |

GWD：已停用，不补版式表。

### 3.2 确认闸门（FC/AWD 相同）

1. `channel` 已判定且非 UNKNOWN（或人工指定）  
2. 货件号、仓库键、规格（尺寸+颜色+条数/包）齐全  
3. 与当腿计划箱数勾稽（按规格汇总）  
4. FNSKU/SKU 与沉淀或计划一致；冲突 → 备注，不静默  

确认通过后再做分离/合并落盘与下游单据。

### 3.3 版式特征速查

**FC**：`FBAxxxxU#####`；仓码 `[A-Z]{3}\d`；页标 `(84\|102\|120\|126\|90)-(2\|6\|10)`。  

**AWD**：`AWD Box`；`ShipmentID: STAR-`；`AWD 3PL`；站点如 IUTE。  

混页：按页分渠道，分别确认字段，禁止混进同一仓树。

---

## 4. 落盘形态（拆分 / 合并 = 同一目的）

```text
FBA外箱贴/
  _inbox/                 # 原始上传
  _staging/               # 确认前
  _recognize/             # 识别+字段确认报告
  FC|{AWD}/
    {warehouse_key}/
      {规格夹}/   # FC 与 AWD 中文命名见 §1；勿混用
        {渠道}_{仓}_{规格}_{N}箱.pdf   # 多页；同仓同规格仅此一份
      {渠道}_{仓}_入库贴_{N}箱.pdf     # 货代回传整理件；一仓一份（见 Freight_Inbound_Label_Pipeline.md）
```

| 中间 | 最终交付 |
|------|----------|
| 可按页临时拆开便于识别 | **同仓 + 同规格 → 一个多页 PDF**（工厂批量贴标） |
| 入库贴 `_inbox` → 验证 | **同仓 → 一个多页入库贴 PDF**（与外箱贴并列） |

页序：箱序号升序。  
旧扁平 FC 树（无 `FC/` 前缀）仍可读，默认 channel=FC。

---

## 5. 与下游

| 下游 | 用法 |
|------|------|
| 拆单 / 08 | 用已确认的 channel + warehouse_key + 规格汇总 |
| 货代 | 任意订单号 / reference / 仓码 **按 §3.1 版式表** |
| 报关 | 仍按目的仓一行；channel 写入仓头 JSON |

脚本：`10` 识别入库；`08` FC 统计；`11` AWD 页摘要；合并规则见本文件 §4。

---

## 6. 本票备忘

| 腿 | 版式 | 字段确认要点 |
|----|------|--------------|
| C26079-A | FC | 五仓 FBA + 追踪码；126 米白页标纠 6/10 |
| C26079-B | AWD | IUTE；STAR-…；reference 空；三规格 50+50+40 已合并多页 PDF |
| C26089 | AWD | IUTE；STAR-WDWSD2Q5T56Y4；追踪 2MSYJZTJ；1000 箱 |
