# AutoExport — 新对话交接包（压缩版）

> 项目根：`D:\.cursor\Cursor-projects\AutoExport`  
> GitHub / Vercel / Supabase 名：**AutoExport**；SSH `github.com-office-cp`；提交人 Office CP。  
> 口令：**准备上新** → 总结 + 压缩 + 提示词 + 洁癖轻量（不自动清场）。

---

## 存储与数据接口（重要）

| 层 | 内容 |
|----|------|
| **GitHub** | 规则、Templates、沉淀 JSON、流水线脚本、迁移、轻量草稿（json/md/必要 xlsx） |
| **数据接口** | 任务要模板/参考时按 **interface_id** 取得 — 见 [`Data_Source_Interfaces.md`](Data_Source_Interfaces.md) / `Scripts/data_source_interfaces.json` |
| **Supabase（下一阶段）** | 重 PDF（标签源、外箱贴树、产品标签）经 **Storage/API** 暴露；本阶段只登记接口，不上传 |

禁止把「标记路径」理解成绝对路径 dump；interim_reference 是可调用的模板/参考源。

---

## 实现路径（两阶段）

| 阶段 | 分支 | 目标 |
|------|------|------|
| **P0 固化本地** | `main` | 规则+轻量数据 push GitHub ✅（本收尾） |
| **P1 云端可执行** | `cloud/rules-runtime` | 接口落地：Storage/API + 作业跑已沉淀规则 → 再 Vercel |

P1 顺序：读 `data_source_interfaces.json` → Supabase schema/Storage 对齐 interface_id → Next 后台触发识别/货代生成 → Gate → 部署确认后 prod。

---

## 已确认默认（摘要）

货代：客户单号 `111111111`；箱重尺 16；单箱 floor；图片 reinject；销售链接 C04/C07；AWD reference 通常空。  
外箱贴：FC/AWD 统一识别+按版式确认字段；同仓同规格合并多页 PDF；一腿一渠道。  
货值误差率 ≤1%。SKU 骨架待总表。H01 WAIT。

沉淀：`Scripts/settled_knowledge_db.json` → `confirmed_defaults`。

---

## 本票 EF-C26079

`split_complete`：A=FC 805 箱；B=AWD IUTE 140 箱；草稿抽查通过。Gate→Final 仍须明示。  
重外箱贴/产品标签 PDF **不进 Git**；识别结果轻量 JSON 可进 Git。

---

## 洁癖轻量 · 删除候选（未确认不删）

| 候选 | 理由 |
|------|------|
| `2_Processed_AI/_inspect_*.py`、`_tmp_*.py`、`*_b64`、freight_inspect_*.txt | 会话调试残留 |
| `2_Processed_AI/drafts/_*.md/_*.txt/_run_*.py`、`C26079-A_manifest.DRAFT.json` | 临时扫描/草稿 |
| `Scripts/_inspect_b_media.py` | 一次性检查 |
| `web/_audit-env-keys.js`、`web/_env-link-test-run.js` | 本地探测 |
| `Templates/Local_Data_Paths.md` / `Scripts/local_data_paths.json` | 已废弃，可删或仅留跳转（现留跳转） |

---

## 新对话提示词

````text
你是 AutoExport 助手。工作区：D:\.cursor\Cursor-projects\AutoExport

先读：
- Templates/Next_Session_Handoff.md
- Templates/Data_Source_Interfaces.md
- Scripts/data_source_interfaces.json
- Scripts/settled_knowledge_db.json（confirmed_defaults）
- Templates/Carton_Label_Channels.md
- Templates/02_Freight_Forwarder_Correspondence.md
- .cursorrules

分支：在 cloud/rules-runtime 上，把已沉淀规则变成云端可执行（Supabase Storage/API 按 interface_id；勿把重 PDF 推进 Git）。
本票 C26079 本地已走通；Gate→Final / H01 / Vercel prod 须确认。
硬规则：一腿一渠道；货代图片 reinject；AWD 追踪通常空；误差率≤1%。
「准备上新」→ 总结+提示词+洁癖轻量。
````
