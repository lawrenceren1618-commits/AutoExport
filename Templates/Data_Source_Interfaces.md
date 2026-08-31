# 数据接口 / 模板与参考来源（Data Source Interfaces）

> 确认日：2026-07-24  
> 机器可读：[`Scripts/data_source_interfaces.json`](../Scripts/data_source_interfaces.json)  
> **本机绝对路径速查**（办公室作业）：[`Local_Operational_Paths.md`](Local_Operational_Paths.md)

> **不是**「禁止绝对路径」。接口表管「任务从哪取」；本机路径表管「这台电脑上稳定处理时的盘符位置」。二者并存。

## 存储分层

| 层 | 存什么 | 取得方式 |
|----|--------|----------|
| **根本库** | 已确认业务默认 / 主体品牌等 | `Scripts/settled_knowledge_db.json`；云端表 `autoexport.settled_config`（migration 20260726） |
| **GitHub AutoExport** | 规则、Templates、沉淀 JSON、流水线脚本、迁移、User_IO 空树、少量轻样例 | 仓库路径 / clone |
| **A 渠道** | 每次做单上传/取件 | `User_IO/` · 接口 `job.user_io_project` |
| **B 渠道** | 已验证过程 + 文件次级源 | `Shipments/` + Scripts · 接口 `ref.channel_b_shipments` |
| **接口（云端阶段）** | 重二进制：标签源 PDF、外箱贴树、当票产品标签副本 | **Supabase Storage / API**（TBD，本阶段只登记接口名 + 表结构） |
| **本机作业根路径** | 仓库/Shipments/标签源/输出等 | [`Local_Operational_Paths.md`](Local_Operational_Paths.md) **绝对路径** |
| **interim_reference** | 尚未上云前，脚本可读的已验证模板相对路径 | JSON 内 `interim_reference_rel` |

双渠道说明：[`Channel_AB_Architecture.md`](Channel_AB_Architecture.md)。


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
| 货代入库贴识别 | 货代回传入库贴 PDF | `job.freight_inbound_labels_inbox` | `货代入库贴/_inbox` → `12` 三重验证后写入 `FBA外箱贴/…/入库贴` | Upload API → Storage → `12` |
| 拆单/对照 | 计划+已发汇总 | `ref.split_ledger` | 项目 `拆单比对/*.json`（轻量可进 Git） | 表 `shipment_split_batches` |
| 沉淀默认/对照 | confirmed_defaults | `ref.settled_knowledge` | `Scripts/settled_knowledge_db.json`（Git） | 同步至 DB 或配置 API |
| 版式字段表 | FC/AWD 确认字段 | `ref.carton_label_channels` | `Templates/Carton_Label_Channels.md` + schema | 配置 API / JSON in DB |
| SKU 锁 | sku_index | `ref.amazon_sku_index` | 沉淀库骨架；总表补列后入库 | 表 `sku_index` |
| 仓头/追踪 | FBA↔追踪 | `mod.m4_fba_headers` | 草稿 JSON / `/admin/fba-track` | 已有迁移方向；H42 |
| Gate | 交叉对照权威 | `gate.hx_settled` | 读 settled + 当票草稿 | Gate 服务读 DB |
| 完整存档（仅复制） | 订单/出货/报关/外箱贴/货代下单表/入库贴 | `pack.archive_full` | `3_Output_Final/{项目}/完整存档/` | Storage zip API |
| 工厂贴标包（仅复制） | 按仓外箱贴 + 入库贴 | `pack.factory_label_kit` | `3_Output_Final/{项目}/{腿号}_{实发条数}_{出货日期}_贴标包/`（一腿一包；单仓扁平） | Storage zip API |
| 微信发送包 | 同订单同批次**仅贴标包**合并压缩 | `pack.wechat_send_zip` | `{订单短号}_{出货日}_微信发送.zip`（不含完整存档） | Storage 签名下载 |

握手模块（M0–M4、H01/H12/H42…）见 [`Architecture_Modules_Handshake.md`](Architecture_Modules_Handshake.md)。

---

## 原则

1. 登记的是 **接口与来源**，不是「把整个磁盘树列进仓库」。  
2. 重 PDF **不进 GitHub**；云端通过 **Storage/API** 暴露给作业。  
3. 本机稳定处理：绝对路径写在 [`Local_Operational_Paths.md`](Local_Operational_Paths.md)；规则/脚本正文仍优先相对仓库根。  
4. interim_reference 写相对仓库根的路径（可移植）。  
5. 未实现的云端接口标 `status: pending_cloud`，禁止臆造已上线 bucket。
