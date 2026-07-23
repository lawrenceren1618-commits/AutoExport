# 数据接口 / 模板与参考来源（Data Source Interfaces）

> 确认日：2026-07-23  
> 机器可读：[`Scripts/data_source_interfaces.json`](../Scripts/data_source_interfaces.json)  
> **不是**本机绝对路径清单；是任务需要模板/参考时，**从哪个接口取得**。

## 存储分层

| 层 | 存什么 | 取得方式 |
|----|--------|----------|
| **GitHub AutoExport** | 规则、Templates、沉淀 JSON、流水线脚本、迁移、轻量草稿（json/md/必要 xlsx） | 仓库路径 / clone |
| **接口（云端阶段）** | 重二进制：标签源 PDF、外箱贴树、当票产品标签副本 | **Supabase Storage / API / 后台路由**（TBD，本阶段只登记接口名） |
| **本机临时参考** | 尚未上云前，脚本仍可读的已验证模板/总表/标签源位置 | 记为 **interim_reference**（任务可调用的参考源，不是「待 dump 目录表」） |

云端作业实现时：优先走 **interface_id**；interim 仅本地跑通期兜底。

---

## 任务 → 需要 → 接口

| 任务 | 需要（模板/参考） | interface_id | 如何取得（当前） | 云端拟议 |
|------|-------------------|--------------|------------------|----------|
| 货代下单生成 | 已验证货代 xlsx（含样例图 media） | `tpl.freight_order_xlsx` | Git 内相对路径见 JSON；脚本 `09` `FREIGHT_TEMPLATE` | Supabase Storage `templates/freight/` 或 Storage URL API |
| 报关 1039 生成 | 已验证报关 xlsx | `tpl.customs_1039_xlsx` | 同上 `CUSTOMS_TEMPLATE` | Storage `templates/customs/` |
| 总表补齐箱规/1039 单价 | 人工产品总表 | `ref.master_product_table` | `00_Master_Reference` 总表 xlsx（interim） | 表 `autoexport.master_products` / Storage + H01 |
| 产品标签复制 | 桌布标签源 PDF 库 | `ref.label_source_library` | 标签源闸门路径（只读复制） | Storage bucket `label-source`（只读策略） |
| 外箱贴识别 FC/AWD | 当票上传的外箱贴 | `job.carton_labels_inbox` | 项目 `FBA外箱贴/_inbox` → 识别流水线 | Upload API → Storage → `10`/`08` 作业 |
| 拆单/对照 | 计划+已发汇总 | `ref.split_ledger` | 项目 `拆单比对/*.json`（轻量可进 Git） | 表 `shipment_split_batches` |
| 沉淀默认/对照 | confirmed_defaults | `ref.settled_knowledge` | `Scripts/settled_knowledge_db.json`（Git） | 同步至 DB 或配置 API |
| 版式字段表 | FC/AWD 确认字段 | `ref.carton_label_channels` | `Templates/Carton_Label_Channels.md` + schema | 配置 API / JSON in DB |
| SKU 锁 | sku_index | `ref.amazon_sku_index` | 沉淀库骨架；总表补列后入库 | 表 `sku_index` |
| 仓头/追踪 | FBA↔追踪 | `mod.m4_fba_headers` | 草稿 JSON / `/admin/fba-track` | 已有迁移方向；H42 |
| Gate | 交叉对照权威 | `gate.hx_settled` | 读 settled + 当票草稿 | Gate 服务读 DB |

握手模块（M0–M4、H01/H12/H42…）见 [`Architecture_Modules_Handshake.md`](Architecture_Modules_Handshake.md)。

---

## 原则

1. 登记的是 **接口与来源**，不是「把整个磁盘树列进仓库」。  
2. 重 PDF **不进 GitHub**；云端通过 **Storage/API** 暴露给作业。  
3. interim_reference 写相对仓库根的路径（可移植）；绝对盘符仅作本机备注可选字段。  
4. 未实现的云端接口标 `status: pending_cloud`，禁止臆造已上线 bucket。
