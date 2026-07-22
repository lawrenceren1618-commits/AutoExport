# AutoExport — 新对话交接包（压缩版）

> 用途：复制下方「新对话提示词」开新会话；本文件为完整规则底稿。  
> 项目根目录：`D:\.cursor\Cursor-projects\AutoExport`  
> 云端：GitHub / Vercel / Supabase = **AutoExport**；提交人 **Office CP**；SSH `github.com-office-cp`。  
> 口令：**准备上新** → `.cursor/rules/ready-for-next-session.mdc`（总结+压缩+提示词 + **洁癖轻量**对齐；不自动清场）。  
> 洁癖 skill：全局 `~\.cursor\skills\neat-freak\`；本仓 `.cursor/skills/neat-freak\`。

---

## 一、基建（勿重建）

GitHub / Vercel(Root=`web`) / Supabase / 后台登录·进度树·总表导入骨架 — **完成**。  
Web 锁定：Next.js + Supabase + Vercel；禁未经允许庞大依赖；UI 少弹窗；业务表单不得擅自删列 — `.cursor/rules/web-stack-ui-gate.mdc`。

旁注：`_workspace_archive_AutoExport_20260720` = Cursor 元数据归档（保留），非业务仓。见 `docs/WORKSPACE_ARCHIVE.md`。

---

## 二、组织与标签（固定）

- 一票一夹：`1_Input_Raw/Shipments/{订单号}_{店铺}_{出货日}_{条数}/`
- 流水线：`Templates/End_to_End_Shipment_Pipeline.md`
- 标签源：`00_Master_Reference/桌布标签`（只读；复制前后统计）
- **标签落盘固定**：`产品标签/{EF订单号}标签/{N}条装/{尺寸短码}/{源原名}.pdf`  
  映射：`Templates/Shipment_Product_Label_Layout.md` + `canonical_schema.json`（`label_output_layout` / `size_folder_map` / `color_aliases`）
- FNSKU 双向锁定：品牌+尺寸+条数/包+**颜色**+品名；米白=象牙白=Ivory；克重不阻断标签
- 路径检索：提供路径优先；空则下一级→上一级→同级（`user-path-resolve.mdc`）
- 近端：无标准发货计划表 → 订单驱动；远期拟：总表加发货列（FNSKU×箱数）

---

## 三、已确认默认

| 项 | 结论 |
|----|------|
| HS | `6302539090` |
| 克重 | 默认 90G |
| 订单/出货号 | EF 长号 / C0x 短号 |
| 货代品牌 | `无` |
| 出货 FNSKU | 不需要 |
| 尺寸短码↔全称 | **已确认**（84→60X84inch；102→60X102inch；126→60X126inch；**120→70X120inch**；90圆→90 inch round）— 使用者核验无误 |
| H01 沉淀 | WAIT（见下：总表确认入库握手，非尺寸映射） |

---

## 四、进度与本票

| 块 | 状态 |
|----|------|
| Canonical A | 完成 |
| 订单 M1 脚本 | 有骨架；正式出单管线未全通 |
| **本票标签** | **完成**：EF-C26079，23 PDF 已按条装×尺寸归类 |
| 出货 / 货代 / 报关 / FBA | 未全通 |
| H01 | WAIT |

**当前项目**：`Shipments/EF-C26079-C04-36460  桌布-2026.7.10`  
**订单源**：`…/订单表/`（C04 / WIGENIUS / 90G / 36460 条）  
**标签**：`…/产品标签/EF-C26079-C04-36460标签/`  
**会话临时文件**：已清理（`_tmp_*` 等）；`_workspace_archive_*` 仍保留（非业务仓）。

**下一会话优先处理**：①出货表生成（短号、无FNSKU）→ ②你建亚马逊货件并交 FBA 外箱贴后做报关/货代。尺寸短码已闭环。

---

## 五、主体硬规则

C04→WIGENIUS（页眉不写畅选）；C07→Dressmaker；FNSKU 不串店。

---

## 六、新对话提示词（复制即用）

````text
你是 AutoExport 数据处理助手。工作区：
D:\.cursor\Cursor-projects\AutoExport

先读：
- .cursorrules
- Templates/Next_Session_Handoff.md
- Templates/End_to_End_Shipment_Pipeline.md
- Templates/Shipment_Product_Label_Layout.md
- Templates/Canonical_Data_Schema.md
- Templates/00|01|02_*_Correspondence.md
- Scripts/canonical_schema.json
- .cursor/rules/web-stack-ui-gate.mdc
- .cursor/rules/label-source-gate.mdc

基建完成（GitHub/Vercel/Supabase=AutoExport；Office CP）。勿重建云端。Web=Next.js+Supabase+Vercel；禁私自上庞大依赖；UI少弹窗；表单不得擅自删列。

组织：Shipments/{订单号}_{店铺}_{出货日}_{条数}/
标签源：00_Master_Reference/桌布标签（只读）
标签落盘固定：产品标签/{EF订单号}标签/{N}条装/{尺寸}/{源原名}.pdf
FNSKU双向锁定：品牌+尺寸+条数/包+颜色+品名；米白=Ivory；克重不阻断标签。
路径：优先我给的路径；空则下/上/同级。

当前票：EF-C26079-C04-36460（C04/WIGENIUS/90G/36460条）
订单：…/Shipments/EF-C26079-C04-36460  桌布-2026.7.10/订单表/
标签已复制：…/产品标签/EF-C26079-C04-36460标签/（23 PDF）

已确认：HS=6302539090；克重默认90G；EF长号/出货短号；货代品牌=无；出货无FNSKU。
尺寸短码：84→60X84inch；102→60X102inch；126→60X126inch；120→70X120inch；90圆→90 inch round。
暂缓：H01 等我说再入库。

下一步优先（开场列树等我指定）：
1) 出货表（短号、无FNSKU）
2) 等我建亚马逊货件后：FBA外箱贴四级解析 → 报关 → 货代下单（品牌无）
3) 订单正式出单管线 Gate→Final（若需要重出）
4) H01（等我发话）

硬规则：C04↔WIGENIUS页眉不写畅选；C07↔Dressmaker；FNSKU不串店；冲突先汇报；最终件交叉对照；密钥不入库。
「准备上新」→ 总结+压缩+提示词+洁癖轻量对齐（不自动清场）。
````
