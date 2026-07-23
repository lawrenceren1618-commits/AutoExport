# AutoExport — 新对话交接包（压缩版）

> 用途：复制下方「新对话提示词」开新会话。  
> 项目根：`D:\.cursor\Cursor-projects\AutoExport`  
> 云端：GitHub / Vercel / Supabase = **AutoExport**；SSH `github.com-office-cp`；提交人 Office CP。  
> 口令：**准备上新** → `.cursor/rules/ready-for-next-session.mdc` + 洁癖轻量（不自动清场）。  
> **当前策略（2026-07-23）**：**先本地跑通，再同步云端**（勿催 push/Vercel）。

---

## 一、基建（勿重建）

| 层 | 状态 |
|----|------|
| GitHub ↔ Vercel(Root=`web`) | 已通 |
| Supabase | `.env.local` 已通；schema **`autoexport`** 迁移已备，**本地闭环后再上云** |
| Web | Next.js；禁庞大依赖；少弹窗；表单不删列 |

---

## 二、组织与标签（固定）

- 一票一夹：`1_Input_Raw/Shipments/{订单号}_{店铺}_{出货日}_{条数}/`
- 标签源只读：`00_Master_Reference/桌布标签`
- 落盘：`产品标签/{EF}标签/{N}条装/{尺寸短码}/{源原名}.pdf`
- FNSKU 双向锁定含**颜色**；米白=Ivory；克重不阻断
- **SKU**：店+牌内唯一；人工备注 → 确认后 `sku_index`（总表补列后入库）。见 `Templates/SKU_Correspondence.md`

---

## 三、已确认默认（沉淀库 `confirmed_defaults`）

| 项 | 结论 | 录入 |
|----|------|------|
| HS / 克重 | `6302539090` / 默认 90G | ✅ |
| 出货 | 无 FNSKU；短号 U 日期 | ✅ |
| 货值/毛净重 | 误差率≤1% 不报告；落表=分仓 B | ✅ `Amount_Weight_Reconcile.md` |
| 货代表固定 | 客户单号`111111111`；箱重尺全16；品牌三列无；单箱`floor` | ✅ `freight_order_form` |
| 货代图片 | DISPIMG+**强制 reinject**；验 media≥1 | ✅ 2026-07-23 |
| 销售链接 | C04/C07 分店 URL | ✅ |
| 货代 reference | FC=追踪码；**AWD 通常空** | ✅ |
| 渠道 | FC/AWD/GWD；**一腿一渠道互斥** | ✅ `Carton_Label_Channels.md` |
| SKU | 店+牌唯一；备注路径 | ✅ 骨架；`sku_index` 待总表 |
| H01 | WAIT | ✅ |

---

## 四、进度 EF-C26079（拆单完成）

项目：`1_Input_Raw/Shipments/EF-C26079-C04-36460  桌布-2026.7.10/`  
状态：`split_complete`（剩余 0）

| 腿 | 渠道 | 箱/条 | 货值对照 | 货代报关 | 抽查 |
|----|------|-------|----------|----------|------|
| **A** | FC 五仓 | 805 / 32260 | 0.073% 通过 | 各 5 | 已抽查 |
| **B** | **AWD** IUTE | 140 / 4200 | 0.097% 通过 | 各 1；图片已修 | 已抽查 |

Gate→`3_Output_Final`：**仍 WAIT**（草稿通过≠自动 Final，须明示进 Final）。  
云端 / H01：后置。

### 下一会话优先

1. 是否 **Gate→Final**（A+B 或分腿）  
2. 总表补 **SKU** 列 → 填 `SKU_人工备注` → 确认入 `sku_index`  
3. 本地闭环后再云端；H01 口头确认  

脚本：`08` · `07` · `09`（含 media 校验）· `10_carton_label_ingest` · `11_awd_iute_page_summary`

---

## 五、主体硬规则

C04↔WIGENIUS（页眉不写畅选）；C07↔Dressmaker；FNSKU/SKU 不串店。

---

## 六、新对话提示词（复制即用）

````text
你是 AutoExport 数据处理助手。工作区：
D:\.cursor\Cursor-projects\AutoExport

先读：
- Templates/Next_Session_Handoff.md
- Templates/Carton_Label_Channels.md
- Templates/SKU_Correspondence.md
- Templates/Amount_Weight_Reconcile.md
- Templates/02_Freight_Forwarder_Correspondence.md
- Scripts/settled_knowledge_db.json（confirmed_defaults）
- .cursorrules

策略：先本地；勿催云端。Web=Next+Supabase；禁庞大依赖；少弹窗；不删列。

当前票：EF-C26079-C04-36460（split_complete）
- A=FC 805箱；B=AWD IUTE 140箱；货代报关草稿已生成且抽查通过；图片 reinject 已修。
- 待办：是否 Gate→Final；总表 SKU 入库；H01/云端后置。

硬规则：一腿一渠道；货代图片必须 reinject；AWD 追踪码通常空；客户单号111111111；箱重尺16；误差率≤1%。
「准备上新」→ 总结+压缩+提示词+洁癖轻量。
````
